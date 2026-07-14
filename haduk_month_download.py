"""
Script for downloading HadUK climate data from CEDA. 
Part of the ETL process for the crimetology project.

You will be prompted to provide your CEDA username and password the first time the script is run and
again if the token cached from a previous attempt has expired.
You can check your username here: https://accounts.ceda.ac.uk/realms/ceda/account/#/personal-info
It is case sensitive.

Access tokens can be generated and deleted here: https://services-beta.ceda.ac.uk/account/token/
This script will automatically generate fresh tokens when needed

accessing: https://catalogue.ceda.ac.uk/uuid/789b3065d74a4c948ab05d33556c86d0
info: https://www.metoffice.gov.uk/research/climate/maps-and-data/data/haduk-grid/datasets
"""



# %% import standard modules
from requests.models import Response
from bs4 import BeautifulSoup
import requests
import re
from pathlib import Path
import os

#import custom code
from get_ceda_data import get_file  #code orignally from ceda github
 # reuse code from crime data import (DRY)



# a list of which environmental vars we want
# full list originally, commented out ones to initially skip
var_list: list[str] = [#'airfrost',      # 
                       'groundfrost',   #Count of days when the grass minimum temperature is below 0oC (days)
                       'hurs',          #Mean relative humidity
                       #'psl',           #Mean sea level pressure
                       #'pv',            #Average of hourly (or 3-hourly) vapour pressure over the month, season or year (hPa)
                       #'raindays10mm',  #
                       #'raindays1mm',   #
                       'rainfall',      #Total precipitation amount over the calendar month, season or year (mm)
                       'sfcWind',       #Mean wind speed at 10 m
                       'snowLying',     #Count of days with greater than 50% of the ground covered by snow at 0900 UTC
                       #'summerdays',    #??
                       'sun',           #Duration of bright sunshine during the month, season or year (hours)
                       'tas',           #Average of daily mean air temperature over the calendar month, season or year (oC)
                       'tasmax',        #Average of daily maximum air temperature over the calendar month, season or year (oC)
                       'tasmin']        #Average of daily minimum air temperature over the calendar month, season or year (oC)


# %% Setup directories and paths
cwd: str = os.getcwd()
data_dir: Path = Path(cwd) / 'data' / 'ceda' / 'raw' 
# create a log file to track which cdfs
# have been downloaded
log_file: Path = data_dir / 'dowloaded_cdfs.txt'


# %% Internal helper functions
def _get_files_in_range(soup_obj, start_year:int, end_year:int):
    # Regex date format pattern
    pattern: re.Pattern[str] = re.compile(pattern=r'_(\d{4})\d{2}-\d{4}\d{2}\.nc$')
    # start scooping up files of interest
    selected_files: list = []
    #just links
    for link in soup_obj.find_all('a'):
        href = link.get('href')
        #now start filtering down to what we need
        #1) netcdf files
        if href and href.endswith('.nc'):
            match: re.Match[str] | None = pattern.search(string=href)
            if match:
                # Extract the year contained (via first string match)
                file_year = int(match.group(1))
                # Check in range
                if start_year <= file_year <= end_year:
                    selected_files.append(href)
    return selected_files

def _find_files(var_in:str,start_year,end_year):
    #create download path for variable in
    url_in: str = "https://dap.ceda.ac.uk/badc/ukmo-hadobs/data/insitu/MOHC/HadOBS/HadUK-Grid/v1.3.2.ceda/1km/"+var_in+"/mon/v20260512/"
    # connect to path and pull html containing all links (e.g. downloadable data)
    print(f"Connecting for {var_in}...")
    response: Response = requests.get(url_in)
    #Note: headers not needed as this just looking at files
    # no heavy lifting yet
    soup=BeautifulSoup(markup=response.text, features='html.parser')
    # now filter down to just the files needed
    file_names_list:list= _get_files_in_range(soup,start_year,end_year)
    files_list:list=[url_in+name for name in file_names_list]
    return(files_list)

## create a download log (this is from get_crime_data.py)
## but i didnt make the code nicely enough and I have no 
## clear entry point function to set as __init__ block. 
# TODO ^^
def _is_already_processed(file_name) -> bool:
    """
    Check if the file has been processed in a previous run.
    Returns True is the path is found in the log file
    False if the path is not found in the log file. 
    """
    if not os.path.exists(path=log_file):
        return False
    with open(log_file, mode='r') as f:
        processed: list[str] = f.read().splitlines()
        # if processed already return True, else False
    return file_name in processed

#update the download log
def _mark_as_processed(file_name):
    """Record a file as processed."""
    with open(log_file, mode='a') as f:
        f.write(f"{file_name}\n")

# %%
if __name__ == "__main__":
    # Step One, find all download files
    download_dict:dict={}
    for var in var_list:
        files: list = _find_files(var_in=var,start_year=2016,end_year=2026)
        download_dict[var]=files
    # Step Two, download the raw cdf data
    for var in download_dict.keys():
        for var,link_list in download_dict.items():
            for link in link_list:
                if not _is_already_processed(file_name=link):
                    try:
                        # make sure save loc exists
                        local_dir:Path = data_dir/var
                        local_dir.mkdir(parents=True, exist_ok=True)
                        #attempt to download file
                        result: bool = get_file(url=link,var_id=var,save_loc=local_dir)
                        if result:
                            #successful so add to log
                            _mark_as_processed(file_name=link)
                    #something went wrong so print exception
                    except Exception as e:
                        print(f"An unexpected error occurred: {e}")
