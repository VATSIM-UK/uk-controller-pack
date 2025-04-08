import os
import json
import sys
from datetime import datetime
import argparse


def main():
    parser = argparse.ArgumentParser(description="Update vATIS serials")
    parser.add_argument('--changed-files-list', required=True,
                        help='List of changed files between commits')
    args = parser.parse_args()
    with open(args.changed_files_list, 'r')as f:
        changes_files = f.read().splitlines()

    vatis_files = [f[7:] for f in changes_files if f.startswith(
        "_vATIS/") and f.endswith(".json")]

    update_files(vatis_files)


def update_files(files: list[str]) -> None:

    input_dir = os.path.abspath('_vATIS')

    # Get the list of filenames from the command line arguments

    print(f"Updating\n{'\n'.join(files)}\n")

    # If no filenames are provided, update all JSON files in the input directory
    if not files:
        files = [f for f in os.listdir(
            input_dir) if f.endswith('.json')]

    for filename in files:
        if filename.endswith('.json'):
            name = os.path.splitext(filename)[0]
            input_filepath = os.path.join(input_dir, filename)

            if not os.path.exists(input_filepath):
                print(f"File {input_filepath} does not exist.")
                continue

            with open(input_filepath, 'r') as file:
                data = json.load(file)

            current_serial = str(data.get("updateSerial", "1970010100"))

            current_date = current_serial[:8]
            current_serial_number = int(current_serial[8:])

            today_date = datetime.now().strftime("%Y%m%d")

            print(f"{current_date=}")
            print(f"{today_date=}")
            print(f"{current_serial_number=}")

            if current_date == today_date:
                new_serial_number = current_serial_number + 1
            else:
                new_serial_number = 1

            if new_serial_number > 99:  # should never be an issue
                print("There have been too many updates today. The script will now exit")
                sys.exit(1)

            update_serial = int(f"{today_date}{new_serial_number:02d}")

            update_url = f"https://raw.githubusercontent.com/VATSIM-UK/uk-controller-pack/refs/heads/main/_vATIS/{name}.json"

            data["updateUrl"] = update_url
            data["updateSerial"] = update_serial

            with open(input_filepath, 'w') as file:
                json.dump(data, file, indent=2)

            print(f"Updated {filename} with new serial {update_serial}")


if __name__ == "__main__":
    main()
