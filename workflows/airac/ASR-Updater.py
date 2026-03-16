#!/usr/bin/env python3

import os
import requests

# ------------------------------------------------------------------------------
# 1. Define URLs
# ------------------------------------------------------------------------------
# UK fixes (multiple files, explicitly listed)
BASE_UK_URL = (
    "https://raw.githubusercontent.com/VATSIM-UK/UK-Sector-File/main/Navaids/"
)

UK_FILE_LIST = [
    "FIXES_UK.txt",
    "FIXES_CICZ.txt",
    "FIXES_HMRI-Gates.txt",
]

# For non-UK fixes, there's a separate folder containing multiple .txt files:
BASE_NON_UK_URL = (
    "https://raw.githubusercontent.com/VATSIM-UK/UK-Sector-File/main/Navaids/Fixes_Non-UK/"
)

# Replace these with the actual filenames in Fixes_Non-UK/ that we want to pull from:
NON_UK_FILE_LIST = [
    "FIXES_Belgium.txt",
    "FIXES_France.txt",
    "FIXES_Ireland.txt",
    "FIXES_Netherlands.txt",
    "FIXES_Norway.txt",
    "FIXES_Other.txt",
]

# The exclude/include lists:
URL_FIXES_EXCLUDE = (
    "https://raw.githubusercontent.com/VATSIM-UK/uk-controller-pack/main/.data/fixes_exclude.txt"
)
URL_FIXES_INCLUDE = (
    "https://raw.githubusercontent.com/VATSIM-UK/uk-controller-pack/main/.data/fixes_include.txt"
)


# ------------------------------------------------------------------------------
# 2. Helpers to retrieve lines and parse fix name
# ------------------------------------------------------------------------------
def get_uncommented_lines(url):
    """
    Downloads the file at 'url' using requests,
    returns a list of non-empty, uncommented lines.
    Lines beginning with ';' are considered comments.
    """
    resp = requests.get(url)
    resp.raise_for_status()

    lines = []
    for line in resp.text.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        lines.append(line)
    return lines

def parse_fix_name(line):
    """
    For lines like "BEGID N056.30.00.000 W014.00.00.000",
    return "BEGID" as the fix name.
    """
    parts = line.split()
    if len(parts) < 3:
        return None
    return parts[0].upper()

def is_valid_uk_fix(name, fixes_exclude):
    """
    A valid UK fix:
      - Exactly 5 letters
      - No digits
      - Not in fixes_exclude
    """
    if len(name) != 5:
        return False
    if any(ch.isdigit() for ch in name):
        return False
    if name in fixes_exclude:
        return False
    return True

# ------------------------------------------------------------------------------
# 3. Build the final set of fixes
# ------------------------------------------------------------------------------
def build_final_fixes():
    fixes_exclude = set(get_uncommented_lines(URL_FIXES_EXCLUDE))
    fixes_include = set(get_uncommented_lines(URL_FIXES_INCLUDE))

    # Collect UK fixes from multiple UK files
    uk_fixes = []
    for fname in UK_FILE_LIST:
        file_url = BASE_UK_URL + fname
        lines = get_uncommented_lines(file_url)
        for line in lines:
            fix_name = parse_fix_name(line)
            if fix_name and is_valid_uk_fix(fix_name, fixes_exclude):
                uk_fixes.append(fix_name)

    # Collect Non-UK fixes
    non_uk_fixes = []
    for fname in NON_UK_FILE_LIST:
        file_url = BASE_NON_UK_URL + fname
        lines = get_uncommented_lines(file_url)
        for line in lines:
            fix_name = parse_fix_name(line)
            if fix_name and (fix_name in fixes_include):
                non_uk_fixes.append(fix_name)

    # Combine, remove duplicates, sort
    final_fixes = sorted(set(uk_fixes + non_uk_fixes))
    return final_fixes

# ------------------------------------------------------------------------------
# 4. Update .asr files:
#    - Only process files whose name has "2", "3", or "4",
#      AND does NOT contain "ground" or "g2"/"g3"/"g4".
#    - Remove the old 'Fixes:' lines from the location they appear,
#      then insert the new lines at that same position (block replacement).
# ------------------------------------------------------------------------------
def update_asr_files(final_fixes, asr_root="UK/Data/ASR"):
    """
    Recursively find .asr files in 'asr_root'. For each file:
      - Skip if it has "ground" or "g2","g3","g4" in the name.
      - Skip if it doesn't contain '2','3','4' at all.
      - Otherwise:
          1) Find the first block of lines that start with Fixes: (case-insensitive).
          2) Remove them, then insert the new lines in that exact spot.
          3) If no old Fixes lines exist but the file is 2/3/4, do nothing (or optionally insert at end).
    """
    for root, dirs, files in os.walk(asr_root):
        for filename in files:
            name_lower = filename.lower()
            if not name_lower.endswith(".asr"):
                continue

            # Exclude if filename contains 'ground'
            if "ground" in name_lower:
                continue
            # Exclude if 'g2','g3','g4' in name
            if any((f"g{digit}" in name_lower) for digit in ["2","3","4"]):
                continue

            # Must contain '2','3', or '4' to be processed
            if not any(digit in name_lower for digit in ["2","3","4"]):
                continue

            filepath = os.path.join(root, filename)
            print(f"Processing: {filepath}")

            # Decide what lines we want to eventually insert
            lines_to_insert = []
            if "2" in name_lower or "3" in name_lower:
                for fix in final_fixes:
                    lines_to_insert.append(f"Fixes:{fix}:symbol")
            elif "4" in name_lower:
                for fix in final_fixes:
                    lines_to_insert.append(f"Fixes:{fix}:name")
                    lines_to_insert.append(f"Fixes:{fix}:symbol")

            # Read the original file
            with open(filepath, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            new_lines = []
            i = 0
            inserted_once = False

            while i < len(original_lines):
                line = original_lines[i]
                # If we find a "Fixes:" block, skip it
                if line.strip().lower().startswith("fixes:"):
                    # Remove consecutive lines that start with 'Fixes:'
                    while i < len(original_lines) and original_lines[i].strip().lower().startswith("fixes:"):
                        i += 1
                    # Insert the new lines at this same position
                    for inserted_line in lines_to_insert:
                        new_lines.append(inserted_line)
                    inserted_once = True
                else:
                    # Keep the line
                    new_lines.append(line.rstrip("\n"))
                    i += 1

            # If no old Fixes lines found in this file, do we want to do anything?
            # If you prefer to insert them anyway (at the end), you can uncomment:
            #
            # if not inserted_once and lines_to_insert:
            #     # Insert at the end (or some other logic)
            #     new_lines.append("")  # blank line if you like
            #     new_lines.extend(lines_to_insert)

            # Rewrite the file
            with open(filepath, "w", encoding="utf-8") as f:
                for line in new_lines:
                    f.write(line + "\n")

            print(f" -> Removed old Fixes: lines, reinserted {len(lines_to_insert)} lines.\n")

# ------------------------------------------------------------------------------
# 5. Main entry point
# ------------------------------------------------------------------------------
def main():
    final_fixes = build_final_fixes()
    update_asr_files(final_fixes, asr_root="UK/Data/ASR")

if __name__ == "__main__":
    main()
