"""
Script to combine a suitable subset of the 
cleaned crime data to weather variables.
Mapping from lat lon to the 1km grid
"""

# to pull in the separate data sources run:
# - get_crime_data.py 
# - haduk_month_download.py

# A sensible subset of data is posts 2016 (when Athena was introduced)


###########################################################
# %% Import modules
from _duckdb import DuckDBPyConnection
import os
import duckdb
from pathlib import Path
import duckdb


#####################################################################
#
# Step One: Open a subset of crime data
# (this forms the base of out new data table)
#
#####################################################################

############################################################
# %% Setup directories and paths
cwd: str = os.getcwd()
crime_data_dir: Path = Path(cwd) / 'data' / 'police_archives'
crime_db: Path = crime_data_dir/'crime_archive.db'



# %%
# set up duck db connection
con: DuckDBPyConnection = duckdb.connect(database=crime_db)

# introspect
con.execute(query="SHOW TABLES").fetchall()
con.execute(query="SELECT * FROM street_data LIMIT 5;").df()

# %%
#TODO: just want data spanning 2016-01 to 2025-12
# TODO: drop unnecessary columns