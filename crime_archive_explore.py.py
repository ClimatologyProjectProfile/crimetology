#######################################################################
# This script is deigned to be used with conda env
# crime_weather env
#
# Code to explore the crime_archive.db
#
#######################################################################



###########################################################
# %% Import modules
import os
import duckdb
from pathlib import Path
import duckdb

############################################################
# %% Setup directories and paths
cwd = os.getcwd()
data_dir = Path(cwd) / 'data' / 'police_archives'
crime_db = data_dir/'crime_archive.db'


# %%
# set up duck db connection
con = duckdb.connect(crime_db)

# introspect
con.execute("SHOW TABLES").fetchall()

# head
con.execute("SELECT * FROM street_data LIMIT 5;").df()

# DQ Notes: 
#  - 'Falls within' in a duplication of 'Reported by'
#  - 'Context' is empty
# 
# Columns needed for project = 
# Month, 
# Longitude, 
# Latitude, 
# Crime type 
# (could also keep Crime ID as URN/key)
#

# time span of this data?
time_span_query = """SELECT   
                        MIN(Month) AS min_date,
                        MAX(Month) AS max_date,
                    FROM street_data;"""
con.execute(time_span_query).df()

# min = 2010-12, max = 2026-04

# NOTE: athena was introduced in 2015, so data prior to this
# will most likely be slightly different. No calibration between 
# time periods and method. Best to pull data post 2016 only. 
# Leaves 10years of data, run project from 2016-01-01 to 2026-01-01

# HadUK - https://www.metoffice.gov.uk/hadobs/hadukgrid/ 
# is up to Dec 2024. Can be extended to 2026 using the provisional 
# data release

# For project development use 8 years of monthly data, 2016 to 2024. 
# https://data.ceda.ac.uk/badc/ukmo-hadobs/data/insitu/MOHC/HadOBS/HadUK-Grid/v1.3.2.ceda/1km