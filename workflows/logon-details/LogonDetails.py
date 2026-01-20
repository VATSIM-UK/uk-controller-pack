import os
import re
from pathlib import Path
import sys
import json
import time
import winreg
import tkinter as tk
from tkinter import simpledialog, messagebox, ttk
import tkinter.simpledialog as simpledialog 
from PIL import Image, ImageTk
from ctypes import windll, c_uint

_original_init = simpledialog.Dialog.__init__

def is_dark_theme_enabled():
    try:
        # Read from Windows registry: AppsUseLightTheme (0 = dark, 1 = light)
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except Exception:
        return False  # Default to light if detection fails
    
def apply_azure_theme(root):
    try:
        style = ttk.Style()
        theme_dir = resource_path("theme")

        if "azure-light" not in style.theme_names():
            root.tk.call("source", os.path.join(theme_dir, "light.tcl"))
        if "azure-dark" not in style.theme_names():
            root.tk.call("source", os.path.join(theme_dir, "dark.tcl"))
        if "azure-light" not in style.theme_names():
            root.tk.call("source", resource_path("azure.tcl"))
            
        print("Registry dark theme enabled:", is_dark_theme_enabled())

        theme = "azure-dark" if is_dark_theme_enabled() else "azure-light"
        print("Applying theme:", theme)
        style.theme_use(theme)

    except Exception as e:
        messagebox.showwarning("Theme Load Failed", f"Could not load Azure theme:\n{e}")


def _custom_init(self, master, title=None):
    _original_init(self, master, title)
    try:
        self.wm_iconbitmap(resource_path("logo.ico"))
    except Exception:
        pass

simpledialog.Dialog.__init__ = _custom_init

def resource_path(filename):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.abspath("."), filename)

# Writable path for JSON (next to .exe or fallback)
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Expected correct/default location for UK folder
EXPECTED_ES_PARENT = os.path.abspath(os.path.expandvars(r"%APPDATA%\EuroScope"))

# Config JSON location/name
OPTIONS_PATH = os.path.join(BASE_DIR, "controller_pack_config.json")

# Resource path for bundled images
if getattr(sys, 'frozen', False):
    IMAGE_DIR = sys._MEIPASS
else:
    IMAGE_DIR = os.path.dirname(os.path.abspath(__file__))

def center_window(win):
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (width // 2)
    y = (win.winfo_screenheight() // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

def on_close():
    try:
        if tk._default_root:
            for w in tk._default_root.children.values():
                w.destroy()
            tk._default_root.destroy()
    except Exception:
        pass
    sys.exit()


def is_valid_cid(cid):
    return cid.isdigit() and 6 <= len(cid) <= 7

DEFAULT_FIELDS = {
    "name": "",
    "initials": "",
    "cid": "",
    "rating": "",
    "password": "",
    "cpdlc": "",
    "realistic_tags": "n",
    "realistic_conversion": "n",
    "coast_choice": "1",
    "land_choice": "1",
    "discord_presence": "n"
}

BASIC_FIELDS = ["name", "initials", "cid", "rating", "password", "cpdlc", "discord_presence"]
ADVANCED_FIELDS = ["realistic_tags", "realistic_conversion", "coast_choice", "land_choice", "asel_key"]

def load_previous_options():
    if os.path.exists(OPTIONS_PATH):
        with open(OPTIONS_PATH, "r") as f:
            return json.load(f)
    return {}

def save_options(options):
    with open(OPTIONS_PATH, "w") as f:
        json.dump(options, f, indent=2)

def ask_string(prompt, default=""):
    result = None
    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title("UK Controller Pack Configurator")
    dialog.resizable(False, False)
    dialog.protocol("WM_DELETE_WINDOW", on_close)

    ttk.Label(dialog, text=prompt).pack(padx=20, pady=(15, 5))
    entry_var = tk.StringVar(value=default)
    entry = ttk.Entry(dialog, textvariable=entry_var, width=40)
    entry.pack(padx=20, pady=5)

    def submit(event=None):
        nonlocal result
        result = entry_var.get()
        dialog.destroy()

    def cancel(event=None):
        dialog.destroy()

    button_frame = ttk.Frame(dialog)
    button_frame.pack(pady=15)
    ttk.Button(button_frame, text="OK", command=submit).pack(side="left", padx=5)
    ttk.Button(button_frame, text="Cancel", command=cancel).pack(side="left", padx=5)

    dialog.bind("<Return>", submit)
    dialog.bind("<Escape>", cancel)

    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    center_window(dialog)
    entry.focus_set()
    dialog.wait_window()

    return result

def ask_yesno(prompt, title="UK Controller Pack Configurator"):
    result = None
    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title(title)
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    dialog.resizable(False, False)

    # Frame for clean layout
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)

    # Message label
    ttk.Label(
        frame,
        text=prompt,
        wraplength=350,
        justify="left"
    ).pack(pady=(0, 15))

    def yes():
        nonlocal result
        result = True
        dialog.destroy()

    def no():
        nonlocal result
        result = False
        dialog.destroy()

    # Button frame
    button_frame = ttk.Frame(frame)
    button_frame.pack()
    ttk.Button(button_frame, text="Yes", command=yes).pack(side="left", padx=10)
    ttk.Button(button_frame, text="No", command=no).pack(side="left", padx=10)

    dialog.bind("<Return>", lambda e: yes())
    dialog.bind("<Escape>", lambda e: no())
    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    center_window(dialog)
    dialog.wait_window()

    return result

def ask_scan_code_key(prompt, title="Press a Key"):
    result = None

    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title(title)
    ttk.Label(dialog, text=prompt).pack(padx=20, pady=15)

    def capture_key_press(event):
        nonlocal result
        scan_code = windll.User32.MapVirtualKeyA(c_uint(event.keycode), c_uint(0))

        # Only set ASEL if the scan code mapping succeeded - if it fails (returns 0) it's likely due to an emulation issue on non-Windows.
        # TODO: Some way to notify the user that their customisation failed and they've retained the default bind?
        if scan_code != 0:
            result = str(scan_code << 16)

        dialog.destroy()

    def cancel(_=None):
        dialog.destroy()

    ttk.Button(dialog, text="Skip", command=cancel).pack(pady=10)

    dialog.bind("<Escape>", cancel)
    dialog.bind("<KeyPress>", capture_key_press)
    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    center_window(dialog)
    dialog.focus_force()
    dialog.wait_window()

    return result if result is not None else ""


def ask_dropdown(prompt, options_list, current=None):
    selected = tk.StringVar(value=current if current in options_list else options_list[0])
    def submit():
        dialog.quit()
        dialog.destroy()

    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title(prompt)
    ttk.Label(dialog, text=prompt).pack(pady=5)
    dropdown = ttk.Combobox(dialog, textvariable=selected, values=options_list, state="readonly")
    dropdown.pack(pady=5)
    ttk.Button(dialog, text="OK", command=submit).pack()
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    dialog.transient()
    dialog.grab_set()
    dialog.mainloop()
    center_window(dialog)
    return selected.get()

def ask_rating(current=None):
    ratings = ['OBS', 'S1', 'S2', 'S3', 'C1', 'C2 (not used)', 'C3', 'I1', 'I2 (not used)', 'I3', 'SUP', 'ADM']
    try:
        index = int(current)
        if index < 0 or index >= len(ratings):
            index = 0
    except (ValueError, TypeError):
        index = 0

    selected = tk.StringVar(value=ratings[index])

    def submit():
        dialog.quit()
        dialog.destroy()

    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.minsize(width=300, height=200)
    dialog.title("UK Controller Pack Configurator")
    ttk.Label(dialog, text="Select your rating:").pack(pady=5)
    dropdown = ttk.Combobox(dialog, textvariable=selected, values=ratings, state="readonly")
    dropdown.pack(pady=5)
    ttk.Button(dialog, text="OK", command=submit).pack()
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    center_window(dialog)
    dialog.mainloop()
    return str(ratings.index(selected.get()))

def ask_with_images(title, prompt, image_dict, current_key, descriptions_dict=None):
    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title("UK Controller Pack Configurator")
    ttk.Label(dialog, text=prompt, anchor="center", justify="center").pack(padx=20, pady=5)
    var = tk.StringVar(value=current_key if current_key in image_dict else "1")
    image_refs = []

    for key, image_path in image_dict.items():
        img = Image.open(image_path)
        photo = ImageTk.PhotoImage(img)
        image_refs.append(photo)

        frame = ttk.Frame(dialog)
        frame.pack(padx=20, pady=5, anchor="center")

        ttk.Radiobutton(frame, image=photo, variable=var, value=key).pack()
        desc = descriptions_dict.get(key, f"Option {key}") if descriptions_dict else f"Option {key}"
        ttk.Label(frame, text=desc, wraplength=320, justify="left").pack(padx=10)

    def submit():
        dialog.quit()
        dialog.destroy()

    ttk.Button(dialog, text="OK", command=submit).pack(pady=10)
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    center_window(dialog)
    dialog.mainloop()
    return var.get()


def prompt_for_field(key, current):
    descriptions = {
        "name": "Enter your name as used on VATSIM. Refer to Code of Conduct A4(b)",
        "initials": "Enter your 2–3 letter identifier for use when observing (e.g. LB or JSM)",
        "cid": "Enter your VATSIM CID (Certificate ID)",
        "rating": "Enter your current controller rating",
        "password": "Enter your VATSIM password",
        "cpdlc": "Enter your Hoppie CPDLC logon code (leave blank if you don't have one)",
        "realistic_tags": (
            "Apply realistic datablocks **only** for LAC and LTC (LTC, Heathrow, Gatwick, Essex):\n"
            "- Yes (default): Use realistic tags (no climb/descent arrows)\n"
            "- No: Add climb/descent arrows for improved clarity \n\n"
            "Note: STC, MPC and others will remain unaffected."
        ),
        "realistic_conversion": "Select Yes if you want to enable realistic code/callsign conversion (default).\nSelect No if not required (not recommended)",
        "coast_choice": "Select your preferred coastline colour",
        "land_choice": "Select your preferred land colour"
    }

    description = descriptions.get(key, f"Enter {key.replace('_', ' ')}")

    if key == "rating":
        return ask_rating(current)
    elif key == "coast_choice":
        return ask_with_images(
            "Select Coastline", descriptions.get(key),
            {
                "1": os.path.join(IMAGE_DIR, "coastline1.png"),
                "2": os.path.join(IMAGE_DIR, "coastline2.png"),
                "3": os.path.join(IMAGE_DIR, "coastline3.png")
            },
            current,
            {
                "1": "Blue (default): suitable for NOVA based systems (most APP units)",
                "2": "Grey: suitable for NODE based systems (STC,LTC,MPC)",
                "3": "Yellow: high contrast"
            }
        )
    elif key == "land_choice":
        return ask_with_images(
            "Select Land Color", descriptions.get(key),
            {
                "1": os.path.join(IMAGE_DIR, "land1.png"),
                "2": os.path.join(IMAGE_DIR, "land2.png"),
                "3": os.path.join(IMAGE_DIR, "land3.png")
            },
            current,
            {
                "1": "Mid grey (default)",
                "2": "Dark grey",
                "3": "Light Grey"
            }
        )
    
    elif key == "discord_presence":
        return "y" if ask_yesno("Would you like to enable DiscordEuroscope plugin which will show where you're controlling on Discord?") else "n"
    elif key == "asel_key":
        return ask_scan_code_key("Press the key you want to assign as your Aircraft Select (ASEL) key.\n\nThe ASEL key is an advanced keybind for selecting aircraft based on text input.\nPress \"Skip\" to retain the default (NUMPLUS) key.", "Press a key for ASEL")
    elif key in ["realistic_tags", "realistic_conversion"]:
        return "y" if ask_yesno(description) else "n"
    else:
        while True:
            response = ask_string(description, current)
            if response is None:
                sys.exit()
            if key == "cid" and not is_valid_cid(response):
                messagebox.showerror("Invalid CID", "CID must be a 6 or 7 digit number.")
                continue
            return response

def collect_user_input():
    root = tk.Tk()
    root.title("UK Controller Pack Configurator")
    root.iconbitmap(resource_path("logo.ico"))
    root.withdraw()
    tk._default_root = root
    previous_options = load_previous_options()
    options = {}

    if previous_options:
        use_previous = ask_yesno("Do you want to load your previous options?")
        if use_previous:
            options.update(previous_options)
            for key in BASIC_FIELDS:
                if key not in options:
                    options[key] = prompt_for_field(key, "")
        else:
            options = {}

    for key in BASIC_FIELDS:
        if key not in options or not options[key]:
            options[key] = prompt_for_field(key, "")


    save_options(options)
    return options


def patch_prf_file(file_path, name, initials, cid, rating, password):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return

    lines = [l for l in lines if not (
        l.startswith("LastSession\trealname") or
        l.startswith("LastSession\tcertificate") or
        l.startswith("LastSession\trating") or
        l.startswith("LastSession\tcallsign") or
        l.startswith("LastSession\tpassword")
    )]

    new_lines = [
        f"LastSession\trealname\t{name}\n",
        f"LastSession\tcertificate\t{cid}\n",
        f"LastSession\trating\t{rating}\n",
        f"LastSession\tcallsign\t{initials}_OBS\n",
        f"LastSession\tpassword\t{password}\n"
    ]

    lines += ["\n"] + new_lines

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        print(f"Failed to write to {file_path}: {e}")

def patch_prf_file_with_asel(file_path, asel_key):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return

    lines = [l for l in lines if not l.startswith("Settings\tAselKey")]

    new_lines = [
        f"Settings\tAselKey\t{asel_key}\n"
    ]

    lines += ["\n"] + new_lines

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
    except Exception as e:
        print(f"Failed to write to {file_path}: {e}")


def _resolve_discord_relpath(file_path: str) -> str:
    prf_dir = Path(file_path).parent

    for root in [prf_dir] + list(prf_dir.parents):
        plugin_dir = root / "Data" / "Plugin"

        if plugin_dir.exists():
            dll_abs = plugin_dir / "DiscordEuroscope.dll"
            rel = os.path.relpath(dll_abs, start=prf_dir).replace("/", "\\")

            if not rel.startswith("\\"):
                rel = "\\" + rel

            return rel

    return r"\..\Data\Plugin\DiscordEuroscope.dll"  # fallback


def patch_discord_plugin(file_path: str, state: str = "present"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return

    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    if state == "absent":
        new_lines = [l for l in lines if "DiscordEuroscope.dll" not in l]
        if new_lines != lines:
            with open(file_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(new_lines).rstrip("\n") + "\n")
        return

    if any("DiscordEuroscope.dll" in l for l in lines):
        return

    plugin_rx = re.compile(r"^Plugins\tPlugin(\d+)\t")
    last_idx = -1
    max_num = 0
    for i, line in enumerate(lines):
        m = plugin_rx.match(line)
        if m:
            last_idx = i
            try:
                max_num = max(max_num, int(m.group(1)))
            except ValueError:
                pass

    next_num = max_num + 1 if max_num else 1
    dll_rel = _resolve_discord_relpath(file_path)
    new_line = f"Plugins\tPlugin{next_num}\t{dll_rel}"

    if last_idx >= 0:
        insert_at = last_idx + 1
        lines.insert(insert_at, new_line)
    else:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(new_line)

    try:
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines).rstrip("\n") + "\n")
    except Exception as e:
        print(f"Failed to write {file_path}: {e}")


def patch_plugins_file(file_path, cpdlc):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith("vSMR Vatsim UK:cpdlc_password:"):
            new_lines.append(f"vSMR Vatsim UK:cpdlc_password:{cpdlc}\n")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        for i, line in enumerate(new_lines):
            if line.strip() == "END":
                new_lines.insert(i, f"vSMR Vatsim UK:cpdlc_password:{cpdlc}\n")
                break
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def patch_ese_file(file_path, initials):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    updated = content.replace("EXAMPLE", initials)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated)

def patch_profiles_file(file_path, cid):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    updated = content.replace("Submit feedback at vats.im/atcfb", f"Submit feedback at vatsim.uk/atcfb?cid={cid}")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated)

def apply_basic_configuration(name, initials, cid, rating, password, cpdlc, discord_presence):
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            path = os.path.join(root, file)
            if file.endswith(".prf"):
                patch_prf_file(path, name, initials, cid, rating, password)
                if discord_presence == "y":
                    patch_discord_plugin(path, state="present")
                else:
                    patch_discord_plugin(path, state="absent")
            elif file.endswith("Plugins.txt"):
                patch_plugins_file(path, cpdlc)
            elif file.endswith(".ese") and file.startswith("UK"):
                patch_ese_file(path, initials)
            elif file.endswith("Profiles.txt"):
                patch_profiles_file(path, cid)
    for plugin_path in [
        "Data/Plugin/TopSky_iTEC/TopSkyCPDLChoppieCode.txt",
        "Data/Plugin/TopSky_NERC/TopSkyCPDLChoppieCode.txt",
        "Data/Plugin/TopSky_NODE/TopSkyCPDLChoppieCode.txt",
        "Data/Plugin/TopSky_NOVA/TopSkyCPDLChoppieCode.txt"
    ]:
        os.makedirs(os.path.dirname(plugin_path), exist_ok=True)
        with open(plugin_path, "w") as f:
            f.write(cpdlc)

def apply_advanced_configuration(options):
    coast_colors = {"1": "9076039", "2": "5324604", "3": "32896"}
    land_colors = {"1": "3947580", "2": "1777181", "3": "8158332"}

    for root, _, files in os.walk("."):
        for file in files:
            path = os.path.join(root, file)

            # --- Handle .asr files for realistic tags (LAC/LTC only) ---
            if file.endswith(".asr"):
                rel_path = os.path.relpath(path, start="UK/Data/ASR").replace("\\", "/").lower()
                top_folder = rel_path.split("/")[0] if "/" in rel_path else ""

                is_lac = top_folder.startswith("ac_")
                is_ltc = top_folder in ["ltc", "heathrow", "gatwick", "essex"]
                should_patch = is_lac or is_ltc

                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                new_lines = []
                for line in lines:
                    if line.startswith("TAGFAMILY:") and ("NODE" in line or "AC" in line):
                        if should_patch:
                            if options["realistic_tags"] == "n" and "-Easy" not in line:
                                line = line.strip() + "-Easy\n"
                            elif options["realistic_tags"] == "y" and "-Easy" in line:
                                line = line.replace("-Easy", "")
                    new_lines.append(line)

                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

            # --- Handle UK_.sct coastline/land colour overrides ---
            if file.startswith("UK_") and file.endswith(".sct"):
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                new_lines = []
                for line in lines:
                    if line.startswith("#define coast "):
                        line = f"#define coast {coast_colors[options['coast_choice']]}\n"
                    elif line.startswith("#define land "):
                        line = f"#define land {land_colors[options['land_choice']]}\n"
                    new_lines.append(line)

                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

            # --- Handle correlation mode (skip *_SMR.txt files) ---
            if (
                file.endswith(".txt")
                and not file.endswith("_SMR.txt")
                and os.path.normpath("Data/Settings") in os.path.normpath(root)
            ):
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                new_lines = []
                modified = False
                for line in lines:
                    if line.strip().startswith("m_CorrelationMode:"):
                        value = "1" if options["realistic_conversion"] == "y" else "0"
                        line = f"m_CorrelationMode:{value}\n"
                        modified = True
                    new_lines.append(line)

                if modified:
                    with open(path, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)

            # --- Handle ASEL key (.prf files) ---
            if file.endswith(".prf"):
                patch_prf_file_with_asel(path, options["asel_key"])


def main():
    if not tk._default_root:
        root = tk.Tk()
        root.withdraw()
        tk._default_root = root
        apply_azure_theme(root)  # ✅ Theme applied only once

    lockfile = os.path.join(BASE_DIR, 'logondetails.lock')
    if os.path.exists(lockfile):
        messagebox.showerror("Already Running", "Configurator is already running.")
        sys.exit()

    actual_dir = os.path.abspath(BASE_DIR)

    if not actual_dir.startswith(EXPECTED_ES_PARENT + os.sep):
        proceed = ask_yesno(
            f"The configurator is not running from the expected folder:\n\n{EXPECTED_ES_PARENT}\\UK\n\n"
            "This may cause the Controller Pack to not function correctly. Refer to the EuroScope Setup Guide on the VATSIM UK Docs Site.\n\n"
            "Do you want to continue anyway?",
            title="Unexpected Location"
        )
        if not proceed:
            sys.exit()

    with open(lockfile, 'w') as f:
        f.write(str(os.getpid()))

    try:
        options = collect_user_input()
        apply_basic_configuration(
            name=options["name"],
            initials=options["initials"],
            cid=options["cid"],
            rating=options["rating"],
            password=options["password"],
            cpdlc=options["cpdlc"],
            discord_presence=options.get("discord_presence", "n")
        )

        if ask_yesno("Would you like to configure advanced options?"):
            for key in ADVANCED_FIELDS:
                options[key] = prompt_for_field(key, options.get(key, ""))
            apply_advanced_configuration(options)

        messagebox.showinfo("Complete", "Profile Configuration Complete")
        time.sleep(1.5)

    finally:
        if os.path.exists(lockfile):
            os.remove(lockfile)

if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            if tk._default_root:
                for w in tk._default_root.children.values():
                    w.destroy()
                tk._default_root.destroy()
        except Exception:
            pass
        if getattr(sys, 'frozen', False):
            os._exit(0)
        else:
            sys.exit(0)

