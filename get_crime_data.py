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

###########################################################
# %%User Inputs 
get_data = False
del_archive_zips = True


############################################################
# %%
# Create a data directory if it doesn't exist
# Get the current working directory
cwd = os.getcwd()

data_dir = cwd+'/data/police_archives/'
os.makedirs(data_dir, exist_ok=True)

base_url = "https://data.police.uk/data/archive/"

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def download_archives():
    print(f"Connecting to {base_url}...")
    response = requests.get(base_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all links ending in .zip
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.endswith('.zip'):
            file_url = urljoin(base_url, href)
            file_name = href.split('/')[-1]
            file_path = os.path.join(data_dir, file_name)

            if not os.path.exists(file_path):
                print(f"Downloading {file_name}...")
                try:
                    # stream=True is more efficient for large ZIP files
                    with requests.get(file_url, headers=headers, stream=True) as r:
                        r.raise_for_status() # Check for errors
                        with open(file_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                    print(f"Finished {file_name}")
                except Exception as e:
                    print(f"Failed to download {file_name}: {e}")
            else:
                print(f"Skipping {file_name}, already exists.")

if get_data:
    download_archives()
#time taken to run (12/06/2026): 1.5 hrs

# unzip the files, as duckdb couldnt sniff them....
if get_data:
    zip_dir = data_dir
    out_dir = cwd+'/data/police_archives_csvs/'
    for zip_file in glob.glob(os.path.join(zip_dir, "*.zip")):
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(out_dir)
#time taken to run (12/06/2026): inf.... manual interrupt. 


if del_archive_zips:
    for file_name in os.listdir(data_dir):
        if file_name.endswith('.zip'):
            file_path = os.path.join(data_dir, file_name)
            os.remove(file_path)
            print(f"Deleted {file_name}")

#TODO - turns csv files into parquet, and then delete the csv files and zips.


###########################################################
# %% make a local duckDB
print("Initializing DuckDB engine...")
con = duckdb.connect('data/crime_archive.db')


# data desc is here: https://data.police.uk/about/#columns

#HERE - need to now open and read the 
# zipped data files, and combine them into a single table

sniffer_result = con.sql(f"SELECT * FROM sniff_csv("str(data_dir)+"'2025-04.zip').fetchone()

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