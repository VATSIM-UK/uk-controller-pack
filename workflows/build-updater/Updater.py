import requests
from requests.adapters import HTTPAdapter
from datetime import datetime
import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox
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

LOCAL_VERSION_FILE = "version.txt"            # AIRAC pack version, e.g. 2025_11
UPDATER_VERSION_FILE = "updater_version.txt"  # commit hash of Updater.exe build

# Remote location of updater_version.txt (adjust branch if needed)
UPDATER_VERSION_URL = (
    f"https://raw.githubusercontent.com/VATSIM-UK/uk-controller-pack/refs/heads/main/UK/updater_version.txt"
)

AERONAV_URL = "https://files.aero-nav.com/EGXX"
DATAFILES_DIR = os.path.join("Data", "Datafiles")
VSMR_DIR = os.path.join("Data", "Plugin", "vSMR")

# map target basenames to acceptable source basenames in the GNG ZIP (case-insensitive)
GNG_REQUIRED = {
    "ICAO_Aircraft.txt": {"icao_aircraft.txt"},
    "ICAO_Airlines.txt": {"icao_airlines.txt"},
    "ICAO_Airports.txt": {"icao_airports.txt"},
    "airway.txt": {"airway.txt"},
    "icao.txt": {"icao.txt"},
    "isec.txt": {"isec.txt"},
}


# --- Helper Functions ---


def resource_path(rel: str) -> str:
    """
    Helper to find resources when frozen with PyInstaller.
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(__file__), rel)


def use_azure_theme(root: tk.Tk, mode: str = "dark") -> None:
    """
    Try to apply the Azure ttk theme. Fails silently if not available.
    """
    try:
        root.tk.call("source", resource_path("workflows/build-updater/azure.tcl"))
        style = ttk.Style(root)
        style.theme_use("azure")
        root.tk.call("set_theme", mode)
    except Exception:
        # Fall back to default theme
        pass


def normalize_version(vstr: str) -> str:
    """
    Normalizes a version string so lexical comparison works for YYYY_M / YYYY_MM.

    Example:
      '2025_9'   -> '2025_09'
      '2025_11a' -> '2025_11a' (suffix preserved)
    """
    if not vstr:
        return vstr

    m = re.match(r"^(\d{4})_(\d{1,2})(.*)$", vstr)
    if m:
        year, month, suffix = m.groups()
        return f"{year}_{int(month):02d}{suffix}"
    return vstr


def set_window_icon(root: tk.Tk) -> None:
    try:
        icon_path = resource_path("workflows/build-updater/logo.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(default=icon_path)
    except Exception:
        pass


class UpdaterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("UK Controller Pack Updater")
        self.root.geometry("720x520")
        self.root.resizable(True, True)
        set_window_icon(self.root)

        # Try Azure dark theme
        use_azure_theme(self.root, mode="dark")

        # --- UI layout ---
        title_frame = ttk.Frame(root)
        title_frame.pack(padx=10, pady=(10, 0), fill="x")
        ttk.Label(
            title_frame,
            text="UK Controller Pack Updater",
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left")

        container = ttk.Frame(root)
        container.pack(padx=10, pady=10, fill="both", expand=True)

        self.log_box = tk.Text(
            container,
            wrap="word",
            state="disabled",
            relief="flat",
            highlightthickness=0,
        )
        self.log_box.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(container, orient="vertical", command=self.log_box.yview)
        sb.pack(side="right", fill="y")
        self.log_box.configure(yscrollcommand=sb.set)

        self.update_button = ttk.Button(
            root, text="Check for Updates", command=self.start_update
        )
        self.update_button.pack(pady=(0, 10))

        self.nav_button = ttk.Button(
            root, text="Update Navdata (GNG)…", command=self.start_gng_flow
        )
        self.nav_button.pack(pady=(0, 10))

        # logging queue so threads can safely log to the Text widget
        self._q: queue.Queue[str] = queue.Queue()
        self.root.after(50, self._drain_log_queue)

        self.session = self._make_session()

        # base_dir is the folder containing Updater.exe (UK\)
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # --- Logging and threading helpers ---

    def log(self, message: str) -> None:
        self._q.put(str(message))

    def _drain_log_queue(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                self.log_box.config(state="normal")
                self.log_box.insert(tk.END, msg + "\n")
                self.log_box.see(tk.END)
                self.log_box.config(state="disabled")
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._drain_log_queue)

    def _make_session(self) -> requests.Session:
        s = requests.Session()
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
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

    # --- Version handling ---

    def get_local_version(self) -> str:
        """
        Read UK/version.txt in the same folder as Updater.exe.
        """
        try:
            path = os.path.join(self.base_dir, LOCAL_VERSION_FILE)
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            self.log("version.txt not found. Assuming version 2025_01.")
            return "2025_01"

    def set_local_version(self, ver: str) -> None:
        """
        Write UK/version.txt.
        """
        path = os.path.join(self.base_dir, LOCAL_VERSION_FILE)
        with open(path, "w", encoding="utf-8") as f:
            f.write(ver)

    def get_local_updater_version(self) -> str:
        """
        Read UK/updater_version.txt in the same folder as Updater.exe.
        Returns a commit hash or 'unknown' if not present/invalid.
        """
        try:
            path = os.path.join(self.base_dir, UPDATER_VERSION_FILE)
            with open(path, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if text:
                    return text
                self.log("updater_version.txt is empty – treating updater version as unknown.")
                return "unknown"
        except FileNotFoundError:
            self.log("updater_version.txt not found – treating updater version as unknown.")
            return "unknown"
        except Exception as e:
            self.log(f"Error reading updater_version.txt: {e}")
            return "unknown"

    def get_remote_updater_version(self) -> str:
        """
        Fetch the latest updater_version.txt from GitHub.
        """
        self.log("Checking if a newer Updater.exe is available...")
        r = self.session.get(UPDATER_VERSION_URL, timeout=(5, 15))
        r.raise_for_status()
        return r.text.strip()

    def ensure_updater_current(self) -> bool:
        """
        Hard gate: the updater must match the repo's updater_version.txt
        before any pack files are updated.
        Returns True if current, False if updates must NOT proceed.
        """
        local_hash = self.get_local_updater_version()

        if not local_hash or local_hash == "unknown":
            msg = (
                "This copy of the updater cannot determine its own build version.\n\n"
                "To ensure updates are applied safely, please download the latest "
                "Updater.exe from GitHub and replace your existing UK\\Updater.exe.\n\n"
                "No changes have been made."
            )
            messagebox.showerror("Updater version unknown", msg)
            try:
                webbrowser.open(
                    f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest", new=1
                )
                self.log("Opened releases page so you can download the latest Updater.exe.")
            except Exception as e:
                self.log(f"Failed to open releases page: {e}")
            return False

        try:
            remote_hash = self.get_remote_updater_version()
        except Exception as e:
            self.log(f"Updater version check failed: {e}")
            msg = (
                "The updater could not verify its own version against GitHub.\n\n"
                "This may be due to a network error or GitHub rate limiting. "
                "To avoid applying updates with a potentially outdated updater, "
                "no changes will be made.\n\n"
                "Please try again later."
            )
            messagebox.showerror("Updater version check failed", msg)
            return False

        if not remote_hash:
            msg = (
                "GitHub returned an empty updater_version.txt.\n\n"
                "To be safe, no updates will be applied. Please try again later."
            )
            messagebox.showerror("Updater version check failed", msg)
            return False

        if remote_hash != local_hash:
            self.log(
                f"Updater.exe out of date (local {local_hash}, latest {remote_hash})."
            )
            msg = (
                "A newer version of the updater (Updater.exe) is available.\n\n"
                f"Current updater build: {local_hash}\n"
                f"Latest updater build:  {remote_hash}\n\n"
                "The updater must be updated before it can modify any other files.\n\n"
                "1. Click OK to open the releases page.\n"
                "2. Download the latest Updater.exe.\n"
                "3. Replace your existing UK\\Updater.exe.\n"
                "4. Run the new Updater.exe and try again."
            )
            messagebox.showinfo("Updater.exe is out of date", msg)
            try:
                webbrowser.open(
                    f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest", new=1
                )
                self.log("Opened releases page so you can download the latest Updater.exe.")
            except Exception as e:
                self.log(f"Failed to open releases page: {e}")
            return False

        # All good
        self.log("Updater.exe is current.")
        return True

    # --- GitHub API / pack updates ---

    def get_latest_version(self) -> dict:
        """
        Get latest release tag and publish timestamp from GitHub.
        """
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()
        data = response.json()
        return {"tag": data["tag_name"], "published_at": data["published_at"]}

    @staticmethod
    def format_date(iso_date_str: str) -> str:
        dt = datetime.fromisoformat(iso_date_str.rstrip("Z"))
        return dt.strftime("%Y-%m-%d")

    def get_changed_files(self, base_tag: str, head_tag: str):
        """
        Compare two tags and return (updated_files, removed_files, prf_modified).
        """
        url = (
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/compare/"
            f"{base_tag}...{head_tag}"
        )
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()
        changed = response.json().get("files", []) or []

        updated_files: list[str] = []
        removed_files: list[str] = []
        prf_modified = False

        for f in changed:
            filename = f.get("filename", "")
            status = f.get("status", "")

            if status in ("added", "modified"):
                updated_files.append(filename)
            elif status == "removed":
                removed_files.append(filename)

            if filename.lower().endswith(".prf") and status in ("added", "modified"):
                prf_modified = True

        return updated_files, removed_files, prf_modified

    def get_local_path(self, remote_path: str) -> str:
        """
        Map a repo path like 'UK/Config/foo.txt' to local path relative to base_dir.
        """
        if remote_path.startswith("UK/"):
            return remote_path[len("UK/") :]
        return remote_path

    def download_file(self, branch: str, filepath: str) -> None:
        """
        Download one file from GitHub at given branch/tag and write it to local UK folder.
        """
        url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch}/{filepath}"
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()

        local_rel = self.get_local_path(filepath)
        local_path = os.path.join(self.base_dir, local_rel)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(response.content)

    def delete_file(self, filepath: str) -> None:
        local_rel = self.get_local_path(filepath)
        local_path = os.path.join(self.base_dir, local_rel)

        if os.path.exists(local_path):
            os.remove(local_path)
            self.log(f"Removed {local_rel}")
        else:
            self.log(f"File {local_rel} does not exist, skipping removal.")

    # --- Profiles / Configurator ---

    def prompt_run_configurator(self) -> None:
        """
        Prompt the user to run the Configurator after profile (.prf) changes.
        """
        msg = (
            "One or more profile (.prf) files were updated.\n\n"
            "It is strongly recommended that you run the UK Controller Pack Configurator "
            "to review / apply any new settings.\n\n"
            "Do you want to open the Configurator folder now?"
        )

        if messagebox.askyesno("Profile Files Updated", msg):
            configurator_path = os.path.join(self.base_dir, "Configurator")
            if os.path.isdir(configurator_path):
                try:
                    os.startfile(configurator_path)
                except Exception as e:
                    self.log(f"Failed to open Configurator folder: {e}")
            else:
                self.log("Configurator folder not found.")

    # --- Main update logic ---

    def start_update(self) -> None:
        self.update_button.config(state="disabled")
        threading.Thread(target=self._run_update_safely, daemon=True).start()

    def _run_update_safely(self) -> None:
        try:
            # HARD GATE: updater must be current before touching any pack files
            if not self.ensure_updater_current():
                return
            self.update_if_needed()
        finally:
            self.update_button.config(state="normal")

    def update_if_needed(self) -> None:
        """
        Check GitHub for a newer pack version and apply changes.
        Updater.exe itself is never auto-updated.
        """
        self.log("Checking for updates...")
        local_ver = self.get_local_version()

        try:
            latest = self.get_latest_version()
        except Exception as e:
            self.log(f"Error checking latest version: {e}")
            if "403" in str(e):
                self.log(
                    "You may have exceeded the GitHub API rate limit. "
                    "Consider setting a GITHUB_TOKEN environment variable."
                )
            return

        latest_ver = latest["tag"]
        release_date = self.format_date(latest["published_at"])

        if normalize_version(latest_ver) > normalize_version(local_ver):
            self.log(
                f"Updating {REPO_OWNER}/{REPO_NAME} to {latest_ver} "
                f"(previously using {local_ver})"
            )

            try:
                updated_files, removed_files, prf_modified = self.get_changed_files(
                    local_ver, latest_ver
                )

                # Update all changed files except Updater.exe
                for file in updated_files:
                    if os.path.normcase(file) == os.path.normcase("UK/Updater.exe"):
                        self.log(
                            "Note: Updater.exe has changed in this release but will not "
                            "be auto-updated."
                        )
                        continue

                    self.log(f"Updating {file}")
                    self.download_file(latest_ver, file)

                # Delete removed files
                for file in removed_files:
                    self.delete_file(file)

                # Bump local version
                self.set_local_version(latest_ver)
                self.log(
                    f"\nUpdate complete: now on {REPO_OWNER}/{REPO_NAME} version "
                    f"{latest_ver} (released {release_date})"
                )

                # Offer optional GNG/navdata update
                self.root.after(0, self.offer_gng_prompt)

                # Prompt user to run Configurator if .prf was touched
                if prf_modified:
                    self.log("\n⚠️ One or more Profile Files were updated.")
                    self.root.after(0, self.prompt_run_configurator)

            except Exception as e:
                self.log(f"Update failed: {e}")
        else:
            self.log(f"{REPO_OWNER}/{REPO_NAME} is up to date (version {local_ver})")

    # --- GNG / navdata update ---

    def gng_update_flow(self) -> None:
        self.log("GNG: Do you want to update navdata (requires VATSIM SSO login)?")
        if not messagebox.askyesno(
            "GNG Navdata",
            "Open Aeronav GNG download page?\n\n"
            "Sign in, download the .zip, then select it.",
        ):
            self.log("GNG: User cancelled.")
            return

        try:
            webbrowser.open(AERONAV_URL, new=1)
            self.log(f"GNG: Opened {AERONAV_URL}")
        except Exception as e:
            self.log(f"GNG: Failed to open browser: {e}")

        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")

        zip_path = filedialog.askopenfilename(
            initialdir=downloads_dir,
            title="Select the downloaded GNG navdata ZIP",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")],
        )

        if not zip_path:
            self.log("GNG: No file selected.")
            return

        try:
            self.import_gng_zip(zip_path)
        except Exception as e:
            self.log(f"GNG: Import failed: {e}")

    def start_gng_flow(self) -> None:
        threading.Thread(target=self.gng_update_flow, daemon=True).start()

    def offer_gng_prompt(self) -> None:
        try:
            if messagebox.askyesno(
                "Navdata (GNG)",
                "Do you also want to update navdata now?\n\n"
                "This requires logging into Aeronav with VATSIM SSO and downloading a GNG ZIP.\n"
                "I will then ask you to pick that ZIP and import it.",
            ):
                self.start_gng_flow()
        except Exception as e:
            self.log(f"GNG prompt failed: {e}")

    def import_gng_zip(self, zip_path: str) -> None:
        self.log(f"GNG: Importing {zip_path}")
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"GNG ZIP not found: {zip_path}")

        target_dir = os.path.join(self.base_dir, DATAFILES_DIR)
        os.makedirs(target_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()

            # Build a case-insensitive lookup by basename
            lower_map: dict[str, list[str]] = {}
            for n in names:
                base = os.path.basename(n).lower()
                if base:
                    lower_map.setdefault(base, []).append(n)

            extracted: list[str] = []
            missing: list[str] = []

            for target_basename, accepted_set in GNG_REQUIRED.items():
                found_fullname = None
                for candidate in accepted_set:
                    paths = lower_map.get(candidate)
                    if paths:
                        # Prefer the shortest path if multiple exist
                        found_fullname = sorted(paths, key=len)[0]
                        break

                if found_fullname:
                    src = found_fullname
                    dst = os.path.join(target_dir, target_basename)
                    self.log(f"GNG: Extracting {src} → {dst}")
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    with z.open(src, "r") as in_f, open(dst, "wb") as out_f:
                        out_f.write(in_f.read())
                    extracted.append(target_basename)
                else:
                    missing.append(target_basename)

            # Copy ICAO_Airlines.txt to vSMR, if present
            if "ICAO_Airlines.txt" in extracted:
                vsmr_dir = os.path.join(self.base_dir, VSMR_DIR)
                if os.path.isdir(vsmr_dir):
                    main_dst = os.path.join(target_dir, "ICAO_Airlines.txt")
                    vsmr_dst = os.path.join(vsmr_dir, "ICAO_Airlines.txt")
                    try:
                        with open(main_dst, "rb") as src_f, open(
                            vsmr_dst, "wb"
                        ) as out2:
                            out2.write(src_f.read())
                        self.log(f"GNG: Copied ICAO_Airlines.txt → {VSMR_DIR}")
                    except Exception as e:
                        self.log(
                            f"GNG: Failed to copy ICAO_Airlines.txt to vSMR: {e}"
                        )

            if missing:
                self.log(f"GNG: Missing expected files: {', '.join(missing)}")

            # Simple sanity check
            if not any(
                x in extracted for x in {"ICAO_Airports.txt", "airway.txt", "icao.txt"}
            ):
                raise RuntimeError(
                    "ZIP does not look like a valid GNG navdata package (core files missing)."
                )


# --- Launch GUI ---
if __name__ == "__main__":
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()
