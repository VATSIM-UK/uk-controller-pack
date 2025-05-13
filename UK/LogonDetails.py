
import os
import time

def get_basic_user_inputs():
    os.system('cls')
    name = input("Enter Name: ")
    os.system('cls')
    initials = input("Enter Initials (for _OBS callsign):")
    os.system('cls')
    cid = input("Enter CID: ")
    os.system('cls')

    options = ['OBS', 'S1', 'S2', 'S3', 'C1', 'C2 (not used)', 'C3',  'I1', 'I2 (not used)', 'I3', 'SUP', 'ADM']
    rating = ''
    input_message = "Select Controller Rating:\n"
    for index, item in enumerate(options):
        input_message += f'{index}) {item}\n'
    input_message += 'Your choice: '
    while rating not in map(str, range(0, len(options))):
        rating = input(input_message)
    os.system('cls')

    password = input("Enter Password: ")
    os.system('cls')
    cpdlc = input("Enter Hoppie's Code: ")
    os.system('cls')

    return name, initials, cid, rating, password, cpdlc

def get_advanced_options():
    advanced = input("Would you like to configure advanced options? (y/n): ").strip().lower()
    if advanced != 'y':
        print("Advanced options skipped.")
        return None

    realistic_tags = input("Do you want realistic tags? (y/n): ").strip().lower()
    realistic_conversion = input("Do you want realistic code/callsign conversion? (y/n): ").strip().lower()

    print("\nSelect coastline colour:")
    print("1: Light Blue (Default)")
    print("2: Grey (STC/PC)")
    print("3: Yellow ")
    coast_choice = input("Enter choice (1/2/3): ").strip()

    print("\nSelect land colour:")
    print("1: Medium Grey (Default)")
    print("2: Dark Grey")
    print("3: Light Grey")
    land_choice = input("Enter choice (1/2/3): ").strip()

    return {
        'realistic_tags': realistic_tags,
        'realistic_conversion': realistic_conversion,
        'coast_choice': coast_choice,
        'land_choice': land_choice
    }

def apply_basic_configuration(name, initials, cid, rating, password, cpdlc):
    paths = [
        "Data/Plugin/TopSky_iTEC/TopSkyCPDLChoppieCode.txt",
        "Data/Plugin/TopSky_NERC/TopSkyCPDLChoppieCode.txt",
        "Data/Plugin/TopSky_NODE/TopSkyCPDLChoppieCode.txt",
        "Data/Plugin/TopSky_NOVA/TopSkyCPDLChoppieCode.txt"
    ]
    for path in paths:
        with open(path, "w") as f:
            f.write(cpdlc)

    vccs = f"TeamSpeakVccs\tTs3NickName\t{cid}"
    name_line = f"LastSession\trealname\t{name}"
    cid_line = f"LastSession\tcertificate\t{cid}"
    rating_line = f"LastSession\trating\t{rating}"
    callsign_line = f"LastSession\tcallsign\t{initials}_OBS"
    password_line = f"LastSession\tpassword\t{password}"

    for root, _, files in os.walk(os.getcwd()):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(".prf"):
                with open(file_path, 'a') as f:
                    f.write(f"\n{vccs}\n{name_line}\n{cid_line}\n{callsign_line}\n{rating_line}\n{password_line}\n")
            elif file.endswith("Plugins.txt"):
                with open(file_path, 'r') as f:
                    content = f.read()
                content = content.replace("END", f"vSMR Vatsim UK:cpdlc_password:{cpdlc}\nEND")
                with open(file_path, 'w') as f:
                    f.write(content)
            elif file.endswith(".ese") and file.startswith("UK"):
                with open(file_path, 'r') as f:
                    content = f.read().replace("EXAMPLE", initials)
                with open(file_path, 'w') as f:
                    f.write(content)
            elif file.endswith("Profiles.txt"):
                with open(file_path, 'r') as f:
                    content = f.read().replace("Submit feedback at vats.im/atcfb", f"Submit feedback at vatsim.uk/atcfb?cid={cid}")
                with open(file_path, 'w') as f:
                    f.write(content)

def apply_advanced_configuration(options):
    # Realistic Tags and MODE C
    asr_files = [
        os.path.join(root, file)
        for root, _, files in os.walk('.')
        for file in files if file.endswith('.asr')
    ]

    for file_path in asr_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if 'TAGFAMILY:AC-TopSky' in line or 'TAGFAMILY:NODE' in line:
                if options['realistic_tags'] == 'n' and not line.strip().endswith('-Easy'):
                    line = line.strip() + '-Easy\n'
                elif options['realistic_tags'] == 'y' and line.strip().endswith('-Easy'):
                    line = line.replace('-Easy', '')
            if 'SIMULATION_MODE:' in line:
                if options['realistic_conversion'] == 'y':
                    line = line.replace('SIMULATION_MODE:1', 'SIMULATION_MODE:4')
                else:
                    line = line.replace('SIMULATION_MODE:4', 'SIMULATION_MODE:1')
            new_lines.append(line)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    sct_files = [
        os.path.join(root, file)
        for root, _, files in os.walk('.')
        for file in files if file.startswith('UK_') and file.endswith('.sct')
    ]

    coast_colors = {'1': '9076039', '2': '5324604', '3': '32896'}
    land_colors = {'1': '3947580', '2': '1777181', '3': '8158332'}

    for file_path in sct_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.startswith('#define coast '):
                line = f"#define coast {coast_colors.get(options['coast_choice'], '0.5 0.5 0.5')}\n"
            if line.startswith('#define land '):
                line = f"#define land {land_colors.get(options['land_choice'], '0.6 0.6 0.6')}\n"
            new_lines.append(line)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

def main():
    name, initials, cid, rating, password, cpdlc = get_basic_user_inputs()
    advanced_options = get_advanced_options()
    apply_basic_configuration(name, initials, cid, rating, password, cpdlc)
    if advanced_options:
        apply_advanced_configuration(advanced_options)
    print("Profile Configuration Complete")
    time.sleep(1.5)

if __name__ == "__main__":
    main()