import os
import sys
import json
import time
import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(__file__)

OPTIONS_PATH = os.path.join(BASE_DIR, "myOptions.json")
IMAGE_DIR = os.path.join(BASE_DIR, "images")

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

def load_previous_options():
    if os.path.exists(OPTIONS_PATH):
        with open(OPTIONS_PATH, "r") as f:
            return json.load(f)
    return {}

def save_options(options):
    with open(OPTIONS_PATH, "w") as f:
        json.dump(options, f, indent=2)

def ask_string(prompt, default=""):
    return simpledialog.askstring("Input", prompt, initialvalue=default)

def ask_yesno(prompt):
    return messagebox.askyesno("Select", prompt)

def ask_dropdown(prompt, options_list, current=None):
    selected = tk.StringVar(value=current if current in options_list else options_list[0])
    def submit():
        dialog.quit()
        dialog.destroy()
    dialog = tk.Toplevel()
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
    dialog.title("Select Controller Rating")
    tk.Label(dialog, text="Select your rating:").pack(pady=5)
    dropdown = tk.OptionMenu(dialog, selected, *ratings)
    dropdown.pack(pady=5)
    tk.Button(dialog, text="OK", command=submit).pack()
    dialog.transient()
    dialog.grab_set()
    dialog.mainloop()
    return str(ratings.index(selected.get()))

def ask_with_images(title, prompt, image_dict, current_key):
    dialog = tk.Toplevel()
    dialog.title(title)
    tk.Label(dialog, text=prompt).pack(pady=5)
    var = tk.StringVar(value=current_key if current_key in image_dict else "1")
    image_refs = []
    for key, image_path in image_dict.items():
        img = Image.open(image_path)
        img = img.resize((280, 60))
        photo = ImageTk.PhotoImage(img)
        image_refs.append(photo)
        tk.Radiobutton(dialog, image=photo, text=f"Option {key}", variable=var, value=key, compound="top").pack(anchor="w")
    def submit():
        dialog.quit()
        dialog.destroy()
    tk.Button(dialog, text="OK", command=submit).pack(pady=10)
    dialog.transient()
    dialog.grab_set()
    dialog.mainloop()
    return var.get()

def prompt_for_field(key, current):
    if key == "rating":
        return ask_rating(current)
    elif key == "coast_choice":
        return ask_with_images("Select Coastline", "Choose a coastline style:", {
            "1": os.path.join(IMAGE_DIR, "coastline1.png"),
            "2": os.path.join(IMAGE_DIR, "coastline2.png"),
            "3": os.path.join(IMAGE_DIR, "coastline3.png")
        }, current)
    elif key == "land_choice":
        return ask_with_images("Select Land Color", "Choose a land style:", {
            "1": os.path.join(IMAGE_DIR, "land1.png"),
            "2": os.path.join(IMAGE_DIR, "land2.png"),
            "3": os.path.join(IMAGE_DIR, "land3.png")
        }, current)
    elif key in ["realistic_tags", "realistic_conversion"]:
        return "y" if ask_yesno(f"{key.replace('_', ' ').capitalize()}?") else "n"
    else:
        return ask_string(f"Enter {key.replace('_', ' ')}", current)

def collect_user_input():
    root = tk.Tk()
    root.withdraw()
    previous_options = load_previous_options()
    options = {}
    if previous_options:
        use_previous = ask_yesno("Do you want to load your previous options?")
        if use_previous:
            options.update(previous_options)
            for k in DEFAULT_FIELDS:
                if k not in options:
                    options[k] = prompt_for_field(k, "")
        else:
            options = {}
    for key in DEFAULT_FIELDS:
        if key not in options or not options[key]:
            options[key] = prompt_for_field(key, "")
    save_options(options)
    return options

def patch_prf_file(file_path, name, initials, cid, rating, password):
    keys = ["TeamSpeakVccs", "LastSession	realname", "LastSession	certificate",
            "LastSession	rating", "LastSession	callsign", "LastSession	password"]
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    lines = [l for l in lines if not any(k in l for k in keys)]
    new_lines = [
        f"TeamSpeakVccs\tTs3NickName\t{cid}\n",
        f"LastSession\trealname\t{name}\n",
        f"LastSession\tcertificate\t{cid}\n",
        f"LastSession\trating\t{rating}\n",
        f"LastSession\tcallsign\t{initials}_OBS\n",
        f"LastSession\tpassword\t{password}\n"
]

    lines += ["\n"] + new_lines

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

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
    if not ask_yesno("Would you like to configure advanced options?"):
        return
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
                    if 'TAGFAMILY' in line:
                        if options["realistic_tags"] == "n" and "-Easy" not in line:
                            line = line.strip() + "-Easy\n"
                        elif options["realistic_tags"] == "y" and "-Easy" in line:
                            line = line.replace("-Easy", "")
                    if "SIMULATION_MODE:" in line:
                        if options["realistic_conversion"] == "y":
                            line = line.replace("SIMULATION_MODE:1", "SIMULATION_MODE:4")
                        else:
                            line = line.replace("SIMULATION_MODE:4", "SIMULATION_MODE:1")
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

def main():
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
    messagebox.showinfo("Complete", "Profile Configuration Complete")
    time.sleep(1.5)

if __name__ == "__main__":
    main()