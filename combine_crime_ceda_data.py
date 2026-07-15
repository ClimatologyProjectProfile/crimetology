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
from pandas.core.frame import DataFrame
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

# %% User Inputs
make_table:bool = False



# %%
# set up duck db connection
con: DuckDBPyConnection = duckdb.connect(database=crime_db)

# introspect
con.execute(query="SHOW TABLES").fetchall()
con.execute(query="SELECT * FROM street_data LIMIT 5;").df()
con.execute(query="SELECT COUNT(*) FROM street_data;").df()

# Look at data type for later filtering
con.execute(query="SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'street_data' AND column_name = 'Month';").fetchall()
# Month column is VARCHAR

# have a look at all months
con.execute(query="""SELECT DISTINCT 
                            Month 
                    FROM street_data 
                    WHERE Month BETWEEN '2016-01' AND '2025-12'
                    ORDER BY Month;
                    """).df()
# 120 rows found so it is getting the time filtering ok 


# look at owning forces for later filtering
force_list: DataFrame = con.execute(query="""SELECT DISTINCT "Falls Within" FROM street_data;""").df()
# Norfolk: Norfolk Constabulary
# Suffolk: Suffolk Constabulary





## Interesting question: Initially looking at Norfolk and Suffolk
# for initial scoping of project. This is rurual, rural/urban (not large city urban, metropolitian)
# intersting to compare the results to UK wide vs this geographic subset 
# to see if differences emerge

# %%


# select subsection of crime data needed for project
# Crime ID, Month, Longitude, Latitude, Crime type
# filter to just Norfolk and Suffolk between 2016 and 2026
#write this to a new table

if make_table:
        subset_query = """
                CREATE OR REPLACE TABLE crimetology_NS AS
                SELECT "Crime ID", 
                        Month, 
                        Longitude, 
                        Latitude, 
                        "Crime type"
                FROM street_data 
                WHERE "Falls within" IN ('Norfolk Constabulary', 'Suffolk Constabulary')
                AND Month BETWEEN '2016-01' AND '2025-12';
                """
        con.execute(query=subset_query)


#table size = 1314474 rows
# original street data archive = 92362169


#now open and have a look
con.execute(query="SHOW TABLES").fetchall()
con.execute(query="SELECT * FROM crimetology_NS LIMIT 15;").df()

## map to weather