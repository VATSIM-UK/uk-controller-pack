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
import json
import re
import queue
import subprocess
import webbrowser
import zipfile

from dulwich.objects import Blob

REPO_OWNER = "VATSIM-UK"
REPO_NAME = "UK-Controller-Pack"

LOCAL_VERSION_FILE = "version.txt"  # AIRAC pack tag, e.g. 2025_10
SECTOR_DIR = os.path.join("Data", "Sector")
LOCAL_PACK_VERSION_FILE = os.path.join(SECTOR_DIR, "pack_version.txt")

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

CONFIGURATOR_OPTIONS_FILE = "controller_pack_config.json"

# Profile entries owned by the user, not the pack. These are written by the
# Configurator or by EuroScope itself, so a local value always wins over the
# release even when the release changed the same entry.
PRF_USER_OWNED_KEYS = {
    ("LastSession", "realname"),
    ("LastSession", "certificate"),
    ("LastSession", "password"),
    ("LastSession", "rating"),
    ("LastSession", "callsign"),
    ("Settings", "AselKey"),
}

# Plugin settings owned by the user. Keyed by (plugin name, setting name).
PLUGIN_SETTING_USER_OWNED_KEYS = {
    ("vSMR Vatsim UK", "cpdlc_password"),
}

# Files whose entire content is a user secret written by the Configurator.
USER_OWNED_FILENAMES = {"topskycpdlchoppiecode.txt"}

# Sector files are renamed every AIRAC cycle (UK_2026_07.sct -> UK_2026_08.sct),
# so they always arrive as new files with no common ancestor to merge against.
# Group 1 is the AIRAC tag, group 2 the extension.
AIRAC_FILE_RE = re.compile(r"^UK_(\d{4}_\d{1,2})\.(sct|ese|rwy)$", re.IGNORECASE)

# Only these two carry user customisations worth moving to the new cycle.
AIRAC_CUSTOMISED_SUFFIXES = (".sct", ".ese")

# Colour overrides the Configurator writes into the sector file.
SCT_CARRIED_DEFINES = ("coast", "land")

# ASR keys holding the sector file EuroScope had loaded when the display was
# saved. Unlike the rest of an ASR these are derived state, not user settings,
# so they are repointed at the current cycle instead of being merged.
ASR_SECTOR_KEYS = ("SECTORFILE", "SECTORTITLE")

# Per-display view and tag settings. Each appears at most once in an ASR, so a
# customised value can be protected from a same-line clash with the release.
ASR_USER_OWNED_KEYS = frozenset({
    "SHOWC",
    "SHOWSB",
    "BELOW",
    "ABOVE",
    "LEADER",
    "SHOWLEADER",
    "TURNLEADER",
    "HISTORY_DOTS",
    "SIMULATION_MODE",
    "DISABLEPANNING",
    "DISABLEZOOMING",
    "DisplayRotation",
    "TAGFAMILY",
    "WINDOWAREA",
})

# Placeholder the pack ships in .ese files; the Configurator swaps in the
# controller's initials.
ESE_INITIALS_PLACEHOLDER = "EXAMPLE"


def resource_path(rel: str) -> str:
    # Resolve bundled resource paths for both PyInstaller and source runs.
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
    # Normalize tags like YYYY_M to YYYY_MM so lexical version comparisons are safe.
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
        # Compute a Git-compatible blob ID so file content comparisons are reliable.
        with open(path, "rb") as f:
            return Blob.from_string(f.read()).id

    @staticmethod
    def _read_bytes_if_exists(path: str) -> bytes | None:
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
        sm = difflib.SequenceMatcher(a=base_lines, b=changed_lines)
        edits: list[tuple[int, int, list[str]]] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            edits.append((i1, i2, changed_lines[j1:j2]))
        return edits

    @staticmethod
    def _ranges_conflict(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
        a_insert = a_start == a_end
        b_insert = b_start == b_end

        if a_insert and b_insert:
            # Two insertions at the same point are kept side by side rather than
            # treated as a conflict: the common case is the Configurator appending
            # user settings at end of file while the release appends its own.
            return False

        if a_insert:
            return b_start <= a_start < b_end

        if b_insert:
            return a_start <= b_start < a_end

        return not (a_end <= b_start or b_end <= a_start)

    @classmethod
    def _check_trivial_merge_cases(
        cls, base_text: str, local_text: str, upstream_text: str
    ):
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
        # Upstream is listed first so that where both sides insert at the same
        # point, the release content leads and the user's additions follow.
        combined: list[tuple[int, int, list[str]]] = []
        seen = set()
        for edit in upstream_edits + local_edits:
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

    # ---- Text normalisation -------------------------------------------------

    @staticmethod
    def _decode_text(data: bytes) -> tuple[str, str, bool]:
        # Line endings drift between the release ZIP and a local install, and that
        # difference must not be mistaken for a user customisation.
        had_bom = data.startswith(b"\xef\xbb\xbf")
        if had_bom:
            data = data[3:]

        text = data.decode("utf-8")
        crlf = text.count("\r\n")
        lone_lf = text.count("\n") - crlf
        eol = "\r\n" if crlf > lone_lf else "\n"

        return text.replace("\r\n", "\n").replace("\r", "\n"), eol, had_bom

    @staticmethod
    def _encode_text(text: str, eol: str, had_bom: bool) -> bytes:
        if eol != "\n":
            text = text.replace("\n", eol)
        data = text.encode("utf-8")
        return b"\xef\xbb\xbf" + data if had_bom else data

    # ---- Keyed record merging -----------------------------------------------

    @staticmethod
    def _three_way_map(
        base: dict, local: dict, upstream: dict, user_owned: set
    ) -> tuple[dict, list]:
        # Upstream ordering is preserved; user-added keys are appended after it.
        merged: dict = {}
        conflicts: list = []

        for key, upstream_value in upstream.items():
            if key in user_owned and key in local:
                merged[key] = local[key]
                continue

            base_value = base.get(key)

            if key not in local:
                # Honour a deletion only when upstream left the entry alone.
                if key in base and upstream_value == base_value:
                    continue
                merged[key] = upstream_value
                continue

            local_value = local[key]

            if local_value == upstream_value or local_value == base_value:
                merged[key] = upstream_value
            elif key in base and upstream_value == base_value:
                merged[key] = local_value
            else:
                merged[key] = upstream_value
                conflicts.append(key)

        for key, local_value in local.items():
            if key not in upstream and key not in base:
                merged[key] = local_value

        return merged, conflicts

    # ---- EuroScope profile (.prf) merging -----------------------------------

    _PRF_PLUGIN_RE = re.compile(r"^Plugin(\d+)(Display(\d+))?$")

    @classmethod
    def _parse_prf(cls, text: str) -> tuple[dict, list, bool]:
        # Plugins are held separately because their keys carry a positional index
        # that both the pack and the Configurator renumber independently.
        # The final flag reports repeated entries, which this parse cannot represent.
        entries: dict[tuple[str, str], str] = {}
        plugins: list[tuple[str, list[str]]] = []
        by_index: dict[int, tuple[str, dict[int, str]]] = {}
        duplicated = False

        for line in text.split("\n"):
            if not line.strip():
                continue

            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue

            section, key, value = parts

            if section == "Plugins":
                m = cls._PRF_PLUGIN_RE.match(key)
                if m:
                    index = int(m.group(1))
                    slot = by_index.setdefault(index, ("", {}))
                    if m.group(2) is None:
                        by_index[index] = (value, slot[1])
                    else:
                        slot[1][int(m.group(3))] = value
                    continue

            if (section, key) in entries:
                duplicated = True
            entries[(section, key)] = value

        for index in sorted(by_index):
            path, displays = by_index[index]
            if path:
                plugins.append((path, [displays[i] for i in sorted(displays)]))

        return entries, plugins, duplicated

    @staticmethod
    def _plugin_key(path: str) -> str:
        # Identify a plugin by its DLL path, ignoring separator and case drift.
        return path.replace("/", "\\").lstrip("\\").lower()

    @classmethod
    def _merge_prf_plugins(cls, base: list, local: list, upstream: list) -> list:
        # Take the release plugin list and append any plugin the user added.
        #
        # A plugin missing locally is never treated as a deliberate removal: a
        # stale or hand-edited profile looks identical to a removal, and dropping
        # a pack plugin breaks the position far more than an unwanted extra one.
        # The only removal the Configurator performs is DiscordEuroscope, which
        # the pack never ships, so it is handled by the user-addition rule below.
        base_keys = {cls._plugin_key(path) for path, _ in base}
        upstream_keys = {cls._plugin_key(path) for path, _ in upstream}

        merged = list(upstream)
        merged.extend(
            entry
            for entry in local
            if cls._plugin_key(entry[0]) not in upstream_keys
            and cls._plugin_key(entry[0]) not in base_keys
        )

        return merged

    @classmethod
    def _render_prf(
        cls, upstream_text: str, entries: dict, plugins: list
    ) -> str:
        # Rebuild a profile, keeping the release's line order and appending extras.
        lines: list[str] = []
        emitted: set[tuple[str, str]] = set()
        plugins_written = False

        def write_plugins() -> None:
            for index, (path, displays) in enumerate(plugins):
                lines.append(f"Plugins\tPlugin{index}\t{path}")
                for display_index, display in enumerate(displays):
                    lines.append(
                        f"Plugins\tPlugin{index}Display{display_index}\t{display}"
                    )

        for line in upstream_text.split("\n"):
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue

            section, key, _ = parts

            if section == "Plugins" and cls._PRF_PLUGIN_RE.match(key):
                if not plugins_written:
                    plugins_written = True
                    write_plugins()
                continue

            if (section, key) in emitted or (section, key) not in entries:
                continue

            emitted.add((section, key))
            lines.append(f"{section}\t{key}\t{entries[(section, key)]}")

        if not plugins_written:
            write_plugins()

        extras = [k for k in entries if k not in emitted]
        if extras:
            lines.append("")
            lines.extend(f"{s}\t{k}\t{entries[(s, k)]}" for s, k in extras)

        return "\n".join(lines) + "\n"

    @classmethod
    def _merge_prf(
        cls, base_text: str, local_text: str, upstream_text: str
    ) -> tuple[str, list] | None:
        # Returns None when any input repeats an entry, so the caller can fall
        # back to a line merge rather than silently dropping records.
        base_entries, base_plugins, base_dup = cls._parse_prf(base_text)
        local_entries, local_plugins, local_dup = cls._parse_prf(local_text)
        upstream_entries, upstream_plugins, upstream_dup = cls._parse_prf(upstream_text)

        if base_dup or local_dup or upstream_dup:
            return None

        merged_entries, conflicts = cls._three_way_map(
            base_entries, local_entries, upstream_entries, PRF_USER_OWNED_KEYS
        )
        merged_plugins = cls._merge_prf_plugins(
            base_plugins, local_plugins, upstream_plugins
        )

        return cls._render_prf(upstream_text, merged_entries, merged_plugins), conflicts

    # ---- EuroScope settings file merging ------------------------------------

    @staticmethod
    def _parse_delimited(text: str, fields: int) -> tuple[dict, list, bool]:
        # Parse `a:b:value` style settings into keys of the first `fields` parts.
        # Lines without enough separators (PLUGINS/END markers) are kept verbatim.
        # The final flag reports repeated keys, which this parse cannot represent.
        entries: dict[tuple[str, ...], str] = {}
        markers: list[str] = []
        duplicated = False

        for line in text.split("\n"):
            if not line.strip():
                continue

            parts = line.split(":", fields)
            if len(parts) <= fields:
                markers.append(line)
                continue

            key = tuple(parts[:fields])
            if key in entries:
                duplicated = True
            entries[key] = parts[fields]

        return entries, markers, duplicated

    @classmethod
    def _merge_delimited(
        cls,
        base_text: str,
        local_text: str,
        upstream_text: str,
        fields: int,
        user_owned: set,
    ) -> tuple[str, list] | None:
        # Returns None when any input repeats a key, since collapsing repeated
        # records (tag definitions, symbology rows) would silently lose data.
        base_entries, _, base_dup = cls._parse_delimited(base_text, fields)
        local_entries, _, local_dup = cls._parse_delimited(local_text, fields)
        upstream_entries, upstream_markers, upstream_dup = cls._parse_delimited(
            upstream_text, fields
        )

        if base_dup or local_dup or upstream_dup:
            return None

        merged, conflicts = cls._three_way_map(
            base_entries, local_entries, upstream_entries, user_owned
        )

        # Local-only entries the user added must sit before any trailing END marker.
        trailing = upstream_markers[-1] if upstream_markers else None
        lines: list[str] = []
        emitted: set[tuple[str, ...]] = set()

        for line in upstream_text.split("\n"):
            if not line.strip():
                continue

            parts = line.split(":", fields)
            if len(parts) <= fields:
                if line == trailing:
                    lines.extend(
                        ":".join(k) + ":" + merged[k] for k in merged if k not in emitted
                    )
                    emitted.update(merged)
                lines.append(line)
                continue

            key = tuple(parts[:fields])
            if key in emitted or key not in merged:
                continue

            emitted.add(key)
            lines.append(":".join(key) + ":" + merged[key])

        lines.extend(":".join(k) + ":" + merged[k] for k in merged if k not in emitted)

        return "\n".join(lines) + "\n", conflicts

    # ---- Merge strategy selection -------------------------------------------

    @classmethod
    def _structured_merge(
        cls, local_rel: str, base_text: str, local_text: str, upstream_text: str
    ) -> tuple[str, list] | None:
        # Returns None when no merger applies or the file cannot be parsed safely,
        # leaving the caller to fall back to the generic line merge.
        normalized = local_rel.replace("\\", "/").lower()
        name = normalized.rsplit("/", 1)[-1]

        if name.endswith(".prf"):
            return cls._merge_prf(base_text, local_text, upstream_text)

        if name.endswith("plugins.txt"):
            return cls._merge_delimited(
                base_text,
                local_text,
                upstream_text,
                2,
                PLUGIN_SETTING_USER_OWNED_KEYS,
            )

        if name.endswith(".txt") and "data/settings/" in normalized:
            return cls._merge_delimited(
                base_text, local_text, upstream_text, 1, set()
            )

        return None

    # ---- AIRAC file customisation carry-forward ------------------------------

    def is_pack_configured(self) -> bool:
        # The profiles themselves are the authority rather than the saved options
        # file: without a certificate in the profiles EuroScope cannot connect,
        # and the options file can be deleted or left behind when a pack is moved.
        for root, _, files in os.walk(self.base_dir):
            for name in files:
                if not name.lower().endswith(".prf"):
                    continue
                try:
                    with open(
                        os.path.join(root, name), "r", encoding="utf-8", errors="replace"
                    ) as f:
                        for line in f:
                            if line.startswith("LastSession\tcertificate\t"):
                                if line.split("\t", 2)[2].strip():
                                    return True
                except OSError:
                    continue

        return False

    def _read_configurator_options(self) -> dict:
        path = os.path.join(self.base_dir, CONFIGURATOR_OPTIONS_FILE)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _find_previous_airac_file(self, local_path: str) -> str | None:
        # Locate the outgoing AIRAC file this one replaces, e.g. the UK_2026_07.sct
        # sitting alongside an incoming UK_2026_08.sct.
        directory = os.path.dirname(local_path)
        name = os.path.basename(local_path)
        suffix = os.path.splitext(name)[1].lower()

        candidates = [
            entry
            for entry in os.listdir(directory)
            if entry.lower() != name.lower()
            and AIRAC_FILE_RE.match(entry)
            and os.path.splitext(entry)[1].lower() == suffix
        ]

        if not candidates:
            return None

        # Compare on the AIRAC tag itself so UK_2026_7 sorts before UK_2026_08.
        newest = max(
            candidates,
            key=lambda e: normalize_version(os.path.splitext(e)[0].split("_", 1)[-1]),
        )
        return os.path.join(directory, newest)

    def _read_previous_airac_text(self, local_path: str) -> str | None:
        try:
            previous = self._find_previous_airac_file(local_path)
            previous_bytes = self._read_bytes_if_exists(previous) if previous else None
            if previous_bytes is None:
                return None
            text, _, _ = self._decode_text(previous_bytes)
            return text
        except Exception as e:
            self.log(
                f"Could not read previous sector file for "
                f"{os.path.basename(local_path)}: {e}"
            )
            return None

    def _carry_forward_airac_customisations(
        self, local_path: str, upstream_bytes: bytes
    ) -> tuple[bytes, bool]:
        # These files arrive as additions every cycle, so there is no common
        # ancestor and an ordinary merge cannot preserve anything.
        #
        # Returns (content, customisation_lost). The flag is set when the outgoing
        # file was customised but the customisation could not be recovered, which
        # is the only way this can silently discard user changes.
        name = os.path.basename(local_path)
        if not AIRAC_FILE_RE.match(name):
            return upstream_bytes, False

        if not name.lower().endswith(AIRAC_CUSTOMISED_SUFFIXES):
            return upstream_bytes, False

        try:
            text, eol, had_bom = self._decode_text(upstream_bytes)
        except UnicodeDecodeError:
            return upstream_bytes, False

        if name.lower().endswith(".ese"):
            return self._carry_forward_ese(local_path, upstream_bytes, text, eol, had_bom)

        previous_text = self._read_previous_airac_text(local_path)
        if previous_text is None:
            return upstream_bytes, False

        carried = []
        for define in SCT_CARRIED_DEFINES:
            pattern = re.compile(rf"^#define {define} .*$", re.MULTILINE)
            chosen = pattern.search(previous_text)
            current = pattern.search(text)
            if chosen and current and current.group(0) != chosen.group(0):
                text = pattern.sub(chosen.group(0).replace("\\", "\\\\"), text, count=1)
                carried.append(define)

        if carried:
            self.log(f"Carried forward {', '.join(carried)} colours into {name}.")

        return self._encode_text(text, eol, had_bom), False

    def _carry_forward_ese(
        self, local_path: str, upstream_bytes: bytes, text: str, eol: str, had_bom: bool
    ) -> tuple[bytes, bool]:
        name = os.path.basename(local_path)

        if ESE_INITIALS_PLACEHOLDER not in text:
            return upstream_bytes, False

        initials = (self._read_configurator_options().get("initials") or "").strip()
        if initials:
            self.log(f"Re-applied controller initials to {name}.")
            return (
                self._encode_text(
                    text.replace(ESE_INITIALS_PLACEHOLDER, initials), eol, had_bom
                ),
                False,
            )

        # No saved options. If the outgoing file had initials applied, they are
        # being lost here and only the Configurator can put them back.
        previous_text = self._read_previous_airac_text(local_path)
        if previous_text is not None and ESE_INITIALS_PLACEHOLDER not in previous_text:
            self.log(
                f"Could not recover controller initials for {name} "
                f"({CONFIGURATOR_OPTIONS_FILE} is missing)."
            )
            return upstream_bytes, True

        return upstream_bytes, False

    def remove_superseded_sector_files(self) -> int:
        # These cannot be cleaned up by the normal removal path: a release only
        # lists what *it* shipped, so a UK_2026_07.* that arrived by any other
        # route is never named for deletion and would accumulate every cycle.
        # Must run after the update loop, since the carry-forward reads the
        # outgoing sector file to recover the user's colour choices.
        directory = os.path.join(self.base_dir, SECTOR_DIR)
        if not os.path.isdir(directory):
            return 0

        by_tag: dict[str, list[str]] = {}
        for entry in os.listdir(directory):
            match = AIRAC_FILE_RE.match(entry)
            if match:
                by_tag.setdefault(normalize_version(match.group(1)), []).append(entry)

        if len(by_tag) < 2:
            return 0

        current = max(by_tag)
        removed = 0

        for tag in sorted(by_tag):
            if tag == current:
                continue
            for entry in sorted(by_tag[tag]):
                try:
                    os.remove(os.path.join(directory, entry))
                    removed += 1
                    self.log(f"Removed superseded sector file {entry}")
                except OSError as e:
                    # Most likely EuroScope still has the old sector file open.
                    self.log(f"Could not remove {entry}: {e}")

        return removed

    def current_airac_sector_file(self) -> str | None:
        # Name of the sector file the pack is currently on, e.g. UK_2026_08.sct.
        directory = os.path.join(self.base_dir, SECTOR_DIR)
        if not os.path.isdir(directory):
            return None

        candidates = [
            entry
            for entry in os.listdir(directory)
            if AIRAC_FILE_RE.match(entry) and entry.lower().endswith(".sct")
        ]
        if not candidates:
            return None

        return max(
            candidates,
            key=lambda e: normalize_version(os.path.splitext(e)[0].split("_", 1)[-1]),
        )

    @staticmethod
    def _asr_single_keys(text: str) -> dict:
        # Collect the one-per-file display settings, keyed by name.
        found: dict[str, str] = {}
        for line in text.split("\n"):
            key, sep, _ = line.partition(":")
            if sep and key in ASR_USER_OWNED_KEYS and key not in found:
                found[key] = line
        return found

    @classmethod
    def _pin_asr_user_settings(
        cls, base_text: str, local_text: str, upstream_text: str
    ) -> tuple[str, str]:
        # Pre-seed base and upstream with display settings the user has changed.
        #
        # Making all three sides agree stops the line merge treating a same-line
        # clash as a conflict, so the user keeps their view while the rest of the
        # display still updates. Settings they never touched are left out of this,
        # so the release can still retune the defaults it ships.
        base_keys = cls._asr_single_keys(base_text)
        local_keys = cls._asr_single_keys(local_text)

        customised = {
            key: line
            for key, line in local_keys.items()
            if key in base_keys and base_keys[key] != line
        }
        if not customised:
            return base_text, upstream_text

        def apply(text: str) -> str:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                key, sep, _ = line.partition(":")
                if sep and key in customised:
                    lines[i] = customised[key]
            return "\n".join(lines)

        return apply(base_text), apply(upstream_text)

    @classmethod
    def _retarget_asr_sector_lines(cls, text: str, current: str) -> tuple[str, bool]:
        # Point any SECTORFILE/SECTORTITLE naming an AIRAC sector file at the
        # current cycle, leaving the path prefix and every other line untouched.
        # Displays pinned to a non-AIRAC sector (Gibraltar, Falkland) are ignored.
        lines = text.split("\n")
        changed = False

        for i, line in enumerate(lines):
            key, sep, value = line.partition(":")
            if not sep or key not in ASR_SECTOR_KEYS:
                continue

            prefix, _, filename = value.rpartition("\\")
            if not AIRAC_FILE_RE.match(filename) or filename == current:
                continue

            lines[i] = f"{key}:{prefix}\\{current}" if prefix else f"{key}:{current}"
            changed = True

        return "\n".join(lines), changed

    def retarget_asr_sector_references(self) -> int:
        # Repoint stale sector references left in ASRs by EuroScope.
        #
        # EuroScope writes the loaded sector file into an ASR when the display is
        # saved. The line merge cannot tell that apart from a real user setting,
        # so it faithfully preserves a path that the AIRAC rollover has renamed
        # and the cleanup above has deleted.
        current = self.current_airac_sector_file()
        if not current:
            return 0

        updated = 0
        for root, _, files in os.walk(self.base_dir):
            for name in files:
                if not name.lower().endswith(".asr"):
                    continue

                path = os.path.join(root, name)
                try:
                    data = self._read_bytes_if_exists(path)
                    if data is None or not self._is_text_bytes(data):
                        continue

                    text, eol, had_bom = self._decode_text(data)
                    retargeted, changed = self._retarget_asr_sector_lines(text, current)
                    if not changed:
                        continue

                    with open(path, "wb") as f:
                        f.write(self._encode_text(retargeted, eol, had_bom))
                    updated += 1
                except OSError as e:
                    self.log(f"Could not update sector reference in {name}: {e}")

        if updated:
            self.log(f"Repointed {updated} radar display(s) at {current}.")

        return updated

    @staticmethod
    def _is_user_owned(local_rel: str) -> bool:
        # Files whose local copy replaces, rather than customises, the pack's.
        normalized = local_rel.replace("\\", "/").lower()
        return (
            normalized.rsplit("/", 1)[-1] in USER_OWNED_FILENAMES
            or normalized.startswith(DATAFILES_DIR.replace("\\", "/").lower() + "/")
        )

    def merge_or_replace_file_from_snapshots(
        self, repo_path: str, from_uk_dir: str, to_uk_dir: str, conflicts: list = None
    ) -> bool:
        # Returns True if the file was actually modified/written locally, False otherwise.
        #
        # When `conflicts` is supplied, the local path is appended to it if the
        # merge had to discard user changes. That is the only case worth asking
        # the user to re-run the Configurator for.
        local_rel = self.get_local_path(repo_path)

        def note_conflict() -> None:
            if conflicts is not None:
                conflicts.append(local_rel)

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
            upstream_bytes, customisation_lost = self._carry_forward_airac_customisations(
                local_path, upstream_bytes
            )
            if customisation_lost:
                note_conflict()
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            return True

        if local_bytes == upstream_bytes:
            return False

        if base_bytes is not None and local_bytes != base_bytes and self._is_user_owned(local_rel):
            # Wholly user-owned content: the Hoppie CPDLC code, or navdata the user
            # replaced via the GNG import. Merging line-by-line would corrupt these,
            # so once touched locally the release copy is not applied at all.
            self.log(f"Preserved user-owned file {local_rel}.")
            return False

        if base_bytes is None:
            # New upstream file with existing local content: upstream takes priority.
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            self.log(f"Conflict on new file {local_rel}; upstream version applied.")
            note_conflict()
            return True

        if not (
            self._is_text_bytes(base_bytes)
            and self._is_text_bytes(local_bytes)
            and self._is_text_bytes(upstream_bytes)
        ):
            if local_bytes == base_bytes:
                with open(local_path, "wb") as f:
                    f.write(upstream_bytes)
                return True
            if upstream_bytes == base_bytes:
                self.log(f"Preserved local changes in {local_rel} (upstream unchanged).")
                return False
            with open(local_path, "wb") as f:
                f.write(upstream_bytes)
            self.log(f"Major binary conflict in {local_rel}; upstream version applied.")
            note_conflict()
            return True

        # Compare on normalised text so line-ending drift between the release ZIP
        # and the local install is never mistaken for a user customisation.
        base_text, _, _ = self._decode_text(base_bytes)
        local_text, local_eol, local_bom = self._decode_text(local_bytes)
        upstream_text, _, _ = self._decode_text(upstream_bytes)

        if local_rel.lower().endswith(".asr"):
            base_text, upstream_text = self._pin_asr_user_settings(
                base_text, local_text, upstream_text
            )

        def write(text: str) -> bytes:
            data = self._encode_text(text, local_eol, local_bom)
            with open(local_path, "wb") as f:
                f.write(data)
            return data

        if local_text == upstream_text:
            write(upstream_text)
            return True

        if local_text == base_text:
            write(upstream_text)
            return True

        if upstream_text == base_text:
            self.log(f"Preserved local changes in {local_rel} (upstream unchanged).")
            return False

        structured = self._structured_merge(
            local_rel, base_text, local_text, upstream_text
        )

        if structured is not None:
            merged_text, lost_keys = structured
            if lost_keys:
                self.log(
                    f"Applied release values over {len(lost_keys)} customised "
                    f"setting(s) in {local_rel}: "
                    + ", ".join("/".join(k) for k in sorted(lost_keys)[:5])
                    + (" ..." if len(lost_keys) > 5 else "")
                )
                note_conflict()
        else:
            merged_text, had_conflict = self._merge_text_three_way(
                base_text, local_text, upstream_text
            )
            if had_conflict:
                merged_text = upstream_text
                self.log(
                    f"Major merge conflict in {local_rel}; upstream version applied."
                )
                note_conflict()

        if merged_text == local_text:
            return False

        merged_bytes = write(merged_text)

        if merged_text == upstream_text:
            self.log(f"Applied upstream update for {local_rel}.")
        else:
            self.log(f"Merged upstream and local changes for {local_rel}.")

        return merged_bytes != local_bytes

    def download_release_snapshot_for_tag(self, tag: str) -> str:
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
        # Compare Git blob IDs so we detect true content changes, not just name/timestamp differences.
        from_uk_dir = None
        to_uk_dir = None

        try:
            from_uk_dir = self.download_release_snapshot_for_tag(from_tag)
            to_uk_dir = self.download_release_snapshot_for_tag(to_tag)

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

    def prompt_configurator_if_needed(self, conflicted_files: list = None) -> bool:
        # Returns whether a prompt was raised.
        conflicted_files = conflicted_files or []

        if not self.is_pack_configured():
            self.log(
                "\n⚠️ This pack has not been configured yet - EuroScope will not "
                "be able to connect until you run the Configurator."
            )
            self.root.after(0, lambda: self.prompt_run_configurator(unconfigured=True))
            return True

        if conflicted_files:
            self.log(
                f"\n⚠️ {len(conflicted_files)} file(s) had customisations that "
                "could not be merged and were replaced by the release version."
            )
            self.root.after(0, lambda: self.prompt_run_configurator(conflicted_files))
            return True

        return False

    def prompt_run_configurator(
        self, conflicted_files: list = None, unconfigured: bool = False
    ) -> None:
        conflicted_files = conflicted_files or []

        if unconfigured:
            msg = (
                "This copy of the controller pack has not been set up yet.\n\n"
                "Your VATSIM name, CID, rating and password are not present in "
                "any profile, so EuroScope will not be able to connect.\n\n"
                "Do you want to run Configurator.exe now?"
            )
            title = "Pack not configured"
        else:
            listed = "\n".join(f"  • {f}" for f in conflicted_files[:10])
            if len(conflicted_files) > 10:
                listed += f"\n  • ...and {len(conflicted_files) - 10} more"

            msg = (
                f"{len(conflicted_files)} file(s) had customisations that could not "
                "be merged with this release, so the release version was applied:"
                f"\n\n{listed}\n\n"
                "Running the UK Controller Pack Configurator will re-apply your "
                "settings to them.\n\n"
                "Do you want to run Configurator.exe now?"
            )
            title = "Customisations replaced"

        if not messagebox.askyesno(title, msg):
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

        try:
            if normalize_version(local_ver) >= normalize_version(latest_ver):
                updated_files: list[str] = []
                removed_files: list[str] = []
            else:
                updated_files, removed_files, _ = (
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
                # A freshly downloaded pack is already current but still unusable
                # until the Configurator has run.
                self.prompt_configurator_if_needed()
                return

            from_uk_dir = None
            to_uk_dir = None
            # Files where the merge could not keep the user's changes. Only these
            # are worth interrupting the user about; everything else merged cleanly.
            conflicted_files: list[str] = []
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
                    self.merge_or_replace_file_from_snapshots(
                        file, from_uk_dir, to_uk_dir, conflicted_files
                    )
            finally:
                if from_uk_dir:
                    shutil.rmtree(os.path.dirname(from_uk_dir), ignore_errors=True)
                if to_uk_dir:
                    shutil.rmtree(os.path.dirname(to_uk_dir), ignore_errors=True)

            for file in removed_files:
                self.delete_file(file)

            self.remove_superseded_sector_files()
            self.retarget_asr_sector_references()

            self.set_local_version(latest_ver)
            if release_sha:
                self.set_local_pack_version(release_sha)
            self.log(
                f"\nUpdate complete: now on {REPO_OWNER}/{REPO_NAME} version "
                f"{latest_ver} (released {release_date})"
            )

            self.root.after(0, self.offer_gng_prompt)

            self.prompt_configurator_if_needed(conflicted_files)

        except Exception as e:
            self.log(f"Update failed: {e}")

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
