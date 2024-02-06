import os
import time

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

# Write CPDLC to TopSky

f = open("Data/Plugin/TopSky/TopSkyCPDLChoppieCode.txt", "w")
f.write(CPDLC)
f.close

# Add CID as Nickname to VCCS profiles

PrfVCCS=("TeamSpeakVccs	Ts3NickName	"+CID)

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
                f.write(f"\n{PrfVCCS}\n{PrfName}\n{PrfCID}\n{PrfOBSCallsign}\n{Prfrating}\n{PrfPassword}\n")

# Adds CPDLC code to Plugins.txt files for vSMR use

        elif file.endswith("Plugins.txt"):
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                line = f.read()
                line = line.replace("END", "vSMR:cpdlc_password:"+CPDLC+"\nEND")
                writeFile = open(file_path, "w")
                writeFile.write(line)

# Adds Intials to ESE for use with alternate ownership

        elif file.endswith(".ese"):
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                line = f.read()
                line = line.replace(f"EXAMPLE", str(EseInitials))
                writeFile = open(file_path, "w")
                writeFile.write(line)

print("Detail entry process complete")
time.sleep(1.5)
