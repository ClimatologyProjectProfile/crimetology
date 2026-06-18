#######################################################################
# This script is deigned to be used with conda env
# crime_weather env
#
# Script to download UK police crime data from 
# the official rolling archive
   
#######################################################################


###########################################################
# %% Import modules
import zipfile
import glob
import os
import duckdb
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pathlib import Path


###########################################################
# %%User Inputs 
get_data = True
del_archive_zips = True


############################################################
# %%
# Create a data directory if it doesn't exist
# Get the current working directory
cwd = os.getcwd()

#data dir for archives downloads (zips)
data_dir = Path(cwd) / 'data' / 'police_archives'
data_dir.mkdir(parents=True, exist_ok=True)

# set the unzip location
out_dir = Path(cwd) / 'data' / 'police_archives' / 'csvs'
out_dir.mkdir(parents=True, exist_ok=True)

# archived data location (where to source zips from)
base_url = "https://data.police.uk/data/archive/"


# set up download function
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

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
            # create a pattern to search output directory for unzipped files
            dir_path = out_dir / file_stem 

            # now see if this path exists (meaning that data has been 
            # extracted from the zip file already)
            if dir_path.exists() and dir_path.is_dir():
                print(f"Skipping {download_file_name}, already exists and is unzipped.")
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


# %% Routine to download and unzip any new archive files

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

    


#time taken to run (12/06/2026): 1.5 hrs
#time taken to run (12/06/2026): inf.... manual interrupt. 

#TODO - turns csv files into parquet, and then delete the csv files and zips.


###########################################################
# %% make a local duckDB
print("Initializing DuckDB engine...")
con = duckdb.connect('data/crime_archive.db')


# data desc is here: https://data.police.uk/about/#columns

#HERE - need to now open and read the 
# zipped data files, and combine them into a single table


con.sql("""
SELECT * FROM read_csv('"""+str(data_dir)+"""2025-04.zip');
""")

con.sql(f"""
    SELECT * FROM read_csv(
        '{data_dir}2025-04.zip', 
        header=True, 
        delim=',', 
        quote='"',
        sample_size=-1  -- Force it to read the whole file to detect types
    );
""")

# get all the data into a single table
con.sql("""
CREATE OR REPLACE TABLE all_crime_data AS 
SELECT 
    date, 
    "Crime type" as crime_type, 
    latitude as lat, 
    longitude as lon
FROM read_csv_auto('""" + str(data_dir) + """*.zip/*.csv', union_by_name=True)
WHERE latitude IS NOT NULL
""")





# %%
summary = con.execute("""
    SELECT 
        MIN(month) as earliest_month, 
        MAX(month) as latest_month, 
        COUNT(*) as total_crimes 
    FROM 'combined_crime_data.parquet'
""").fetchall()

print(f"\nFinal Dataset Summary:")
print(f"Time Range: {summary[0][0]} to {summary[0][1]}")
print(f"Total Rows Processed: {summary[0][2]:,}")