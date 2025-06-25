import os
import shutil

# Whilst all data changes are constructed, only when the data files are changed will the result be committed
# When files need conjoining, iTEC is used as the working directory, and data files are copied across to NERC, NODE, and NOVA directories
iTEC_Path = 'UK/Data/Plugin/TopSky_iTEC/'
NERC_Path = 'UK/Data/Plugin/TopSky_NERC/'
NODE_Path = 'UK/Data/Plugin/TopSky_NODE/'
NOVA_Path = 'UK/Data/Plugin/TopSky_NOVA/'
Shared_Path = '.data/TopSky Shared/'

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

#region Split datafile construction
def Areas():
    AreaFiles = ImportFileIndex('Areas/')
    Remove('TopSkyAreas.txt')
    Construct('Areas/', AreaFiles, 'TopSkyAreas.txt')

def CPDLC():
    CPDLCFiles = ImportFileIndex('CPDLC/')
    Remove('TopSkyCPDLC.txt')
    Construct('CPDLC/', CPDLCFiles, 'TopSkyCPDLC.txt')
    CopyAll('Hoppie Code.txt', 'TopSkyCPDLChoppieCode.txt')

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
    if os.path.exists(iTEC_Path + FileName):
        os.remove(iTEC_Path + FileName)
    if os.path.exists(NERC_Path + FileName):
        os.remove(NERC_Path + FileName)
    if os.path.exists(NODE_Path + FileName):
        os.remove(NODE_Path + FileName)
    if os.path.exists(NOVA_Path + FileName):
        os.remove(NOVA_Path + FileName)

def CopyAll(InputFileName, OutputFileName): # Copies specified file from shared data (if it exists) to iTEC, NERC, NODE, and NOVA with the new filename
    if os.path.exists(Shared_Path + InputFileName):
        shutil.copy(Shared_Path + InputFileName, iTEC_Path + OutputFileName)
        shutil.copy(Shared_Path + InputFileName, NERC_Path + OutputFileName)
        shutil.copy(Shared_Path + InputFileName, NODE_Path + OutputFileName)
        shutil.copy(Shared_Path + InputFileName, NOVA_Path + OutputFileName)

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

def ImportFileIndex(Folder):
    Files = []
    with open(Shared_Path + Folder + '.Index.txt') as Index:
        for Entry in Index:
            if '//' in Entry: ## Remove comments
                Entry = Entry.split('//')[0]
            if not Entry.strip() == '' and '.' in Entry: ## Check needed when comment is taking full line and validates for a potential file extension
                Files.append(Entry.strip())
    return Files
#endregion

if __name__ == '__main__':
    main()
