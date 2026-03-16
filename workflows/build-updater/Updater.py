import os
import sys
import shutil
import tempfile

# Replaced at build time by the GitHub workflow
UPDATER_BUILD = "__GIT_COMMIT__"


def _cli_early_exit() -> None:
    args = sys.argv[1:]

    if "--write-build" in args:
        i = args.index("--write-build")
        if i + 1 >= len(args):
            raise SystemExit(2)

        out_path = args[i + 1]
        build = (UPDATER_BUILD or "").strip()

        try:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(build)
            raise SystemExit(0)  # only after success
        except Exception:
            raise SystemExit(1)  # make CI fail properly

    if "--print-build" in args:
        print((UPDATER_BUILD or "").strip())
        raise SystemExit(0)


_cli_early_exit()

import requests
from requests.adapters import HTTPAdapter
from datetime import datetime
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

from dulwich.objects import Blob

REPO_OWNER = "VATSIM-UK"
REPO_NAME = "UK-Controller-Pack"

LOCAL_VERSION_FILE = "version.txt"  # AIRAC pack tag, e.g. 2025_10
LOCAL_PACK_VERSION_FILE = os.path.join("Data", "Sector", "pack_version.txt")

# Remote reference for latest updater build ID (short hash)
UPDATER_VERSION_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/.data/updater_version.txt"

UPDATER_DOWNLOAD_URL = (
    f"https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/main/UK/Updater.exe"
)

AERONAV_URL = "https://files.aero-nav.com/EGXX"
DATAFILES_DIR = os.path.join("Data", "Datafiles")
VSMR_DIR = os.path.join("Data", "Plugin", "vSMR")

GNG_REQUIRED = {
    "ICAO_Aircraft.txt": {"icao_aircraft.txt"},
    "ICAO_Airlines.txt": {"icao_airlines.txt"},
    "ICAO_Airports.txt": {"icao_airports.txt"},
    "airway.txt": {"airway.txt"},
    "icao.txt": {"icao.txt"},
    "isec.txt": {"isec.txt"},
}


def resource_path(rel: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(__file__), rel)


def use_azure_theme(root: tk.Tk, mode: str = "dark") -> None:
    try:
        root.tk.call("source", resource_path("workflows/build-updater/azure.tcl"))
        style = ttk.Style(root)
        style.theme_use("azure")
        root.tk.call("set_theme", mode)
    except Exception:
        pass


def normalize_version(vstr: str) -> str:
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

        self._q: queue.Queue[str] = queue.Queue()
        self.root.after(50, self._drain_log_queue)

        self.root.title("UK Controller Pack Updater")
        self.root.geometry("720x520")
        self.root.resizable(True, True)

        self.log(f"Updater path:  {os.path.abspath(sys.argv[0])}")
        local_hash = (UPDATER_BUILD or "").strip()
        self.log(f"Updater build (local): {local_hash!r}")

        set_window_icon(self.root)
        use_azure_theme(self.root, mode="dark")

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

        self.session = self._make_session()

        # This is the user's UK folder (Updater.exe lives here)
        self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    def is_user_file(self, repo_path: str) -> bool:
        # Users should only ever receive UK/*
        return repo_path.startswith("UK/")

    def log(self, message: str) -> None:
        q = getattr(self, "_q", None)
        if q is None:
            try:
                print(str(message), file=sys.stderr)
            except Exception:
                pass
            return
        q.put(str(message))

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

        # Token is optional; it helps with rate limiting on GitHub API calls
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

    def get_local_version(self) -> str:
        try:
            path = os.path.join(self.base_dir, LOCAL_VERSION_FILE)
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            self.log("version.txt not found. Assuming version 2025_01.")
            return "2025_01"

    def set_local_version(self, ver: str) -> None:
        path = os.path.join(self.base_dir, LOCAL_VERSION_FILE)
        with open(path, "w", encoding="utf-8") as f:
            f.write(ver)

    def get_remote_updater_version(self) -> str:
        self.log("Checking updater version...")
        r = self.session.get(UPDATER_VERSION_URL, timeout=(5, 15))
        r.raise_for_status()
        return r.text.strip()

    def ensure_updater_current(self) -> bool:
        local_hash = (UPDATER_BUILD or "").strip()

        # If the workflow didn't inject the hash, we can't verify anything
        if not local_hash:
            messagebox.showerror(
                "Updater update required",
                "This updater build ID is missing.\n\n"
                "Please download the latest Updater.exe from GitHub and replace your copy.\n\n"
                "No changes have been made.",
            )
            try:
                webbrowser.open(UPDATER_DOWNLOAD_URL, new=1)
                self.log("Opened Updater.exe download page on GitHub.")
            except Exception as e:
                self.log(f"Failed to open download page: {e}")
            return False

        try:
            remote_hash = self.get_remote_updater_version()
            self.log(f"Updater build (remote): {remote_hash!r}")
        except Exception as e:
            self.log(f"Updater version check failed: {e}")
            messagebox.showerror(
                "Updater version check failed",
                "Unable to verify the updater version right now.\n\n"
                "This may be a network issue or GitHub rate limiting.\n"
                "No changes have been made.\n\n"
                "Please try again later.",
            )
            return False

        if not remote_hash:
            messagebox.showerror(
                "Updater version check failed",
                "GitHub returned an empty updater_version.txt.\n\n"
                "No changes have been made.\n\n"
                "Please try again later.",
            )
            return False

        if remote_hash != local_hash:
            self.log(f"Updater out of date (local {local_hash}, latest {remote_hash}).")
            messagebox.showinfo(
                "Updater update required",
                "A newer updater is required before any files can be updated.\n\n"
                f"Current updater build: {local_hash}\n"
                f"Latest updater build:  {remote_hash}\n\n"
                "Please download the latest Updater.exe from GitHub and replace your copy.\n\n"
                "No changes have been made.",
            )
            try:
                webbrowser.open(UPDATER_DOWNLOAD_URL, new=1)
                self.log("Opened Updater.exe download page on GitHub.")
            except Exception as e:
                self.log(f"Failed to open download page: {e}")
            return False

        self.log("Updater.exe is current.")
        return True

    def get_latest_version(self) -> dict:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()
        data = response.json()
        return {
            "tag": data["tag_name"],
            "published_at": data["published_at"],
            "zipball_url": data["zipball_url"],
            "release_sha": self.get_release_sha(data["tag_name"]),
        }

    def get_release_sha(self, tag_name: str) -> str:
        ref_url = (
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/ref/tags/{tag_name}"
        )
        response = self.session.get(ref_url, timeout=(5, 30))
        response.raise_for_status()
        ref_data = response.json()

        obj = ref_data.get("object", {})
        obj_type = obj.get("type")
        obj_sha = (obj.get("sha") or "").strip()

        if obj_type == "commit":
            return obj_sha

        if obj_type == "tag" and obj_sha:
            tag_url = (
                f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/tags/{obj_sha}"
            )
            tag_response = self.session.get(tag_url, timeout=(5, 30))
            tag_response.raise_for_status()
            tag_data = tag_response.json()
            commit_sha = (tag_data.get("object", {}).get("sha") or "").strip()
            if commit_sha:
                return commit_sha

        raise RuntimeError(f"Unable to resolve release SHA for tag {tag_name}")

    def get_local_pack_version(self) -> str:
        try:
            path = os.path.join(self.base_dir, LOCAL_PACK_VERSION_FILE)
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def set_local_pack_version(self, sha: str) -> None:
        path = os.path.join(self.base_dir, LOCAL_PACK_VERSION_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write((sha or "").strip())

    @staticmethod
    def format_date(iso_date_str: str) -> str:
        dt = datetime.fromisoformat(iso_date_str.rstrip("Z"))
        return dt.strftime("%Y-%m-%d")

    @staticmethod
    def _blob_id(path: str) -> bytes:
        with open(path, "rb") as f:
            return Blob.from_string(f.read()).id

    def get_changed_files(self, release_uk_dir: str):
        updated_files: list[str] = []
        removed_files: list[str] = []  # local-only files are left untouched
        prf_modified = False

        release_rel_paths: set[str] = set()

        for root, _, files in os.walk(release_uk_dir):
            for name in files:
                release_path = os.path.join(root, name)
                rel = os.path.relpath(release_path, release_uk_dir).replace("\\", "/")
                release_rel_paths.add(rel)

                repo_path = f"UK/{rel}"
                local_path = os.path.join(self.base_dir, rel)

                if not os.path.exists(local_path):
                    updated_files.append(repo_path)
                    if repo_path.lower().endswith(".prf"):
                        prf_modified = True
                    continue

                if self._blob_id(release_path) != self._blob_id(local_path):
                    updated_files.append(repo_path)
                    if repo_path.lower().endswith(".prf"):
                        prf_modified = True

        local_only_files: list[str] = []
        for root, _, files in os.walk(self.base_dir):
            for name in files:
                local_path = os.path.join(root, name)
                rel = os.path.relpath(local_path, self.base_dir).replace("\\", "/")
                if rel not in release_rel_paths:
                    local_only_files.append(rel)

        if local_only_files:
            self.log(
                "Found local-only files not present in the latest release; "
                "they were left untouched: "
                + ", ".join(sorted(local_only_files)[:10])
                + ("..." if len(local_only_files) > 10 else "")
            )

        return sorted(set(updated_files)), removed_files, prf_modified

    def download_release_snapshot(self, zipball_url: str) -> str:
        temp_dir = tempfile.mkdtemp(prefix="ukcp-release-")
        zip_path = os.path.join(temp_dir, "release.zip")

        with self.session.get(zipball_url, timeout=(5, 60), stream=True) as response:
            response.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(temp_dir)

        for entry in os.listdir(temp_dir):
            candidate = os.path.join(temp_dir, entry, "UK")
            if os.path.isdir(candidate):
                return candidate

        raise RuntimeError("Unable to locate UK/ in release snapshot ZIP")

    def get_local_path(self, remote_path: str) -> str:
        if remote_path.startswith("UK/"):
            return remote_path[len("UK/") :]
        return remote_path

    def download_file(self, branch: str, filepath: str) -> None:
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

    def prompt_run_configurator(self) -> None:
        msg = (
            "One or more profile (.prf) files were updated.\n\n"
            "It is recommended that you run the UK Controller Pack Configurator "
            "to review or apply any new settings.\n\n"
            "Do you want to run Configurator.exe now?"
        )

        if not messagebox.askyesno("Profile Files Updated", msg):
            return

        exe_path = os.path.join(self.base_dir, "Configurator.exe")

        if os.path.isfile(exe_path):
            try:
                os.startfile(exe_path)
                self.log("Launched Configurator.exe")
            except Exception as e:
                self.log(f"Failed to launch Configurator.exe: {e}")
                messagebox.showerror(
                    "Configurator launch failed",
                    f"Could not start Configurator.exe.\n\n{e}",
                )
        else:
            self.log("Configurator.exe not found.")
            messagebox.showwarning(
                "Configurator not found",
                "Configurator.exe was not found in your UK folder.\n\n"
                "If you have it elsewhere, please run it manually.",
            )

    def start_update(self) -> None:
        self.update_button.config(state="disabled")
        threading.Thread(target=self._run_update_safely, daemon=True).start()

    def _run_update_safely(self) -> None:
        try:
            if not self.ensure_updater_current():
                return
            self.update_if_needed()
        finally:
            self.update_button.config(state="normal")

    def update_if_needed(self) -> None:
        self.log("Checking for updates...")
        local_ver = self.get_local_version()
        local_pack_sha = self.get_local_pack_version()

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
        release_sha = (latest.get("release_sha") or "").strip()

        self.log(
            f"Checking local files against {REPO_OWNER}/{REPO_NAME} {latest_ver} "
            f"(local version marker: {local_ver})"
        )
        self.log(
            "Pack version SHA "
            f"(local): {local_pack_sha or '<missing>'} | "
            f"(release): {release_sha or '<unknown>'}"
        )

        release_uk_dir = None
        try:
            release_uk_dir = self.download_release_snapshot(latest["zipball_url"])
            updated_files, removed_files, prf_modified = self.get_changed_files(
                release_uk_dir
            )

            updated_files = [p for p in updated_files if self.is_user_file(p)]
            removed_files = [p for p in removed_files if self.is_user_file(p)]

            if not updated_files and not removed_files:
                self.log(
                    f"{REPO_OWNER}/{REPO_NAME} is up to date with latest release "
                    f"{latest_ver}"
                )
                if normalize_version(latest_ver) > normalize_version(local_ver):
                    self.set_local_version(latest_ver)
                if release_sha and local_pack_sha != release_sha:
                    self.set_local_pack_version(release_sha)
                    self.log("Updated local pack_version.txt SHA marker.")
                return

            for file in updated_files:
                if os.path.normcase(file) == os.path.normcase("UK/Updater.exe"):
                    self.log(
                        "Note: Updater.exe changed, but it will not be auto-updated."
                    )
                    continue

                self.log(f"Updating {file}")
                self.download_file(latest_ver, file)

            for file in removed_files:
                self.delete_file(file)

            self.set_local_version(latest_ver)
            if release_sha:
                self.set_local_pack_version(release_sha)
            self.log(
                f"\nUpdate complete: now on {REPO_OWNER}/{REPO_NAME} version "
                f"{latest_ver} (released {release_date})"
            )

            self.root.after(0, self.offer_gng_prompt)

            if prf_modified:
                self.log("\n⚠️ One or more Profile Files were updated.")
                self.root.after(0, self.prompt_run_configurator)

        except Exception as e:
            self.log(f"Update failed: {e}")
        finally:
            if release_uk_dir:
                shutil.rmtree(os.path.dirname(release_uk_dir), ignore_errors=True)

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

        if not messagebox.askyesno(
            "GNG Navdata",
            "Have you downloaded the GNG ZIP already?\n\nClick Yes to select it now.",
        ):
            self.log("GNG: User not ready to select ZIP yet.")
            return

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
                        self.log(f"GNG: Failed to copy ICAO_Airlines.txt to vSMR: {e}")

            if missing:
                self.log(f"GNG: Missing expected files: {', '.join(missing)}")

            if not any(
                x in extracted for x in {"ICAO_Airports.txt", "airway.txt", "icao.txt"}
            ):
                raise RuntimeError(
                    "ZIP does not look like a valid GNG navdata package."
                )

        self.log("GNG: Navdata import complete.")

        try:
            if messagebox.askyesno(
                "GNG Navdata", "Delete the downloaded ZIP file now?"
            ):
                os.remove(zip_path)
                self.log("GNG: Deleted ZIP after import.")
        except Exception as e:
            self.log(f"GNG: Failed to delete ZIP: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = UpdaterApp(root)
    root.mainloop()
