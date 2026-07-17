#######################################################################
# This script is deigned to be used with conda env
# crime_weather env
#
# Code to explore the crime_archive.db
#
#######################################################################



###########################################################
# %% Import modules
from xarray.core.dataset import Dataset
import os
import duckdb
from pathlib import Path
import xarray as xr
from pyproj import Transformer


############################################################
# %% Setup directories and paths
cwd: str = os.getcwd()
data_dir: Path = Path(cwd) / 'data' / 'police_archives'
crime_db: Path = data_dir/'crime_archive.db'


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

# time span of this data?
time_span_query = """SELECT   
                        MIN(Month) AS min_date,
                        MAX(Month) AS max_date,
                    FROM crimetology_NS;"""
con.execute(time_span_query).df()



# time span of this data?
data_look_query = """SELECT *
                    FROM crimetology_NS
                    ORDER BY Month ASC
                    LIMIT 10;"""
con.execute(data_look_query).df()


## size of this subset?
size_query = """SELECT COUNT(*)
                    FROM crimetology_NS
                    WHERE "Crime ID" LIKE 'NO_ID%';"""
con.execute(size_query).df()


# nan is weather data?
weather_nan_query = """SELECT COUNT(*)
                    FROM crimetology_NS
                    WHERE tasmax IS NULL
                        OR tas IS NULL
                        OR groundfrost IS NULL
                        OR sun IS NULL
                        OR snowLying IS NULL
                        OR tasmin IS NULL
                        OR rainfall IS NULL
                        OR hurs IS NULL
                        or sfcWind IS NULL
                    ;"""
con.execute(weather_nan_query).df()



# manually check data - make sure its worked as expected

ground_frost_2016: Dataset = xr.open_dataset(filename_or_obj='data/ceda/raw/groundfrost/groundfrost_hadukgrid_uk_1km_mon_201601-201612.nc')
tasmax_2016: Dataset = xr.open_dataset(filename_or_obj='data/ceda/raw/tasmax/tasmax_hadukgrid_uk_1km_mon_201601-201612.nc')
tas_2016: Dataset = xr.open_dataset(filename_or_obj='data/ceda/raw/tas/tas_hadukgrid_uk_1km_mon_201601-201612.nc')
sun_2016: Dataset =xr.open_dataset(filename_or_obj='data/ceda/raw/sun/sun_hadukgrid_uk_1km_mon_201601-201612.nc') 
snowLying_2016: Dataset =xr.open_dataset(filename_or_obj='data/ceda/raw/snowLying/snowLying_hadukgrid_uk_1km_mon_201601-201612.nc') 
tasmin_2016: Dataset =xr.open_dataset(filename_or_obj='data/ceda/raw/tasmin/tasmin_hadukgrid_uk_1km_mon_201601-201612.nc') 
rainfall_2016: Dataset =xr.open_dataset(filename_or_obj='data/ceda/raw/rainfall/rainfall_hadukgrid_uk_1km_mon_201601-201612.nc') 
hurs_2016: Dataset =xr.open_dataset(filename_or_obj='data/ceda/raw/hurs/hurs_hadukgrid_uk_1km_mon_201601-201612.nc') 
sfcWind_2016: Dataset =xr.open_dataset(filename_or_obj='data/ceda/raw/sfcWind/sfcWind_hadukgrid_uk_1km_mon_201601-201612.nc') 


# 1. Set up a transformer from standard Lat/Lon (EPSG:4326) to HadUK Grid (EPSG:27700)
# always_xy=True ensures we pass (longitude, latitude) and get back (X, Y)
transformer: Transformer = Transformer.from_crs(crs_from="EPSG:4326", crs_to="EPSG:27700", always_xy=True)

# 2. Convert your target coordinates
target_lon = 1.071786
target_lat = 52.652082
time_in = '2016-01'
haduk_x, haduk_y = transformer.transform(xx=target_lon, yy=target_lat)


ground_frost_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['groundfrost'].values#.plot(vmin=8.52,vmax=8.53,)
tasmax_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['tasmax'].values#.plot(vmin=8.52,vmax=8.53,)
tas_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['tas'].values#.plot(vmin=8.52,vmax=8.53,)
sun_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['sun'].values#.plot(vmin=8.52,vmax=8.53,)
snowLying_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['snowLying'].values#.plot(vmin=8.52,vmax=8.53,)
tasmin_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['tasmin'].values#.plot(vmin=8.52,vmax=8.53,)
rainfall_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['rainfall'].values#.plot(vmin=8.52,vmax=8.53,)
hurs_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['hurs'].values#.plot(vmin=8.52,vmax=8.53,)
sfcWind_2016.sel(time=time_in,projection_x_coordinate=haduk_x,projection_y_coordinate=haduk_y,method='nearest')['sfcWind'].values#.plot(vmin=8.52,vmax=8.53,)


## All look good! :D