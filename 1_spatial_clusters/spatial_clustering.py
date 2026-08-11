#######################################################################
# This script is deigned to be used with conda env
# crime_weather env
#
# Code for creating spatial clusters 
# utilising HDBScan
#
#######################################################################


# %% import standard modules
from _duckdb import DuckDBPyConnection
from pathlib import Path
import os
import duckdb



############################################################
# %% Setup directories and paths
cwd: str = os.getcwd()
data_dir: Path = Path(cwd).parent / 'data' / 'police_archives'
crime_db: Path = data_dir/'crime_archive.db'

# %%

# %%
# set up duck db connection
con: DuckDBPyConnection = duckdb.connect(database=crime_db)

# introspect
con.execute(query="SHOW TABLES").fetchall()

# head
con.execute(query="SELECT * FROM crimetology_NS_clean LIMIT 5;").df()

## expect this to be 1255500
con.execute(query="SELECT COUNT(*) FROM crimetology_NS_clean LIMIT 5;").df()

# %%
# Only need lat and lon pairs to cluster over. 
