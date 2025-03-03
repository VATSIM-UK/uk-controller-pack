import glob

def insert_plugins_after_WINDOWAREA_line():
    plugin_lines = [
        "PLUGIN:RDF Plugin for Euroscope:Radius:20",
        "PLUGIN:RDF Plugin for Euroscope:Threshold:-1",
        "PLUGIN:RDF Plugin for Euroscope:Precision:0",
        "PLUGIN:RDF Plugin for Euroscope:LowAltitude:0",
        "PLUGIN:RDF Plugin for Euroscope:LowPrecision:50",
        "PLUGIN:RDF Plugin for Euroscope:DrawControllers:0",
    ]
    
    # Recursive glob search for files ending with 'SMR.asr'
    for file_path in glob.glob("**/*SMR.asr", recursive=True):
        print(f"Processing file: {file_path}")
        
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        new_lines = []
        inserted = False
        
        for line in lines:
            new_lines.append(line)
            if line.lstrip().startswith("WINDOWAREA"):
                for p_line in plugin_lines:
                    new_lines.append(p_line + "\n")
                inserted = True
        
        # Write updated content back to the file
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        
        if inserted:
            print(f"Inserted plugin lines into {file_path}")
        else:
            print(f"No line starting with 'WINDOWAREA' found in {file_path}; nothing inserted.")


if __name__ == "__main__":
    insert_plugins_after_WINDOWAREA_line()
