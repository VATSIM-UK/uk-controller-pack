import os
import json

directory = os.getcwd()
json_files = [f for f in os.listdir(directory) if f == "UK - Swanwick.json"]

for file_name in json_files:
    file_path = os.path.join(directory, file_name)
    with open(file_path, 'r') as file:
        data = json.load(file)
        print(f"Contents of {file_name}:")
        print(data.keys())
        newData = {}
        newData['Name'] = data['Name']
        newData['updateUrl'] = f"https://raw.githubusercontent.com/VATSIM-UK/uk-controller-pack/refs/heads/main/_vATIS/{file_name}"
        newData['updateSerial'] = 2025021401
        newData['stations'] = []
        for station in data['Composites']:
            print(f"Updating {station['Name']}")
            newStation = {}
            newStation['Name'] = station['Name']
            newStation['Identifier'] = station['Identifier']
            newStation['contractions'] = station['Contractions']
            newStation['AtisFrequency'] = station['AtisFrequency']
            newStation['AtisVoice'] = station['AtisVoice']
            if "IDSEndpoint" in station.keys():
                newStation['IDSEndpoint'] = station['IDSEndpoint']
            else:
                newStation['IDSEndpoint'] = None
            newStation['useNotamPrefix'] = False
            newStation['useDecimalTerminology'] = True
            newStation['Presets'] = station['Presets']
            newStation['AirportConditionDefinitions'] = station['AirportConditionDefinitions']
            newStation['notamDefinitions'] = station['NotamDefinitions']

            # newFormat = {}
            # atisFormat = station['atisFormat']
            # newFormat['altimeter'] = atisFormat['altimeter']
            # newFormat['transitionLevel'] = atisFormat['transitionLevel']
            # if "closingStatement" in atisFormat.keys():
                # newFormat['closingStatement'] = atisFormat['closingStatement']
            # newStation['atisFormat'] = newFormat

            newData['stations'].append(newStation)

            


    with open(file_path, 'w')as file:
        json.dump(newData, file, indent=4)
