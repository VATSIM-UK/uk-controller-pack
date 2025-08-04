import requests
from datetime import datetime
import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import re

# --- Configuration ---
REPO_OWNER = "VATSIM-UK"
REPO_NAME = "UK-Controller-Pack"
LOCAL_VERSION_FILE = "version.txt"


def normalize_version(vstr):
    """
    Normalize version strings like '2022_09a' or '2023_10' into comparable tuples.
    E.g., '2022_09a' -> (2022, 9, 'a')
          '2023_10'  -> (2023, 10)
    """
    parts = re.split(r'[_\-.]', vstr)
    norm = []
    for part in parts:
        if part.isdigit():
            norm.append(int(part))
        else:
            norm.append(part.lower())
    return tuple(norm)


class UpdaterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("UK Controller Pack Updater")
        self.root.geometry("600x400")
        self.root.resizable(False, False)

        self.log_box = ScrolledText(root, width=80, height=20, state='disabled', bg="#f4f4f4")
        self.log_box.pack(padx=10, pady=10)

        self.update_button = tk.Button(root, text="Check for Updates", command=self.start_update)
        self.update_button.pack(pady=(0, 10))

    def log(self, message):
        self.log_box.config(state='normal')
        self.log_box.insert(tk.END, message + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state='disabled')

    def start_update(self):
        threading.Thread(target=self.update_if_needed, daemon=True).start()

    def get_local_version(self):
        try:
            with open(LOCAL_VERSION_FILE) as f:
                return f.read().strip()
        except FileNotFoundError:
            self.log("version.txt not found. Assuming version 2021_01.")
            return "2021_01"

    def set_local_version(self, ver):
        with open(LOCAL_VERSION_FILE, "w") as f:
            f.write(ver)

    def get_latest_version(self):
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return {
            "tag": data["tag_name"],
            "published_at": data["published_at"]
        }

    def format_date(self, iso_date_str):
        dt = datetime.fromisoformat(iso_date_str.rstrip("Z"))
        return dt.strftime("%Y-%m-%d")

    def get_changed_files(self, base_tag, head_tag):
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/compare/{base_tag}...{head_tag}"
        response = requests.get(url)
        response.raise_for_status()
        changed = response.json()["files"]

        updated_files = []
        removed_files = []
        prf_modified = False

        for f in changed:
            path = f["filename"]
            status = f["status"]

            if not path.startswith("UK/"):
                continue

            if status in ("added", "modified"):
                updated_files.append(path)
                if path.endswith(".prf"):
                    prf_modified = True
            elif status == "removed":
                removed_files.append(path)

        return updated_files, removed_files, prf_modified

    def download_file(self, branch, filepath):
        url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch}/{filepath}"
        response = requests.get(url)
        response.raise_for_status()
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(response.content)

    def delete_file(self, filepath):
        if os.path.exists(filepath):
            os.remove(filepath)
            self.log(f"Deleted {filepath}")

    def prompt_run_configurator(self):
        result = messagebox.askyesno(
            title="Profile Files Updated",
            message="One or more Profile Files were updated or added.\n\nDo you want to run the profile configuration tool now?"
        )
        if result:
            configurator_path = os.path.join(os.path.dirname(sys.argv[0]), "Configurator.exe")
            if os.path.exists(configurator_path):
                try:
                    subprocess.Popen([configurator_path], shell=True)
                    self.log("Configurator.exe launched.")
                except Exception as e:
                    self.log(f"Failed to launch Configurator.exe: {e}")
            else:
                self.log("Configurator.exe not found in script directory.")

    def update_if_needed(self):
        self.log("Checking for updates...")
        local_ver = self.get_local_version()

        try:
            latest = self.get_latest_version()
        except Exception as e:
            self.log(f"Error checking latest version: {e}")
            return

        latest_ver = latest["tag"]
        release_date = self.format_date(latest["published_at"])

        # Use normalized version comparison instead of packaging.version
        if normalize_version(latest_ver) > normalize_version(local_ver):
            self.log(f"Updating {REPO_OWNER}/{REPO_NAME} to {latest_ver} (previously using {local_ver})")

            try:
                updated_files, removed_files, prf_modified = self.get_changed_files(local_ver, latest_ver)

                for file in updated_files:
                    self.log(f"Updating {file}")
                    self.download_file(latest_ver, file)

                for file in removed_files:
                    self.delete_file(file)

                self.set_local_version(latest_ver)
                self.log(f"\nUpdate complete: now on {REPO_OWNER}/{REPO_NAME} version {latest_ver} (released {release_date})")

                if prf_modified:
                    self.log("\n⚠️ One or more Profile Files were updated.")
                    self.prompt_run_configurator()

            except Exception as e:
                self.log(f"Update failed: {e}")
        else:
            self.log(f"{REPO_OWNER}/{REPO_NAME} is up to date (version {local_ver})")


# --- Launch GUI ---
if __name__ == "__main__":
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()
