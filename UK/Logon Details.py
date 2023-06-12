import os
import glob
import time

# User Inputs

Name = input("Enter Name: ")
os.system('cls')
CID = input("Enter CID: ")
os.system('cls')
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

PrfVCCS=("TeamSpeakVccs	Ts3NickName	"+CID)

# Appeding "LastSession" to user input

PrfName=("LastSession	realname	"+Name)
PrfCID=("LastSession	certificate	"+CID)
#PrfPassword=("LastSession	password	"+Password)

# Adds all .prf files to an array and then writes to all those files

for root, dirs, files in os.walk(os.getcwd()):
    for file in files:
        if file.endswith(".prf"):
            file_path = os.path.join(root, file)
            with open(file_path, 'a') as f:
                    f.write(f"{PrfName}\n{PrfCID}\n")

print("Detail entry process complete")
time.sleep(1.5)
