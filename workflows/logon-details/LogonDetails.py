import os
import sys
import json
import time
import tempfile
import tkinter as tk
from tkinter import simpledialog, messagebox
import tkinter.simpledialog as simpledialog 
from PIL import Image, ImageTk

_original_init = simpledialog.Dialog.__init__

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

OPTIONS_PATH = os.path.join(BASE_DIR, "myOptions.json")

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
    "land_choice": "1"
}

BASIC_FIELDS = ["name", "initials", "cid", "rating", "password", "cpdlc"]
ADVANCED_FIELDS = ["realistic_tags", "realistic_conversion", "coast_choice", "land_choice"]

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

    tk.Label(dialog, text=prompt).pack(padx=20, pady=(15, 5))

    entry_var = tk.StringVar(value=default)
    entry = tk.Entry(dialog, textvariable=entry_var, width=40)
    entry.pack(padx=20, pady=5)
    entry.focus_set()

    def submit(event=None):
        nonlocal result
        result = entry_var.get()
        dialog.destroy()

    def cancel(event=None):
        dialog.destroy()

    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=15)
    tk.Button(button_frame, text="OK", width=10, command=submit).pack(side="left", padx=5)
    tk.Button(button_frame, text="Cancel", width=10, command=cancel).pack(side="left", padx=5)

    dialog.bind("<Return>", submit)
    dialog.bind("<Escape>", cancel)

    dialog.transient()
    dialog.grab_set()
    center_window(dialog)
    dialog.wait_window()

    return result

def ask_yesno(prompt):
    result = None
    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title("UK Controller Pack Configurator")
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    dialog.resizable(False, False)

    tk.Label(dialog, text=prompt, wraplength=300, justify="left").pack(padx=20, pady=15)

    def yes():
        nonlocal result
        result = True
        dialog.destroy()

    def no():
        nonlocal result
        result = False
        dialog.destroy()

    button_frame = tk.Frame(dialog)
    button_frame.pack(pady=10)
    tk.Button(button_frame, text="Yes", width=10, command=yes).pack(side="left", padx=5)
    tk.Button(button_frame, text="No", width=10, command=no).pack(side="left", padx=5)

    dialog.bind("<Return>", lambda e: yes())
    dialog.bind("<Escape>", lambda e: no())

    dialog.transient()
    dialog.grab_set()
    center_window(dialog)
    dialog.wait_window()

    return result

def ask_dropdown(prompt, options_list, current=None):
    selected = tk.StringVar(value=current if current in options_list else options_list[0])
    def submit():
        dialog.quit()
        dialog.destroy()
    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title(prompt)
    tk.Label(dialog, text=prompt).pack(pady=5)
    dropdown = tk.OptionMenu(dialog, selected, *options_list)
    dropdown.pack(pady=5)
    tk.Button(dialog, text="OK", command=submit).pack()
    dialog.transient()
    dialog.grab_set()
    dialog.mainloop()
    return selected.get()

def ask_rating(current=None):
    ratings = ['OBS', 'S1', 'S2', 'S3', 'C1', 'C2 (not used)', 'C3', 'I1', 'I2 (not used)', 'I3', 'SUP', 'ADM']
    selected = tk.StringVar(value=ratings[int(current)] if current and current.isdigit() else ratings[0])
    def submit():
        dialog.quit()
        dialog.destroy()
    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title("Select Controller Rating")
    tk.Label(dialog, text="Select your rating:").pack(pady=5)
    dropdown = tk.OptionMenu(dialog, selected, *ratings)
    dropdown.pack(pady=5)
    tk.Button(dialog, text="OK", command=submit).pack()
    dialog.transient()
    dialog.grab_set()
    dialog.mainloop()
    return str(ratings.index(selected.get()))

def ask_with_images(title, prompt, image_dict, current_key, descriptions_dict=None):
    dialog = tk.Toplevel()
    dialog.iconbitmap(resource_path("logo.ico"))
    dialog.title(title)
    tk.Label(dialog, text=prompt).pack(pady=5)
    var = tk.StringVar(value=current_key if current_key in image_dict else "1")
    image_refs = []

    for key, image_path in image_dict.items():
        img = Image.open(image_path)
        photo = ImageTk.PhotoImage(img)
        image_refs.append(photo)

        frame = tk.Frame(dialog)
        frame.pack(pady=5, anchor="center")

        tk.Radiobutton(frame, image=photo, variable=var, value=key, compound="top").pack()
        desc = descriptions_dict.get(key, f"Option {key}") if descriptions_dict else f"Option {key}"
        tk.Label(frame, text=desc, wraplength=280, justify="left").pack()

    def submit():
        dialog.quit()
        dialog.destroy()

    tk.Button(dialog, text="OK", command=submit).pack(pady=10)
    dialog.transient()
    dialog.grab_set()
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
        "realistic_tags": "Select Yes if you want realistic aircraft datablocks. Select No if you want climb/descent arrows in aircraft datablocks",
        "realistic_conversion": "Select Yes if you want to enable realistic code/callsign conversion. Select No if not required (not recommended)",
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

    elif key in ["realistic_tags", "realistic_conversion"]:
        return "y" if ask_yesno(description) else "n"
    else:
        return ask_string(description, current)

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

    if ask_yesno("Would you like to configure advanced options?"):
        for key in ADVANCED_FIELDS:
            options[key] = prompt_for_field(key, options.get(key, ""))

    save_options(options)
    root.destroy()
    return options


def patch_prf_file(file_path, name, initials, cid, rating, password):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return

    lines = [l for l in lines if not (
        l.startswith("TeamSpeakVccs\tTs3NickName") or
        l.startswith("LastSession\trealname") or
        l.startswith("LastSession\tcertificate") or
        l.startswith("LastSession\trating") or
        l.startswith("LastSession\tcallsign") or
        l.startswith("LastSession\tpassword")
    )]

    new_lines = [
        f"TeamSpeakVccs\tTs3NickName\t{cid}\n",
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

def apply_basic_configuration(name, initials, cid, rating, password, cpdlc):
    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            path = os.path.join(root, file)
            if file.endswith(".prf"):
                patch_prf_file(path, name, initials, cid, rating, password)
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
            if file.endswith(".asr"):
                with open(path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                for line in lines:
                    if line.startswith("TAGFAMILY:NODE") or line.startswith("TAGFAMILY:AC"):
                        if options["realistic_tags"] == "n" and "-Easy" not in line:
                            line = line.strip() + "-Easy\n"
                        elif options["realistic_tags"] == "y" and "-Easy" in line:
                            line = line.replace("-Easy", "")
                    new_lines.append(line)
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
            elif file.startswith("UK_") and file.endswith(".sct"):
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
            elif file.endswith(".txt") and os.path.commonpath([os.path.abspath(root), os.path.abspath("UK/Data/Settings")]) == os.path.abspath("UK/Data/Settings"):
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

def main():
    lockfile = os.path.join(BASE_DIR, 'logondetails.lock')
    if os.path.exists(lockfile):
        messagebox.showerror("Already Running", "Configurator is already running.")
        sys.exit()
    with open(lockfile, 'w') as f:
        f.write(str(os.getpid()))
    options = collect_user_input()
    apply_basic_configuration(
        name=options["name"],
        initials=options["initials"],
        cid=options["cid"],
        rating=options["rating"],
        password=options["password"],
        cpdlc=options["cpdlc"]
    )
    apply_advanced_configuration(options)
    if os.path.exists(lockfile):
        os.remove(lockfile)

    messagebox.showinfo("Complete", "Profile Configuration Complete")
    time.sleep(1.5)

if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            for w in tk._default_root.children.values():
                w.destroy()
            tk._default_root.destroy()
        except Exception:
            pass
        if getattr(sys, 'frozen', False):
            os._exit(0)
        else:
            sys.exit(0)

