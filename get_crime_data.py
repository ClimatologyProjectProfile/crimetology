#######################################################################
# This script is deigned to be used with conda env
# crime_weather env
#
# Script to download UK police crime data from 
# the official rolling archive
#  
# Script is in two halves - first downloads and unzips new archive data, 
# second ingests into local duckdb database.
# 
#  ! Initial run is slow - duckdb method here is inefficient for 
#  large data sets, but it is a simple approach to get started.   
#  Needs to be improved for future runs/batched.
#######################################################################


###########################################################
# %% Import modules
import zipfile
import time
import glob
import os
import duckdb
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path


###########################################################
# %%User Inputs 
get_data = False
del_archive_zips = True

############################################################
# %% Setup directories and paths
# Create a data directory if it doesn't exist
# Get the current working directory
cwd = os.getcwd()

#data dir for archives downloads (zips)
data_dir = Path(cwd) / 'data' / 'police_archives'
data_dir.mkdir(parents=True, exist_ok=True)

# set the unzip location
out_dir = Path(cwd) / 'data' / 'police_archives' / 'csvs'
out_dir.mkdir(parents=True, exist_ok=True)

# create a log file to track which csvs
# have been added to the duckdb
log_file = data_dir / 'ingested_csvs.txt'

# archived data location (where to source zips from)
base_url = "https://data.police.uk/data/archive/"

# ===============================================================================================#
# %% Load in Download function

## Helper Function
## Only download needed data
def is_already_processed(file_name):
    """Check if the file has been processed in a previous run."""
    if not os.path.exists(log_file):
        return False
    with open(log_file, 'r') as f:
        processed = f.read().splitlines()
        # if processed already return True, else False
    return file_name in processed

## set up download function
headers = {'User-Agent': 'StreetDataDownloader/1.0 (github.com/ClimatologyProjectProfile)'}

## Download function
def download_archives(out_dir:Path):
    print(f"Connecting to {base_url}...")
    response = requests.get(base_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all links ending in .zip
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.endswith('.zip'):
            file_url = urljoin(base_url, href)
            # get the file name from the URL with *.zip suffix
            download_file_name = href.split('/')[-1]
            # isolate just the stem (i.e. file name)
            file_stem = Path(download_file_name).stem
            # ignore the nerighbourhood and latest data zips
            if 'neighbourhood' in file_stem or 'latest' in file_stem:
                print(f"Skipping {download_file_name}, not a street data archive.")
                continue

            # now see if the data has been added to duckdb before
            if is_already_processed(file_stem):
                print(f"Skipping {download_file_name}, already ingested.")
            else:
                # file has not been unzipped yet, so download it
                download_path = data_dir / download_file_name
                print(f"Downloading {download_file_name}...")
                try:
                    # stream=True is more efficient for large ZIP files
                    with requests.get(file_url, headers=headers, stream=True) as r:
                        r.raise_for_status() # Check for errors
                        with open(download_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    print(f"Finished {download_file_name}")
                except Exception as e:
                    print(f"Failed to download {download_file_name}: {e}")



# %% Run download function and unzip as we go

if get_data:
    # get any new zip files available from the archive site
    # checking against previously unzipped downloads in 
    # 'out_dir'
    print('----------------------------------------------')
    print(f"Checking for new archive files to download...")
    download_archives(out_dir)
    print('----------------------------------------------')
    # now unzip any downloads 
    print(f"Processing archive files in {data_dir}...")

    # Find all zip files
    zip_files = glob.glob(os.path.join(data_dir, "*.zip"))

    if not zip_files:
        print("No zip files found to process.")

    for zip_file_path in zip_files:
        try:
            print(f"Extracting {os.path.basename(zip_file_path)}...")
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(out_dir)
            
            # Successfully extracted, now safely remove
            if del_archive_zips:
                os.remove(zip_file_path)
                print(f"Successfully extracted and removed {os.path.basename(zip_file_path)}")
            
        except zipfile.BadZipFile:
            print(f"Error: {os.path.basename(zip_file_path)} is corrupted. Skipping.")
        except Exception as e:
            print(f"An unexpected error occurred with {os.path.basename(zip_file_path)}: {e}")

    print('----------------------------------------------')
    print('Finished processing archive files.')
    print('----------------------------------------------')

    

# ===============================================================================================#
# %%  Duck DB update routine
# Ingest archived data into local duckdb database

## Helper Functions
def is_already_processed(file_name):
    """Check if the file has been processed in a previous run."""
    if not os.path.exists(log_file):
        return False
    with open(log_file, 'r') as f:
        processed = f.read().splitlines()
        # if processed already return True, else False
    return file_name in processed

def mark_as_processed(file_name):
    """Record a file as processed."""
    with open(log_file, 'a') as f:
        f.write(f"{file_name}\n")

def initialize_database(con, example_file_path:str|os.PathLike):    
    # Create the table if it doesn't exist
    # LIMIT 0 == get the column headers/types without importing data
    con.execute(f"""CREATE TABLE IF NOT EXISTS street_data AS 
                    SELECT * FROM read_csv_auto('{example_file_path}') LIMIT 0""")
    # Add index for efficient lookups on Crime_ID
    con.execute("""CREATE INDEX IF NOT EXISTS idx_crime_id ON street_data("Crime ID")""")

def update_duckdb(csv_paths:list[str|os.PathLike]):
    # put database at top level of data_dir
    con = duckdb.connect(data_dir/'crime_archive.db')
    # create the datatable if it doesn't exist  
    # Use the first CSV to initialize the table structure
    initialize_database(con, csv_paths[0]) 
    # Now ingest data from each CSV, skipping those already logged
    for csv_path in csv_paths:
        file_name = os.path.basename(csv_path)
        
        # Skip if already logged
        if is_already_processed(file_name):
            continue
            
        print(f"Ingesting {file_name}...")
        try:
            # use union by name incase the schema changes slightly between files (e.g., new columns added)
            con.execute(f"""INSERT INTO street_data
                            SELECT * FROM read_csv_auto('{csv_path}', union_by_name=True) AS new_data
                            WHERE NOT EXISTS (SELECT 1 FROM street_data AS main 
                                              WHERE main."Crime ID" = new_data."Crime ID")
                        ;""")
        
            # Only log success AFTER database update is complete
            print(f"Processed {file_name}...")
            # pause, dont hammer the server because that is just rude. 
            time.sleep(2)
            mark_as_processed(file_name)
        except Exception as e:
            print(f"Failed to process {file_name}: {e}")
            # pause, as above. 
            time.sleep(2)
    # finish up by closing the connection
    con.close()


# Now run duckdb update on all csvs in out_dir
# checking against the log file to avoid duplicates

# find all *-street.csv files in the out_dir and its subdirectories
csv_files_list = glob.glob(os.path.join(data_dir, "**", "*-street.csv"), recursive=True)

## Run database update
print("Found "+str(len(csv_files_list))+" csv files")

# %%  Duck DB update routine

# Run Update (only is new csvs are found)
if len(csv_files_list) > 0:
    print("Updating duckdb database with new csv files...")
    update_duckdb(csv_files_list)
    print("=== Finished updating duckdb database ===")

# ===============================================================================================#


