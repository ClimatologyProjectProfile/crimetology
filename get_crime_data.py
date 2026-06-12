test push
#######################################################################
# Script to download UK police crime data from 
# Kaggle and the official rolling archive,
# consolidate it using DuckDB, and export 
# a clean Parquet file for analysis.    
#######################################################################


###########################################################
# %% Import modules
import os
import duckdb
import kaggle

# Note: kaggle credential need to be set up  
# in ~/.kaggle/access_token

############################################################
# %%
# Create a data directory if it doesn't exist
os.makedirs('data', exist_ok=True)


# --- 2. DOWNLOAD HISTORICAL DATA FROM KAGGLE API ---
print("Downloading historical data via Kaggle API...")
# This downloads the mexwell/uk-police-data dataset and automatically unzips it
kaggle.api.dataset_download_files(
    'mexwell/uk-police-data', 
    path='data/kaggle_uk_police', 
    unzip=True
)
print("Kaggle download and extraction complete!")


# --- 3. DUCKDB CONSOLIDATION PIPELINE ---
print("\nInitializing DuckDB engine...")
con = duckdb.connect('crime_weather.db')

# Install and load the httpfs extension so DuckDB can read URLs directly
con.execute("INSTALL httpfs; LOAD httpfs;")

# URL format for data.police.uk rolling 3-year archives
# We can dynamically target the latest file (e.g., '2024-12.zip' or similar)
latest_archive_url = "https://data.police.uk/data/archive/2024-12.zip"

print(f"Streaming and merging data from official rolling archive URL and local Kaggle files...")

# SQL Query that streams from the web AND reads the local extracted Kaggle files,
# uses UNION to drop duplicates, filters out null coordinates, and maps street records.
build_query = f"""
CREATE OR REPLACE VIEW unified_crime_raw AS

-- Source A: Official rolling archive streamed directly over HTTP
SELECT 
    "Month" AS month,
    "Crime type" AS crime_type,
    CAST("Latitude" AS DOUBLE) AS lat,
    CAST("Longitude" AS DOUBLE) AS lon
FROM read_csv_auto('{latest_archive_url}/**/*.csv')
WHERE "Latitude" IS NOT NULL 
  AND "Longitude" IS NOT NULL
  AND File_Name LIKE '%street%'

UNION

-- Source B: Historical Kaggle files downloaded via API
SELECT 
    "Month" AS month,
    "Crime type" AS crime_type,
    CAST("Latitude" AS DOUBLE) AS lat,
    CAST("Longitude" AS DOUBLE) AS lon
FROM read_csv_auto('data/kaggle_uk_police/**/*.csv')
WHERE "Latitude" IS NOT NULL 
  AND "Longitude" IS NOT NULL
  AND File_Name LIKE '%street%';
"""

con.execute(build_query)
print("Unified dataset compiled in memory. Exporting to Parquet...")

# Export sorted dataset to Parquet
con.execute("""
    COPY (
        SELECT month, crime_type, lat, lon 
        FROM unified_crime_raw
        ORDER BY month, crime_type
    ) TO 'combined_crime_data.parquet' (FORMAT PARQUET);
""")

print("Success! 'combined_crime_data.parquet' is ready.")


# --- 4. VERIFY RESULTS ---
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