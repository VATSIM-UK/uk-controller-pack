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
from tkinter import filedialog
import re
import queue
from urllib3.util.retry import Retry
import webbrowser
import zipfile


# --- Configuration ---
REPO_OWNER = "VATSIM-UK"
REPO_NAME = "UK-Controller-Pack"
LOCAL_VERSION_FILE = "version.txt"
AERONAV_URL = "https://files.aero-nav.com/EGXX"
DATAFILES_DIR = os.path.join("UK", "Data", "Datafiles")
VSMR_DIR = os.path.join("UK", "Data", "Plugin", "vSMR")

# target basename -> accepted source basenames (lowercased) found inside the ZIP
GNG_REQUIRED = {
    "ICAO_Aircraft.txt": {"icao_aircraft.txt"},
    "ICAO_Airlines.txt": {"icao_airlines.txt"},
    "ICAO_Airports.txt": {"icao_airports.txt"},
    "airway.txt": {"airway.txt"},
    "icao.txt": {"icao.txt"},
    "isec.txt": {"isec.txt"},
}

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
        self.nav_button = ttk.Button(root, text="Update Navdata (GNG)…", command=self.start_gng_flow)
        self.nav_button.pack(pady=(0, 10))
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

    def start_gng_flow(self):
        self.nav_button.config(state="disabled")
        threading.Thread(target=self._run_gng_flow_safely, daemon=True).start()

    def _run_gng_flow_safely(self):
        try:
            self.gng_update_flow()
        finally:
            self.root.after(0, lambda: self.nav_button.config(state="normal"))

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
            allowed_methods={"GET", "HEAD", "OPTIONS"},
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
        changed = response.json().get("files", []) or []

        updated_files = []
        removed_files = []
        prf_modified = False

        for f in changed:
            path = f.get("filename", "")
            status = (f.get("status") or "").lower()
            prev = f.get("previous_filename")

            if not path.startswith("UK/"):
                continue

            if status in ("added", "modified", "renamed", "copied", "changed"):
                updated_files.append(path)

                if status == "renamed" and prev and prev.startswith("UK/"):
                    removed_files.append(prev)

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

                self.root.after(0, self.offer_gng_prompt)

                if prf_modified:
                    self.log("\n⚠️ One or more Profile Files were updated.")
                    self.root.after(0, self.prompt_run_configurator)

            except Exception as e:
                self.log(f"Update failed: {e}")
        else:
            self.log(f"{REPO_OWNER}/{REPO_NAME} is up to date (version {local_ver})")


    def gng_update_flow(self):
        self.log("GNG: Do you want to update navdata (requires VATSIM SSO login)?")
        if not messagebox.askyesno(
            "GNG Navdata",
            "Open Aeronav GNG download page?\n\nSign in, download the .zip, then select it."
        ):
            self.log("GNG: User cancelled.")
            return

        try:
            webbrowser.open(AERONAV_URL, new=1)
            self.log(f"GNG: Opened {AERONAV_URL}")
        except Exception as e:
            self.log(f"GNG: Failed to open browser: {e}")

        # Try to open directly in the user's Downloads folder
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        zip_path = filedialog.askopenfilename(
            initialdir=downloads_dir,
            title="Select the downloaded GNG navdata ZIP",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")]
        )

        if not zip_path:
            self.log("GNG: No file selected.")
            return

        try:
            self.import_gng_zip(zip_path)
        except Exception as e:
            self.log(f"GNG: Import failed: {e}")
            messagebox.showerror("GNG Import", f"Import failed:\n{e}")
            return

        messagebox.showinfo("GNG Import", "GNG navdata import complete.")
        self.log("GNG: Import complete.")

    def import_gng_zip(self, zip_path):
        self.log(f"GNG: Reading {zip_path}")
        os.makedirs(DATAFILES_DIR, exist_ok=True)
        os.makedirs(VSMR_DIR, exist_ok=True)
    
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            # build a case-insensitive lookup by basename
            lower_map = {}
            for n in names:
                base = os.path.basename(n).lower()
                if base:
                    lower_map.setdefault(base, []).append(n)
    
            extracted, missing = [], []
    
            for target_basename, accepted_set in GNG_REQUIRED.items():
                found_fullname = None
                for candidate in accepted_set:
                    paths = lower_map.get(candidate)
                    if paths:
                        found_fullname = sorted(paths, key=len)[0]  # prefer shortest path
                        break
    
                if not found_fullname:
                    missing.append(target_basename)
                    continue
    
                dst = os.path.join(DATAFILES_DIR, target_basename)
                with zf.open(found_fullname) as src, open(dst, "wb") as out:
                    out.write(src.read())
                self.log(f"GNG: {found_fullname} → {dst}")
                extracted.append(target_basename)
    
                # also copy airlines list to vSMR
                if target_basename.lower() == "icao_airlines.txt":
                    vsmr_dst = os.path.join(VSMR_DIR, "ICAO_Airlines.txt")
                    try:
                        with open(dst, "rb") as src, open(vsmr_dst, "wb") as out2:
                            out2.write(src.read())
                        self.log(f"GNG: Copied ICAO_Airlines.txt → {vSMR_DIR}")
                    except Exception as e:
                        self.log(f"GNG: Failed to copy ICAO_Airlines.txt to vSMR: {e}")
    
            if missing:
                self.log(f"GNG: Missing expected files: {', '.join(missing)}")
    
            # sanity: make sure it looks like a proper package
            if not any(x in extracted for x in {"ICAO_Airports.txt", "airway.txt", "icao.txt"}):
                raise RuntimeError("ZIP does not look like a valid GNG navdata package (core files missing).")

    def offer_gng_prompt(self):
        try:
            if messagebox.askyesno(
                "Navdata (GNG)",
                "Do you also want to update navdata now?\n\nThis will open the Aeronav GNG page so you can sign in and download the ZIP, then I'll import it."
            ):
                # run the threaded version so the UI stays responsive
                self.start_gng_flow()
        except Exception as e:
            self.log(f"GNG prompt failed: {e}")


# --- Launch GUI ---
if __name__ == "__main__":
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()
