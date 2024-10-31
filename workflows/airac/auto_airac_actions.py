#!/usr/bin/env python3

# Standard Libraries
import datetime
import json
import os
import re
import shutil
from math import floor
from zipfile import ZipFile

# Third Party Libraries
import requests
from loguru import logger

# Local Libraries


class Airac:
    """ A valid AIRAC cycle. """

    # reference cycle date: any valid AIRAC start date
    CYCLE_REFERENCE = datetime.date.fromisoformat("2020-01-02")
    # AIRAC cycle length in days
    CYCLE_LENGTH    = 28

    def __init__(self, date: str | None = None):
        if date is None:
            date = datetime.datetime.now().date()
        else:
            date = datetime.date.fromisoformat(date)

        ref_delta = (date - Airac.CYCLE_REFERENCE).days // Airac.CYCLE_LENGTH
        ref_delta = datetime.timedelta(ref_delta * Airac.CYCLE_LENGTH)
        self.start_date = Airac.CYCLE_REFERENCE + ref_delta

        day_of_year = self.start_date.timetuple().tm_yday
        self.cycle_number = (day_of_year - 1) // Airac.CYCLE_LENGTH + 1

    def cycle(self) -> str:
        return f"{self.start_date.year % 100:02}{self.cycle_number:02}"

    def tag(self) -> str:
        return f"{self.start_date.year}/{self.cycle_number:02}"


class CurrentInstallation:
    """
    Actions to be carried on the current installation of UKCP
    """

    def __init__(self) -> None:
        self.ukcp_location = "UK"

        # Get the current AIRAC cycle
        self.airac = Airac().tag()

        # Write the current tag to use as a workflow variable
        with open("airac.txt", "w", encoding="utf-8") as a_file:
            a_file.write(self.airac)

        # Set some other vars
        self.remote_repo_owner = "VATSIM-UK"
        self.remote_repo_name = "UK-Sector-File"

    def gng_data_update(self) -> None:
        """Pulls data from GNG"""

        # Load the EGXX file list and use regex to search for all relevant zip file urls
        try:
            webpage = requests.get("https://files.aero-nav.com/EGXX", timeout=30)
        except requests.exceptions.ReadTimeout as error:
            logger.warning(f"Unable to update to GNG data due to the following error: {error}")
            return True

        if webpage.status_code == 200:
            list_zip_files = re.findall(
                (r"https\:\/\/files\.aero-nav\.com\/EGTT\/"
                 r"UK\-Datafiles\_[\d]{14}\-[\d]{6}\-[\d]{1,2}\.zip"), str(webpage.content))
        else:
            raise requests.HTTPError(f"URL not found - {webpage.url}")

        # We're only interested in the most recent zip file found.
        logger.debug(f"Full list of found zip file urls: {list_zip_files}")
        zip_file = list_zip_files[-1]
        logger.info(f"Selected zip file url is {zip_file}")

        # Set headers to look like a web browser
        headers = {
            "Sec-Ch-Ua": "",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": "\"\"",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.134 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Referer": "https://files.aero-nav.com/EGXX",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "Connection": "close"
        }
        response = requests.get(zip_file, headers=headers, timeout=30)
        logger.debug(f"Response Status = {response.status_code}")
        if response.status_code == 200:
            with open("navdata.zip", "wb") as file:
                file.write(response.content)
            logger.debug("File navdata.zip has been written")
        else:
            raise requests.HTTPError(f"URL not found - {response.url}")

        # Unzip the file
        with ZipFile("navdata.zip", "r") as zip_ref:
            zip_ref.extractall("import/")
            logger.debug("Extracted navdata.zip")

        # Delete the empty zipfile
        os.remove("navdata.zip")
        logger.debug("Removed navadata.zip")

        # Move artifact files
        list_of_files = [
            "ICAO/ICAO_Aircraft.txt",
            "ICAO/ICAO_Airlines.txt",
            "ICAO/ICAO_Airports.txt",
            "NavData/airway.txt",
            "NavData/icao.txt",
            "NavData/isec.txt"
        ]
        for file in list_of_files:
            shutil.copy(
                f"import/EGTT/{file}",
                f"UK/Data/Datafiles/{file.split('/', maxsplit=1)[-1]}"
            )
            if "ICAO_Airlines" in file:
                # Copy the "ICAO_Airlines.txt" file into the vSMR folder
                shutil.copy(
                    f"import/EGTT/{file}",
                    f"UK/Data/Plugin/vSMR/{file.split('/', maxsplit=1)[-1]}"
                )
            logger.success(f"Moved {file}")

        # Cleanup the import directory
        shutil.rmtree("import/")
        logger.debug("Cleaned up import directory")

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
                    if file_name.endswith(".sct") and file_name.startswith("UK_"):
                        sector_file.append(os.path.join(root, file_name))
                        sector_fn.append(file_name)

            if len(sector_file) == 1 and len(sector_fn) == 1:
                logger.info(f"Sector file found at {sector_file[0]}")

                # Check the sector file matches the current AIRAC cycle
                airac_format = str(self.airac.replace("/", "_"))
                if airac_format not in sector_file[0]:
                    logger.warning(
                        f"Sector file appears out of date with the current {self.airac} release!"
                        )
                    ext = ["ese", "rwy", "sct"]

                    # Get artifact url from VATSIM-UK/UK-Sector-File
                    artifact_list = requests.get(
                        (f"https://api.github.com/repos/{self.remote_repo_owner}/"
                         f"{self.remote_repo_name}/actions/artifacts"), timeout=30)
                    if artifact_list.status_code == 200:
                        al_json = json.loads(artifact_list.content)
                        artifact_url = al_json["artifacts"][0]["archive_download_url"]
                    else:
                        raise requests.HTTPError(f"URL not found - {artifact_list.url}")

                    # Download the file
                    headers = {
                        'Accept': 'application/vnd.github+json',
                        'Authorization': f'Bearer {os.environ["REMOTE_KEY"]}',
                        'X-GitHub-Api-Version': '2022-11-28'
                    }
                    response = requests.get(artifact_url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        with open("sector.zip", "wb") as file:
                            file.write(response.content)
                    else:
                        raise requests.HTTPError(f"URL not found - {artifact_list.url}")

                    # Unzip the file
                    with ZipFile("sector.zip", "r") as zip_ref:
                        zip_ref.extractall(".")

                    # Delete the empty zipfile
                    os.remove("sector.zip")

                    # Rename artifact files
                    logger.debug(f"Sector file name{sector_fn}")
                    for e_type in ext:
                        os.rename(
                            f"UK.{e_type}",
                            f"{self.ukcp_location}/Data/Sector/UK_{airac_format}.{e_type}"
                            )

                    # Clean up old sector files
                    logger.debug(f"Sector file name{sector_fn}")
                    for e_type in ext:

                        path_to_remove = f"{self.ukcp_location}/Data/Sector/{str(sector_fn[0]).split('.', maxsplit=1)[0]}.{e_type}"
                        os.remove(path_to_remove)

                    # Return the newly downloaded sector file
                    return str(f"{self.ukcp_location}/Data/Sector/UK_{airac_format}.sct")
                return str(sector_file[0])
            else:
                logger.error(
                    (f"Sector file search found {len(sector_file)} files. ",
                     "There should only have one of these!"))
                logger.debug(sector_file)
                raise ValueError(
                    f"{len(sector_file)} sector files were found when there should only be one")

        sct_file = get_sector_file()

        @iter_files(".prf", "r+")
        def prf_files(lines=None, file=None, file_path=None):
            """Updates all 'prf' files to include the latest sector file"""

            sector_file = f"Settings\tsector\t{sct_file}"

            sf_replace = sector_file.replace("/", "\\\\")

            chk = False
            for line in lines:
                # Add the sector file path
                content = re.sub(r"^Settings\tsector\t.*UK.+", sf_replace, line)
                chk = True

                # Write the updated content back to the file
                file.write(content.replace("\\\\", "\\"))
            file.truncate()

            # If no changes have been made, add the SECTORFILE and SECTORTITLE lines
            if not chk:
                file.close()
                with open(file_path, "a", encoding="utf-8") as file_append:
                    file_append.write(sf_replace.replace("\\\\", "\\") + "\n")

        prf_files()

run = CurrentInstallation()
run.apply_settings()
run.gng_data_update()
