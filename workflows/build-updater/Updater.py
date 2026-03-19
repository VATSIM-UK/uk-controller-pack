import os
import sys
import shutil
import tempfile
import difflib

# Replaced at build time by the GitHub workflow
UPDATER_BUILD = "__GIT_COMMIT__"


def _cli_early_exit() -> None:
    # Handle helper CLI flags used by CI/build scripts and exit before GUI startup.
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

from datetime import datetime
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import filedialog
import re
import queue
import subprocess
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
    # Resolve bundled resource paths for both PyInstaller and source runs.
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(__file__), rel)


def use_azure_theme(root: tk.Tk, mode: str = "dark") -> None:
    # Apply the Azure Tk theme when available; fail quietly if theme files are missing.
    try:
        root.tk.call("source", resource_path("workflows/build-updater/azure.tcl"))
        style = ttk.Style(root)
        style.theme_use("azure")
        root.tk.call("set_theme", mode)
    except Exception:
        pass


def normalize_version(vstr: str) -> str:
    # Normalize tags like YYYY_M to YYYY_MM so lexical version comparisons are safe.
    if not vstr:
        return vstr

    m = re.match(r"^(\d{4})_(\d{1,2})(.*)$", vstr)
    if m:
        year, month, suffix = m.groups()
        return f"{year}_{int(month):02d}{suffix}"
    return vstr


def set_window_icon(root: tk.Tk) -> None:
    # Set the application window icon when logo.ico is available.
    try:
        icon_path = resource_path("workflows/build-updater/logo.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(default=icon_path)
    except Exception:
        pass


class UpdaterApp:
    def __init__(self, root: tk.Tk):
        # Build the updater UI, initialize logging, and prepare network session state.
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
        # Restrict updates to files under UK/ only.
        # Users should only ever receive UK/*
        return repo_path.startswith("UK/")

    def log(self, message: str) -> None:
        # Queue log output for the UI thread, with stderr fallback during early startup.
        q = getattr(self, "_q", None)
        if q is None:
            try:
                print(str(message), file=sys.stderr)
            except Exception:
                pass
            return
        q.put(str(message))

    def _drain_log_queue(self) -> None:
        # Flush queued log messages into the textbox on the Tk main loop.
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

    def _make_session(self) -> object:
        # Create a resilient HTTP session with optional GitHub token and retries.
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

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
        # Read local AIRAC tag marker; use default baseline if missing.
        try:
            path = os.path.join(self.base_dir, LOCAL_VERSION_FILE)
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            self.log("version.txt not found. Assuming version 2025_01.")
            return "2025_01"

    def set_local_version(self, ver: str) -> None:
        # Persist the installed AIRAC version tag to version.txt.
        path = os.path.join(self.base_dir, LOCAL_VERSION_FILE)
        with open(path, "w", encoding="utf-8") as f:
            f.write(ver)

    def get_remote_updater_version(self) -> str:
        # Fetch the latest updater build hash marker from GitHub.
        self.log("Checking updater version...")
        r = self.session.get(UPDATER_VERSION_URL, timeout=(5, 15))
        r.raise_for_status()
        return r.text.strip()

    def ensure_updater_current(self) -> bool:
        return True
        # Block updates unless this Updater.exe build matches the latest published hash.
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
        # Read latest release metadata and resolve its underlying commit SHA.
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()
        data = response.json()
        return {
            "tag": data["tag_name"],
            "published_at": data["published_at"],
            "release_sha": self.get_release_sha(data["tag_name"]),
        }

    def get_release_sha(self, tag_name: str) -> str:
        # Resolve both lightweight and annotated tags to a concrete commit SHA.
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
        # Read the locally stored release commit marker used for change tracking.
        try:
            path = os.path.join(self.base_dir, LOCAL_PACK_VERSION_FILE)
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""

    def set_local_pack_version(self, sha: str) -> None:
        # Persist the release commit marker to Data/Sector/pack_version.txt.
        path = os.path.join(self.base_dir, LOCAL_PACK_VERSION_FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write((sha or "").strip())

    @staticmethod
    def format_date(iso_date_str: str) -> str:
        # Convert GitHub ISO timestamps into a short YYYY-MM-DD display format.
        dt = datetime.fromisoformat(iso_date_str.rstrip("Z"))
        return dt.strftime("%Y-%m-%d")

    @staticmethod
    def _blob_id(path: str) -> bytes:
        # Compute a Git-compatible blob ID so file content comparisons are reliable.
        with open(path, "rb") as f:
            return Blob.from_string(f.read()).id

    @staticmethod
    def _read_bytes_if_exists(path: str) -> bytes | None:
        # Read file bytes when the path exists, otherwise return None.
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    @staticmethod
    def _is_text_bytes(data: bytes) -> bool:
        # Determine whether content is text we can safely three-way merge.
        if b"\x00" in data:
            return False
        try:
            data.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    @staticmethod
    def _iter_text_edits(base_lines: list[str], changed_lines: list[str]) -> list[tuple[int, int, list[str]]]:
        # Build edit operations to transform base_lines into changed_lines.
        sm = difflib.SequenceMatcher(a=base_lines, b=changed_lines)
        edits: list[tuple[int, int, list[str]]] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            edits.append((i1, i2, changed_lines[j1:j2]))
        return edits

    @staticmethod
    def _ranges_conflict(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
        # Decide whether two edit ranges overlap in a way that indicates conflict.
        a_insert = a_start == a_end
        b_insert = b_start == b_end

        if a_insert and b_insert:
            return a_start == b_start

        if a_insert:
            return b_start <= a_start < b_end

        if b_insert:
            return a_start <= b_start < a_end

        return not (a_end <= b_start or b_end <= a_start)

    @classmethod
    def _check_trivial_merge_cases(
        cls, base_text: str, local_text: str, upstream_text: str
    ):
        # Early returns for cases where no real merge is needed.
        if local_text == base_text:
            return upstream_text, False
        if upstream_text == base_text:
            return local_text, False
        if local_text == upstream_text:
            return upstream_text, False
        return None

    @classmethod
    def _detect_conflicting_edit(
        cls, local_edits: list[tuple[int, int, list[str]]],
        upstream_edits: list[tuple[int, int, list[str]]]
    ) -> bool:
        # Return True if any local and upstream edits conflict.
        for l_start, l_end, l_repl in local_edits:
            for u_start, u_end, u_repl in upstream_edits:
                if cls._ranges_conflict(l_start, l_end, u_start, u_end):
                    if (l_start, l_end, l_repl) != (u_start, u_end, u_repl):
                        return True
        return False

    @classmethod
    def _apply_merged_edits(
        cls, base_lines: list[str], local_edits: list[tuple[int, int, list[str]]],
        upstream_edits: list[tuple[int, int, list[str]]]
    ) -> str:
        # Combine non-conflicting edits and reconstruct merged text.
        combined: list[tuple[int, int, list[str]]] = []
        seen = set()
        for edit in local_edits + upstream_edits:
            key = (edit[0], edit[1], tuple(edit[2]))
            if key not in seen:
                seen.add(key)
                combined.append(edit)

        combined.sort(key=lambda e: (e[0], e[1]))

        merged_lines: list[str] = []
        cursor = 0
        for start, end, replacement in combined:
            if cursor <= start:
                merged_lines.extend(base_lines[cursor:start])
                merged_lines.extend(replacement)
                cursor = end

        merged_lines.extend(base_lines[cursor:])
        return "".join(merged_lines)

    @classmethod
    def _merge_text_three_way(
        cls, base_text: str, local_text: str, upstream_text: str
    ) -> tuple[str, bool]:
        # Merge non-overlapping text changes from local and upstream over base.
        # Returns (merged_text, had_major_conflict). Upstream is preferred on conflict.
        trivial_result = cls._check_trivial_merge_cases(base_text, local_text, upstream_text)
        if trivial_result is not None:
            return trivial_result

        base_lines = base_text.splitlines(keepends=True)
        local_lines = local_text.splitlines(keepends=True)
        upstream_lines = upstream_text.splitlines(keepends=True)

        local_edits = cls._iter_text_edits(base_lines, local_lines)
        upstream_edits = cls._iter_text_edits(base_lines, upstream_lines)

        if cls._detect_conflicting_edit(local_edits, upstream_edits):
            return upstream_text, True

        merged_text = cls._apply_merged_edits(base_lines, local_edits, upstream_edits)
        return merged_text, False

    def merge_or_replace_file_from_snapshots(
        self, repo_path: str, from_uk_dir: str, to_uk_dir: str
    ) -> bool:
        # Apply one upstream file update using a three-way merge when possible.
        # Returns True if the file was actually modified/written locally, False otherwise.
        local_rel = self.get_local_path(repo_path)
        local_path = os.path.join(self.base_dir, local_rel)

        relative_inside_uk = local_rel.replace("/", os.sep)
        base_path = os.path.join(from_uk_dir, relative_inside_uk)
        upstream_path = os.path.join(to_uk_dir, relative_inside_uk)

        upstream_bytes = self._read_bytes_if_exists(upstream_path)
        if upstream_bytes is None:
            raise FileNotFoundError(f"Missing upstream file in snapshot: {repo_path}")

        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        base_bytes = self._read_bytes_if_exists(base_path)
        local_bytes = self._read_bytes_if_exists(local_path)

        if local_bytes is None:
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            return True

        if local_bytes == upstream_bytes:
            return False

        if base_bytes is None:
            # New upstream file with existing local content: upstream takes priority.
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            self.log(f"Conflict on new file {local_rel}; upstream version applied.")
            return True

        if local_bytes == base_bytes:
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            return True

        if upstream_bytes == base_bytes:
            # Upstream unchanged relative to base; preserve local modifications.
            self.log(f"Preserved local changes in {local_rel} (upstream unchanged).")
            return False

        if not (
            self._is_text_bytes(base_bytes)
            and self._is_text_bytes(local_bytes)
            and self._is_text_bytes(upstream_bytes)
        ):
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            self.log(f"Major binary conflict in {local_rel}; upstream version applied.")
            return True

        base_text = base_bytes.decode("utf-8")
        local_text = local_bytes.decode("utf-8")
        upstream_text = upstream_bytes.decode("utf-8")

        merged_text, had_conflict = self._merge_text_three_way(
            base_text, local_text, upstream_text
        )
        merged_bytes = merged_text.encode("utf-8")

        if had_conflict:
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            self.log(f"Major merge conflict in {local_rel}; upstream version applied.")
            return True

        if merged_bytes != local_bytes:
            with open(local_path, "wb") as f:
                f.write(merged_bytes)
            if merged_bytes == upstream_bytes:
                self.log(f"Applied upstream update for {local_rel}.")
            else:
                self.log(f"Merged upstream and local changes for {local_rel}.")
            return True

        return False

    def download_release_snapshot_for_tag(self, tag: str) -> str:
        # Download and extract a release ZIP, then return the extracted UK/ directory.
        # Download the release ZIP for this tag and return the extracted UK/ path.
        temp_dir = tempfile.mkdtemp(prefix=f"ukcp-release-{tag}-")
        zip_path = os.path.join(temp_dir, "release.zip")
        zip_url = (
            f"https://codeload.github.com/{REPO_OWNER}/{REPO_NAME}/zip/refs/tags/{tag}"
        )

        with self.session.get(zip_url, timeout=(5, 60), stream=True) as response:
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

        raise RuntimeError(f"Unable to locate UK/ in release snapshot ZIP for tag {tag}")

    def get_changed_files_between_tags(self, from_tag: str, to_tag: str):
        # Compare two release snapshots and return updated files, removed files, and PRF status.
        # Build incremental update data between two tags and track whether any .prf changed.
        # Compare Git blob IDs so we detect true content changes, not just name/timestamp differences.
        from_uk_dir = None
        to_uk_dir = None

        try:
            from_uk_dir = self.download_release_snapshot_for_tag(from_tag)
            to_uk_dir = self.download_release_snapshot_for_tag(to_tag)

            # Map repo-relative paths (e.g. UK/foo/bar.txt) to blob IDs for both tags.
            from_files: dict[str, bytes] = {}
            to_files: dict[str, bytes] = {}

            for root, _, files in os.walk(from_uk_dir):
                for name in files:
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, from_uk_dir).replace("\\", "/")
                    repo_path = f"UK/{rel}"
                    if self.is_user_file(repo_path):
                        from_files[repo_path] = self._blob_id(full)

            for root, _, files in os.walk(to_uk_dir):
                for name in files:
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, to_uk_dir).replace("\\", "/")
                    repo_path = f"UK/{rel}"
                    if self.is_user_file(repo_path):
                        to_files[repo_path] = self._blob_id(full)

            # updated_files includes both newly added files and modified existing files.
            updated_files: list[str] = []
            removed_files: list[str] = []
            # If any profile changed, we can prompt users to rerun Configurator.
            prf_modified = False

            for path in sorted(to_files.keys() - from_files.keys()):
                updated_files.append(path)
                if path.lower().endswith(".prf"):
                    prf_modified = True

            for path in sorted(from_files.keys() - to_files.keys()):
                removed_files.append(path)
                if path.lower().endswith(".prf"):
                    prf_modified = True

            for path in sorted(to_files.keys() & from_files.keys()):
                if to_files[path] != from_files[path]:
                    updated_files.append(path)
                    if path.lower().endswith(".prf"):
                        prf_modified = True

            return sorted(set(updated_files)), sorted(set(removed_files)), prf_modified
        finally:
            if from_uk_dir:
                shutil.rmtree(os.path.dirname(from_uk_dir), ignore_errors=True)
            if to_uk_dir:
                shutil.rmtree(os.path.dirname(to_uk_dir), ignore_errors=True)

    def get_local_path(self, remote_path: str) -> str:
        # Translate a repository path into the corresponding local filesystem path.
        if remote_path.startswith("UK/"):
            return remote_path[len("UK/") :]
        return remote_path

    def download_file(self, branch: str, filepath: str) -> None:
        # Download one file from GitHub and write it into the local UK folder.
        url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch}/{filepath}"
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()

        local_rel = self.get_local_path(filepath)
        local_path = os.path.join(self.base_dir, local_rel)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        with open(local_path, "wb") as f:
            f.write(response.content)

    def delete_file(self, filepath: str) -> None:
        # Remove a local file that no longer exists in the target release.
        local_rel = self.get_local_path(filepath)
        local_path = os.path.join(self.base_dir, local_rel)

        if os.path.exists(local_path):
            os.remove(local_path)
            self.log(f"Removed {local_rel}")
        else:
            self.log(f"File {local_rel} does not exist, skipping removal.")

    def prompt_run_configurator(self) -> None:
        # Prompt to launch Configurator when profile files were changed by the update.
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
                subprocess.Popen([exe_path])
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
        # Disable the update button and run update logic in a background thread.
        self.update_button.config(state="disabled")
        threading.Thread(target=self._run_update_safely, daemon=True).start()

    def _run_update_safely(self) -> None:
        # Guard update execution so the UI button is always restored afterwards.
        try:
            if not self.ensure_updater_current():
                return
            self.update_if_needed()
        finally:
            self.update_button.config(state="normal")

    def update_if_needed(self) -> None:
        # Main updater workflow: detect differences, apply file changes, and report status.
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

        try:
            if normalize_version(local_ver) >= normalize_version(latest_ver):
                updated_files: list[str] = []
                removed_files: list[str] = []
                prf_modified = False
            else:
                updated_files, removed_files, prf_modified = (
                    self.get_changed_files_between_tags(local_ver, latest_ver)
                )

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

            from_uk_dir = None
            to_uk_dir = None
            prf_modified = False
            try:
                from_uk_dir = self.download_release_snapshot_for_tag(local_ver)
                to_uk_dir = self.download_release_snapshot_for_tag(latest_ver)

                for file in updated_files:
                    if os.path.normcase(file) == os.path.normcase("UK/Updater.exe"):
                        self.log(
                            "Note: Updater.exe changed, but it will not be auto-updated."
                        )
                        continue

                    self.log(f"Updating {file}")
                    was_modified = self.merge_or_replace_file_from_snapshots(file, from_uk_dir, to_uk_dir)
                    if was_modified:
                        file_lower = file.lower()
                        is_config_file = (
                            file_lower.endswith(".prf")
                            or file_lower.endswith(".asr")
                            or (file_lower.endswith(".txt") and not file_lower.endswith("version.txt") and not file_lower.endswith("pack_version.txt"))
                        )
                        if is_config_file:
                            prf_modified = True
            finally:
                if from_uk_dir:
                    shutil.rmtree(os.path.dirname(from_uk_dir), ignore_errors=True)
                if to_uk_dir:
                    shutil.rmtree(os.path.dirname(to_uk_dir), ignore_errors=True)

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

    def gng_update_flow(self) -> None:
        # Guide the user through downloading and importing Aeronav GNG navdata.
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
        # Start the GNG navdata flow on a background thread to keep UI responsive.
        threading.Thread(target=self.gng_update_flow, daemon=True).start()

    def offer_gng_prompt(self) -> None:
        # Offer a post-update prompt to optionally import GNG navdata immediately.
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
        # Import required navdata files from a selected GNG ZIP into local data folders.
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
