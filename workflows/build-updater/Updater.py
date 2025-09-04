import requests
from requests.adapters import HTTPAdapter
from datetime import datetime
import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter import ttk
import re
import queue
from urllib3.util.retry import Retry

# --- Configuration ---
REPO_OWNER = "VATSIM-UK"
REPO_NAME = "UK-Controller-Pack"
LOCAL_VERSION_FILE = "version.txt"

# --- Helper Functions ---

def resource_path(rel):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(__file__), rel)

def use_azure_theme(root, mode='dark'):
    try:
        root.tk.call('source', resource_path('workflows/build-updater/azure.tcl'))
        style = ttk.Style(root)
        style.theme_use('azure')
        root.tk.call('set_theme', mode)
    except Exception:
        pass

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
        self.root.geometry("720x460")
        self.root.resizable(True, True)

        self.log_box = ScrolledText(root, width=80, height=20, state='disabled', bg="#f4f4f4")
        self.log_box.pack(padx=10, pady=10)

        self.update_button = ttk.Button(root, text="Check for Updates", command=self.start_update)
        self.update_button.pack(pady=(0, 10))
        self._q = queue.Queue()
        self.root.after(50, self._drain_log_queue)
        self.session = self._make_session()
        use_azure_theme(self.root, mode="dark")

    def log(self, message):
        self._q.put(str(message))

    def _drain_log_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                self.log_box.config(state='normal')
                self.log_box.insert(tk.END, msg + "\n")
                self.log_box.see(tk.END)
                self.log_box.config(state='disabled')
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._drain_log_queue)

    def start_update(self):
        self.update_button.config(state="disabled")
        threading.Thread(target=self._run_update_safely, daemon=True).start()

    def _run_update_safely(self):
        try:
            self.update_if_needed()
        finally:
            self.root.after(0, lambda: self.update_button.config(state="normal"))

    def _make_session(self):
        s = requests.Session()
        s.headers.update({"User-Agent": "UK-Controller-Pack-Updater/1.0"})
        token = os.getenv("GITHUB_TOKEN")
        if token:
            s.headers.update({"Authorization": f"token {token}"})
        retry = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=None
        )
        s.mount("https://", HTTPAdapter(max_retries=retry))
        return s

    def get_local_version(self):
        try:
            with open(LOCAL_VERSION_FILE) as f:
                return f.read().strip()
        except FileNotFoundError:
            self.log("version.txt not found. Assuming version 2025_01.")
            return "2025_01"

    def set_local_version(self, ver):
        with open(LOCAL_VERSION_FILE, "w") as f:
            f.write(ver)

    def get_latest_version(self):
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        response = self.session.get(url, timeout=(5, 30))
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
        response = self.session.get(url, timeout=(5, 30))
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

    def get_local_path(self, remote_path):
        # Strip leading 'UK/' since we're already inside the UK/ directory
        if remote_path.startswith("UK/"):
            return remote_path[len("UK/"):]
        return remote_path

    def download_file(self, branch, filepath):
        url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch}/{filepath}"
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()

        local_path = self.get_local_path(filepath)
        dir_path = os.path.dirname(local_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(response.content)
        self.log(f"Downloaded {filepath} → {local_path}")

    def delete_file(self, filepath):
        local_path = self.get_local_path(filepath)
        if os.path.exists(local_path):
            os.remove(local_path)
            self.log(f"Deleted {local_path}")

    def prompt_run_configurator(self):
        result = messagebox.askyesno(
            title="Profile Files Updated",
            message="One or more Profile Files were updated or added.\n\nDo you want to run the profile configuration tool now?"
        )
        if result:
            configurator_path = os.path.join(os.path.dirname(sys.argv[0]), "Configurator.exe")
            if os.path.exists(configurator_path):
                try:
                    subprocess.Popen([configurator_path], shell=False)
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
            if "403" in str(e):
                self.log("You may have exceeded the GitHub API rate limit. Consider setting a GITHUB_TOKEN environment variable.")
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
                    self.root.after(0, self.prompt_run_configurator)

            except Exception as e:
                self.log(f"Update failed: {e}")
        else:
            self.log(f"{REPO_OWNER}/{REPO_NAME} is up to date (version {local_ver})")


# --- Launch GUI ---
if __name__ == "__main__":
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()
