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

aerodrome=((glob.glob('**/*.prf'))+(glob.glob('**/**/*.prf')+(glob.glob('**/**/**/*.prf'))))

for i in aerodrome:
    f=open(i, "a")
    f.write("\n")
    f.write(PrfName)
    f.write("\n")
    f.write(PrfCID)
    f.write("\n")
#    f.write(PrfPassword)
#    f.write("\n")
    f.write(PrfVCCS)
    f.close
    print(i)

print("Detail entry process complete")
time.sleep(1.5)
