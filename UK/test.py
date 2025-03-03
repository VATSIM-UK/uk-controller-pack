import glob
import os

def insert_rdf_plugins_after_PLUGINS_line():
    rdf_plugin_lines = [
        "RDF Plugin for Euroscope:LogLevel:none",
        "RDF Plugin for Euroscope:Bridge:1",
        "RDF Plugin for Euroscope:Endpoint:127.0.0.1:49080",
        "RDF Plugin for Euroscope:EnableDraw:0",
        "RDF Plugin for Euroscope:RGB:255:255:255",
        "RDF Plugin for Euroscope:ConcurrentTransmissionRGB:255:0:0",
        "RDF Plugin for Euroscope:Radius:10",
        "RDF Plugin for Euroscope:Threshold:10",
        "RDF Plugin for Euroscope:Precision:10",
        "RDF Plugin for Euroscope:LowAltitude:2500",
        "RDF Plugin for Euroscope:HighAltitude:15000",
        "RDF Plugin for Euroscope:LowPrecision:10",
        "RDF Plugin for Euroscope:HighPrecision:5",
        "RDF Plugin for Euroscope:DrawControllers:0"
    ]
    
    # Search for files that end with "Plugins.txt" in the current directory and all subdirectories
    for file_path in glob.glob("**/*Plugins.txt", recursive=True):
        print(f"Processing file: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        new_lines = []
        inserted = False
        
        for line in lines:
            new_lines.append(line)
            if line.strip() == "PLUGINS":
                for rdf_line in rdf_plugin_lines:
                    new_lines.append(rdf_line + "\n")
                inserted = True
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        
        if inserted:
            print(f"Inserted RDF plugin lines into {file_path}")
        else:
            print(f"No exact 'PLUGINS' line found in {file_path}; no lines inserted.")

if __name__ == "__main__":
    insert_rdf_plugins_after_PLUGINS_line()
