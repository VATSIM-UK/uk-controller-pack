import os
import time
import keyboard
import sounddevice as sd

def has_matching_brackets(s):
    stack = []
    for char in s:
        if char == '(':
            stack.append(char)
        elif char == ')':
            if not stack:
                return False
            stack.pop()
    return not stack

# User Inputs
# Name

Name = input("Enter Name: ")
os.system('cls')

#Initials (used for ESE alternate ownership and OBS callsign)

Initials = input("Enter Initials (for _OBS callsign):")
os.system('cls')

# VATSIM Certificate ID

CID = input("Enter CID: ")
os.system('cls')

#Controller Rating

options = ['OBS', 'S1', 'S2', 'S3', 'C1', 'C2 (not used)', 'C3',  'I1', 'I2 (not used)', 'I3', 'SUP', 'ADM']

rating = ''

input_message = "Select Controller Rating:\n"

for index, item in enumerate(options):
    input_message += f'{index}) {item}\n'

input_message += 'Your choice: '

while rating not in map(str, range(0, len(options))):
    rating = input(input_message)
os.system('cls')

# Password WARNING:EuroScope stores passwords as plain text!

Password = input("Enter Password: ")
os.system('cls')

# Hoppie CPDLC logon code

CPDLC = input("Enter Hoppie's Code: ")
os.system('cls')

# VCCS PTT Key

print("Push a key you want to use for VCCS. (Note: Keyboard only)")
PTT = str(int(hex(keyboard.read_event().scan_code), 16) << 16)
os.system('cls')

# VCCS Input and Output Device Selection

VCCSInput = input("Would you like to use your default audio settings for VCCS? (y/n): ").lower()
os.system('cls')

if 'n' in VCCSInput:
    devices = sd.query_devices()
    unique_input_devices = set()
    unique_output_devices = set()

    input_device = ''
    output_device = ''

    input_device_msg = "Please select the input device: \n"
    output_device_msg = "Please select the output device: \n"

    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0 and "mapper" not in device['name'].lower() and not "driver" in device['name'].lower() and has_matching_brackets(device['name']):
            if device['name'] not in unique_input_devices:
                unique_input_devices.add(device['name'])

    for index, item in enumerate(unique_input_devices):
        input_device_msg += f'{index}) {item}\n'

    while input_device not in map(str, range(0, len(unique_input_devices))):
        input_device = input(input_device_msg)
        VCCSInput = list(unique_input_devices)[int(input_device)]
    os.system('cls')

    for i, device in enumerate(devices):
        if device['max_output_channels'] > 0 and "mapper" not in device['name'].lower() and not "driver" in device['name'].lower() and has_matching_brackets(device['name']):
            if device['name'] not in unique_output_devices:
                unique_output_devices.add(device['name'])

    for index, item in enumerate(unique_output_devices):
        output_device_msg += f'{index}) {item}\n'

    while output_device not in map(str, range(0, len(unique_output_devices))):
        output_device = input(output_device_msg)
        VCCSOutput = list(unique_output_devices)[int(output_device)]
    os.system('cls')
else:
    VCCSInput = sd.query_devices(sd.default.device[0])['name']
    VCCSOutput = sd.query_devices(sd.default.device[1])['name']


# Write CPDLC to TopSky (all instances)

f = open("Data/Plugin/TopSky_iTEC/TopSkyCPDLChoppieCode.txt", "w")
f.write(CPDLC)

f = open("Data/Plugin/TopSky_NERC/TopSkyCPDLChoppieCode.txt", "w")
f.write(CPDLC)

f = open("Data/Plugin/TopSky_NODE/TopSkyCPDLChoppieCode.txt", "w")
f.write(CPDLC)

f = open("Data/Plugin/TopSky_NOVA/TopSkyCPDLChoppieCode.txt", "w")
f.write(CPDLC)

f.close

# Set VCCS Settings

PrfVCCSNick=("TeamSpeakVccs	Ts3NickName	"+CID)
PrfVCCSPTT=("TeamSpeakVccs Ts3G2GPtt "+PTT)
PrfVCCSInput=("TeamSpeakVccs	CaptureDevice	"+VCCSInput)
PrfVCCSOutput=("TeamSpeakVccs	PlaybackDevice	"+VCCSOutput)

#Set intials as object

EseInitials=(Initials)

# Prefixing "LastSession" to user input

PrfName=("LastSession	realname	"+Name)
PrfCID=("LastSession	certificate	"+CID)
Prfrating=("LastSession	rating	"+rating)
PrfOBSCallsign=("LastSession	callsign	"+EseInitials+"_OBS")
PrfPassword=("LastSession	password	"+Password)

# Adds all .prf files to an array and then writes to all those files

for root, dirs, files in os.walk(os.getcwd()):
    for file in files:
        if file.endswith(".prf"):
            file_path = os.path.join(root, file)
            with open(file_path, 'a') as f:
                f.write(f"\n{PrfVCCSNick}\n{PrfVCCSPTT}\n{PrfVCCSInput}\n{PrfVCCSOutput}\n{PrfName}\n{PrfCID}\n{PrfOBSCallsign}\n{Prfrating}\n{PrfPassword}\n")

# Adds CPDLC code to Plugins.txt files for vSMR use

        elif file.endswith("Plugins.txt"):
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                line = f.read()
                line = line.replace("END", "vSMR Vatsim UK:cpdlc_password:"+CPDLC+"\nEND")
                writeFile = open(file_path, "w")
                writeFile.write(line)

# Adds Intials to ESE for use with alternate ownership

        elif file.endswith(".ese") and file.startswith("UK"):
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                line = f.read()
                line = line.replace(f"EXAMPLE", str(EseInitials))
                writeFile = open(file_path, "w")
                writeFile.write(line)

# Adds CID field to feedback link

        elif file == "Profiles.txt":
            file_path = os.path.join(root,file)
            with open(file_path,'r') as f:
                line = f.read()
                line = line.replace("Submit feedback at vats.im/atcfb",f"Submit feedback at vatsim.uk/atcfb?cid={CID}")
                with open(file_path,'w') as out_f:
                    out_f.write(line)


print("Detail entry process complete")
time.sleep(1.5)
