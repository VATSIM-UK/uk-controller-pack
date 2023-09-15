import os
import time

# User Inputs

Name = input("Enter Name: ")
os.system('cls')
CID = input("Enter CID: ")
os.system('cls')
#User selects controller rating from list
options = ['OBS', 'S1', 'S2', 'S3', 'C1', 'C2', 'C3',  'I1', 'I2', 'I3', 'SUP', 'ADM']

rating = ''

input_message = "Select Controller Rating:\n"

for index, item in enumerate(options):
    input_message += f'{index}) {item}\n'

input_message += 'Your choice: '

while rating not in map(str, range(0, len(options))):
    rating = input(input_message)

print (rating)
#Password = input("Enter Password: ")
#os.system('cls')
# Left commented as password is stored plain text, could be uncommented later

CPDLC = input("Enter Hoppie's Code: ")
os.system('cls')

# Write CPDLC to TopSky

f = open("Data/Plugin/TopSky/TopSkyCPDLChoppieCode.txt", "w")
f.write(CPDLC)
f.close

# Add CID as Nickname to VCCS profiles

PrfVCCS=("TeamSpeakVccs Ts3NickName	"+CID)

# Appeding "LastSession" to user input

PrfName=("LastSession	realname	"+Name)
PrfCID=("LastSession	certificate	"+CID)
Prfrating=("LastSession	rating	"+rating)
#PrfPassword=("LastSession	password	"+Password)

# Adds all .prf files to an array and then writes to all those files

for root, dirs, files in os.walk(os.getcwd()):
    for file in files:
        if file.endswith(".prf"):
            file_path = os.path.join(root, file)
            with open(file_path, 'a') as f:
                f.write(f"\n{PrfName}\n{PrfCID}\n{Prfrating}\n{PrfVCCS}\n")
        elif file.endswith("Plugins.txt"):
            file_path = os.path.join(root, file)
            with open(file_path, 'r') as f:
                line = f.read()
                line = line.replace("END", "vSMR:cpdlc_password:"+CPDLC+"\nEND")
                writeFile = open(file_path, "w")
                writeFile.write(line)

print("Detail entry process complete")
time.sleep(1.5)
