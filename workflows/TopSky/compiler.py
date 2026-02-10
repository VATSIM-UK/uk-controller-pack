import os
import shutil

# Whilst all data changes are constructed, only when the data files are changed will the result be committed
# When files need conjoining, iTEC is used as the working directory, and data files are copied across to NERC, NODE, and NOVA directories
#region Constants
iTEC_Path = 'UK/Data/Plugin/TopSky_iTEC/'
NERC_Path = 'UK/Data/Plugin/TopSky_NERC/'
NODE_Path = 'UK/Data/Plugin/TopSky_NODE/'
NOVA_Path = 'UK/Data/Plugin/TopSky_NOVA/'
MIL_Path = 'UK/Data/Plugin/TopSky_MIL/'
Shared_Path = '.data/TopSky Shared/'
Index_Name = '.Index.txt'
#endregion

def main():
    AircraftJSON()
    AircraftText()
    Airlines()
    Airports()
    Airspace()
    Callsigns()
    LocalCallsigns()
    Areas()
    CPDLC()
    Maps()
    MSAW()
    Radars()
    ChangeMilDangerAreaDefinition()

#region Single-file copy-across and renaming
def AircraftJSON():
    Remove('ICAO_Aircraft.json')
    CopyAll('ICAO_Aircraft.json', 'ICAO_Aircraft.json')

def AircraftText():
    Remove('ICAO_Aircraft.txt')
    CopyAll('ICAO_Aircraft.txt', 'ICAO_Aircraft.txt')

def Airlines():
    Remove('ICAO_Airlines.txt')
    CopyAll('ICAO_Airlines.txt', 'ICAO_Airlines.txt')

def Airports():
    Remove('ICAO_Airports.txt')
    CopyAll('ICAO_Airports.txt', 'ICAO_Airports.txt')

def Airspace():
    Remove('TopSkyAirspace.txt')
    CopyAll('Airspace.txt', 'TopSkyAirspace.txt')

def Callsigns():
    Remove('TopSkyCallsigns.txt')
    CopyAll('Callsigns.txt', 'TopSkyCallsigns.txt')

def LocalCallsigns():
    Remove('TopSkyCallsignsLocal.txt')
    CopyAll('Local Callsigns.txt', 'TopSkyCallsignsLocal.txt')
#endregion

#region Compiled datafile construction
def Areas():
    AreaFiles = ImportFileIndex('Areas/')
    Remove('TopSkyAreas.txt')
    Construct('Areas/', AreaFiles, 'TopSkyAreas.txt')

def CPDLC():
    CPDLCFiles = ImportFileIndex('CPDLC/')
    Remove('TopSkyCPDLC.txt')
    Construct('CPDLC/', CPDLCFiles, 'TopSkyCPDLC.txt')
    CopyAll('CPDLC/Hoppie Code.txt', 'TopSkyCPDLChoppieCode.txt')

def Maps():
    MapsFiles = ImportFileIndex('Maps/')
    Remove('TopSkyMaps.txt')
    Construct('Maps/', MapsFiles, 'TopSkyMaps.txt')

def MSAW():
    MSAWFiles = ImportFileIndex('MSAW/')
    Construct('MSAW/', MSAWFiles, 'TopSkyMSAW.txt')

def Radars():
    RadarFiles = ImportFileIndex('Radars/')
    Remove('TopSkyRadars.txt')
    Construct('Radars/', RadarFiles, 'TopSkyRadars.txt')
#endregion

#region Commom construction methods
def Remove(FileName): # Removes specified file across iTEC, NERC, NODE, and NOVA (if it exists)
    if os.path.exists(iTEC_Path + FileName): os.remove(iTEC_Path + FileName)
    else: print('File ' + iTEC_Path + FileName + ' does not exist!')
    if os.path.exists(NERC_Path + FileName): os.remove(NERC_Path + FileName)
    else: print('File ' + NERC_Path + FileName + ' does not exist!')
    if os.path.exists(NODE_Path + FileName): os.remove(NODE_Path + FileName)
    else: print('File ' + NODE_Path + FileName + ' does not exist!')
    if os.path.exists(NOVA_Path + FileName): os.remove(NOVA_Path + FileName)
    else: print('File ' + NOVA_Path + FileName + ' does not exist!')
    if os.path.exists(MIL_Path + FileName): os.remove(MIL_Path + FileName)
    else: print('File ' + MIL_Path + FileName + ' does not exist!')

def CopyAll(InputFileName, OutputFileName): # Copies specified file from shared data (if it exists) to iTEC, NERC, NODE, and NOVA with the new filename
    if os.path.exists(Shared_Path + InputFileName):
        shutil.copy(Shared_Path + InputFileName, iTEC_Path + OutputFileName)
        shutil.copy(Shared_Path + InputFileName, NERC_Path + OutputFileName)
        shutil.copy(Shared_Path + InputFileName, NODE_Path + OutputFileName)
        shutil.copy(Shared_Path + InputFileName, NOVA_Path + OutputFileName)
        shutil.copy(Shared_Path + InputFileName, MIL_Path + OutputFileName)
    else:
        print('File ' + Shared_Path + InputFileName + ' does not exist!')

def Construct(Folder, Files, Output):
    with open(iTEC_Path + Output, 'wb') as OutputFile: # Make output in iTEC
        for File in Files:
            with open(Shared_Path + Folder + File, 'rb') as InputFile:
                shutil.copyfileobj(InputFile, OutputFile)
                OutputFile.write(b'\n\n') # 2 new lines required to append a blank line at the end of each individual file
    
    # Copy output from iTEC to NERC, NODE, and NOVA - more efficient
    shutil.copy(iTEC_Path + Output, NERC_Path + Output)
    shutil.copy(iTEC_Path + Output, NODE_Path + Output)
    shutil.copy(iTEC_Path + Output, NOVA_Path + Output)
    shutil.copy(iTEC_Path + Output, MIL_Path + Output)

def ImportFileIndex(Folder):
    Files = []
    with open(Shared_Path + Folder + Index_Name) as Index:
        for Entry in Index:
            if '//' in Entry: # Remove comments
                Entry = Entry.split('//')[0]
            if not Entry.strip() == '' and '.' in Entry: # Check needed when comment is taking full line and validates for a potential file extension
                Files.append(Entry.strip())
            elif not Entry.strip() == '':
                print('Entry ' + Entry + ' in ' + Shared_Path + Folder + Index_Name + ' has been excluded!')
    return Files
#endregion

def ChangeMilDangerAreaDefinition():
    with open(MIL_Path + 'TopSkyAreas.txt', 'r') as File:
        Contents = File.readlines()
    
    Replaced = False
    
    with open(MIL_Path + 'TopSkyAreas.txt', 'w') as File:
        for Line in Contents:
            if (not Replaced): # Force boolean check first to hopefully reduce performance impact
                if (Line.find('CATEGORYDEF:DANGER') > -1):
                    Elements = Line.split(':')
                    Elements[4] = '50' # 50 to be the closest to a proper overlay rather than anything else. Slightly obscures labels, but strikes the best balance.
                    Line = ':'.join(Elements)
                    File.write(Line)
                    Replaced = True
                else:
                    File.write(Line)
            else:
                File.write(Line)
    
    if (not Replaced):
        print('Mil active danger area fill settings not changed!')
    return

if __name__ == '__main__':
    main()
