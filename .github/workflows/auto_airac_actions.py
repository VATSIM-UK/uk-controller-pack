"""
UKCP Updater
Chris Parkinson (@chssn)
"""

#!/usr/bin/env python3

# Standard Libraries
import datetime
import os
import re
from math import floor

# Third Party Libraries
import py7zr
import requests
from loguru import logger

# Local Libraries

class Airac:
    """Class for general functions relating to AIRAC"""

    def __init__(self):
        # First AIRAC date following the last cycle length modification
        start_date = "2019-01-02"
        self.base_date = datetime.date.fromisoformat(str(start_date))
        # Length of one AIRAC cycle
        self.cycle_days = 28
        # Today
        self.today_date = datetime.datetime.now().date()

    def initialise(self, date_in:str=0) -> int:
        """Calculate the number of AIRAC cycles between any given date and the start date"""
        if date_in:
            input_date = datetime.date.fromisoformat(str(date_in))
        else:
            input_date = datetime.date.today()

        # How many AIRAC cycles have occured since the start date
        diff_cycles = (input_date - self.base_date) / datetime.timedelta(days=1)
        # Round that number down to the nearest whole integer
        number_of_cycles = floor(diff_cycles / self.cycle_days)
        logger.debug(f"{number_of_cycles} AIRAC cycles since {input_date}")

        return number_of_cycles

    def current_cycle(self) -> str:
        """Return the date of the current AIRAC cycle"""
        def cycle(sub:int=0):
            number_of_cycles = self.initialise() - sub
            number_of_days = number_of_cycles * self.cycle_days + 1
            current_cycle = self.base_date + datetime.timedelta(days=number_of_days)
            return current_cycle

        current_cycle = cycle()
        if current_cycle > self.today_date:
            current_cycle = cycle(sub=1)

        logger.info("Current AIRAC Cycle is: {}", current_cycle)

        return str(current_cycle)

    def current_tag(self) -> str:
        """Returns the current tag for use with git"""
        current_cycle = self.current_cycle()
        # Split the current_cycle by '-' and return in format yyyy/mm
        split_cc = str(current_cycle).split("-")
        logger.debug(f"Current tag should be {split_cc[0]}/{split_cc[1]}")

        return f"{split_cc[0]}/{split_cc[1]}"


class CurrentInstallation:
    """
    Actions to be carried on the current installation of UKCP
    """

    def __init__(self) -> None:
        self.ukcp_location = "UK"

        # Get the current AIRAC cycle
        airac = Airac()
        self.airac = airac.current_tag()

        # Write the current tag to use as a workflow variable
        with open("airac.txt", "w", encoding="utf-8") as a_file:
            a_file.write(self.airac)

        # Sector file base URL
        self.sector_url = "http://www.vatsim.uk/files/sector/esad/"

    def apply_settings(self) -> bool:
        """Applies settings to relevant files"""

        def iter_files(ext:str, file_mode:str):
            """Iterate over files in the directory and search within each file"""
            def decorator_func(func):
                def wrapper(*args, **kwargs):
                    for root, dirs, files in os.walk(self.ukcp_location):
                        for file_name in files:
                            if file_name.endswith(ext):
                                file_path = os.path.join(root, file_name)
                                logger.debug(f"Found {file_path}")
                                with open(file_path, file_mode, encoding="utf-8") as file:
                                    lines = file.readlines()
                                    file.seek(0)
                                    func(lines, file, file_path, *args, **kwargs)
                return wrapper
            return decorator_func

        def get_sector_file() -> str:
            """Get the sector file name"""

            sector_file = []
            sector_fn = []
            for root, dirs, files in os.walk(self.ukcp_location):
                for file_name in files:
                    if file_name.endswith(".sct"):
                        sector_file.append(os.path.join(root, file_name))
                        sector_fn.append(file_name)

            if len(sector_file) == 1 and len(sector_fn) == 1:
                logger.info(f"Sector file found at {sector_file[0]}")

                # Check the sector file matches the current AIRAC cycle
                airac_format = str(self.airac.replace("/", "_"))
                if airac_format not in sector_file[0]:
                    logger.warning(f"Your sector file appears out of date with the current {self.airac} release!")
                    # Download the latest file
                    url = f"{self.sector_url}UK_{airac_format}.7z"
                    logger.debug(f"Sector file url {url}")
                    sector_7z = requests.get(url, timeout=30)

                    # Write it to local file
                    file_path = f"UK_{airac_format}.7z"
                    with open(file_path, "wb") as file:
                        file.write(sector_7z.content)

                    # Extract the contents of the archive
                    with py7zr.SevenZipFile(file_path, mode="r") as archive:
                        archive.extractall(path=f"{self.ukcp_location}/Data/Sector")

                    # Clean up artifacts
                    os.remove(file_path)
                    # Clean up old sector files
                    ext = ["ese", "rwy", "sct"]
                    logger.debug(f"Sector file name{sector_fn}")
                    for e_type in ext:
                        os.remove(f"{self.ukcp_location}/Data/Sector/{str(sector_fn[0]).split('.', maxsplit=1)[0]}.{e_type}")

                    # Return the newly downloaded sector file
                    return str(f"{self.ukcp_location}/Data/Sector/UK_{airac_format}.sct")
                return str(sector_file[0])
            else:
                logger.error(f"Sector file search found {len(sector_file)} files. You should only have one of these!")
                logger.debug(sector_file)
                raise ValueError(f"{len(sector_file)} sector files were found when there should only be one")

        sct_file = get_sector_file()
        sct_file_split = sct_file.split("/")

        @iter_files(".asr", "r+")
        def asr_sector_file(lines=None, file=None, file_path=None):
            """Updates all 'asr' files to include the latest sector file"""

            sector_file = f"SECTORFILE:{sct_file}"
            sector_title = f"SECTORTITLE:{sct_file_split[-1]}"

            sf_replace = sector_file.replace("/", "\\\\")

            chk = False
            for line in lines:
                # Add the sector file path
                content = re.sub(r"^SECTORFILE\:(.*)", sf_replace, line)

                # If no replacement is made then try the sector title
                if content == line:
                    content = re.sub(r"^SECTORTITLE\:(.*)", sector_title, line)

                if content != line:
                    chk = True

                # Write the updated content back to the file
                file.write(content)
            file.truncate()

            # If no changes have been made, add the SECTORFILE and SECTORTITLE lines
            if not chk:
                file.close()
                with open(file_path, "a", encoding="utf-8") as file_append:
                    file_append.write(sector_file + "\n")
                    file_append.write(sector_title + "\n")

        @iter_files(".prf", "r+")
        def prf_files(lines=None, file=None, file_path=None):
            """Updates all 'prf' files to include the latest sector file"""

            sector_file = f"Settings\tsector\t{sct_file}"

            sf_replace = sector_file.replace("/", "\\\\")

            for line in lines:
                # Add the sector file path
                content = re.sub(r"^Settings\tsector\t(.*)", sf_replace, line)

                # Write the updated content back to the file
                file.write(content)
            file.truncate()

        logger.info("Updating references to SECTORFILE and SECTORTITLE")
        asr_sector_file()
        prf_files()

run = CurrentInstallation()
run.apply_settings()