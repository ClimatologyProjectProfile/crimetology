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
#from scipy.constants import c
import os
from pathlib import Path
import time

import xarray as xr
from xarray.core.dataset import Dataset
from pandas.core.frame import DataFrame
import numpy as np
from numpy import ndarray
import pandas as pd

from scipy.spatial import cKDTree  # ty:ignore[unresolved-import] because ty is wrong.
#https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html

from _duckdb import DuckDBPyConnection
import duckdb

############################################################
# %% Setup directories and paths
cwd: str = os.getcwd()
crime_data_dir: Path = Path(cwd) / 'data' / 'police_archives'
crime_db: Path = crime_data_dir/'crime_archive.db'
weather_data_dir: Path = Path(cwd) / 'data' / 'ceda' / 'raw'


############################################################
# %% User Inputs
make_table:bool = True


#####################################################################
#
# Step One: Create a subset of crime data for the project
# (this forms the base of out new data table)
#
#####################################################################
# %%
# set up duck db connection
con: DuckDBPyConnection = duckdb.connect(database=crime_db)

# # introspect
# con.execute(query="SHOW TABLES").fetchall()
# con.execute(query="SELECT * FROM street_data LIMIT 5;").df()
# con.execute(query="SELECT COUNT(*) FROM street_data;").df()

# # Look at data type for later filtering
# con.execute(query="""SELECT column_name, 
#                             data_type 
#                      FROM information_schema.columns 
#                      WHERE table_name = 'street_data' 
#                         AND column_name = 'Month';"""
#              ).fetchall()
# # Month column is VARCHAR

# # have a look at all months
# con.execute(query="""SELECT DISTINCT 
#                             Month 
#                     FROM street_data 
#                     WHERE Month BETWEEN '2016-01' AND '2025-12'
#                     ORDER BY Month;
#                     """).df()
# # 120 rows found so it is getting the time filtering ok 


# # look at owning forces for later filtering
# force_list: DataFrame = con.execute(query="""SELECT DISTINCT "Falls Within" FROM street_data;""").df()
# # Norfolk: Norfolk Constabulary
# # Suffolk: Suffolk Constabulary


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
                        AND Month BETWEEN '2016-01' AND '2025-12'
                        AND Month IS NOT NULL
                        AND Latitude IS NOT NULL
                        AND Longitude IS NOT NULL;
                """
        con.execute(query=subset_query)


#table size = 1314474 rows
# once null values filtered = 1280212
# 34262 rows removed....
# original street data archive = 92362169


# #now open and have a look
# con.execute(query="SHOW TABLES").fetchall()
# con.execute(query="SELECT * FROM crimetology_NS LIMIT 15;").df()
# con.execute(query="SELECT COUNT(*) FROM crimetology_NS;").df()



#####################################################################
#
# Step Two: Map distinct police.ac.uk anonymysed lat/lons to the nearest
# Had UK 1km projected lat/lon and save this as a lookup table
#
#####################################################################

############################
## police.ac.uk geospatial points
# %%
# Crime data spatial data - just find the lat, lons that are unqiue as one dataframe
crime_lat_lons_query:str = """ SELECT DISTINCT
                                      Latitude,
                                      Longitude
                                  FROM crimetology_NS;""" 
crime_lat_lons_mapping: DataFrame = con.execute(query=crime_lat_lons_query).df()

# crime_lat_lons_mapping.shape
# # 56205 distinct lat, lon entries 

# # have a look at an entry
# crime_lat_lons_mapping.head()
# #introspect
# crime_lat_lons_mapping.info()

#data quality check (if nans / inf the tree wont work)
for row in np.isnan(crime_lat_lons_mapping).sum():
    if row!=0:
        print('Issue: latitude longitude in crimetology_NS have nans present.')
        print(np.isnan(crime_lat_lons_mapping).sum())
# 0 

for row in np.isinf(crime_lat_lons_mapping).sum():
    if row!=0:
        print('Issue: latitude longitude in crimetology_NS have infs present.')
        print(np.isinf(crime_lat_lons_mapping).sum())
# 0




############################
## HadUK geospatial points
# %%
## look at netcdf format of a random file
cdf_format_check_file: Dataset = xr.open_dataset(filename_or_obj=weather_data_dir / Path('groundfrost/groundfrost_hadukgrid_uk_1km_mon_201601-201612.nc'))
#quick plot
#cdf_format_check_file['groundfrost'].mean(dim='time').plot()
#everything looks reasonable post download

# get the HadUK lat lon grid (transerver mercator proj)
# doing for whole UK to enable future project iterations
HadUK_lats: ndarray = cdf_format_check_file['latitude'].values
HadUK_lons: ndarray = cdf_format_check_file['longitude'].values

# # have a look
# HadUK_lats
# HadUK_lons
# #both have shape (1450,900)
# #expected ravelled length is 1305000

#create all HadUK lat/lon pairs (=1540x900 pairs)
HadUK_latlon_grid_points = np.column_stack([HadUK_lats.ravel(),HadUK_lons.ravel()])
#store the original grid shape for fast x/y indices look up later
grid_shape = HadUK_lats.shape
## length 1305000

# for mapping check, get the largest 1D grid spacing in HadUK
max_hadUK_lat = np.abs([HadUK_lats[i+1]-HadUK_lats[i] for i in range(len(HadUK_lats)-1)]).max()
max_hadUK_lon = np.abs([HadUK_lons[i+1]-HadUK_lons[i] for i in range(len(HadUK_lons)-1)]).max()


############################
## Mapping Step
# to map the crime archive lat lon data to HadUK lat lon data we are going to 
# do a closest value lookup. Efficient method is scipy cKDTree
tree = cKDTree(HadUK_latlon_grid_points)

# # test nearest neigbour lookup on one point
# crime_test_coord = crime_lat_lons_mapping.iloc[25]
# _,i = tree.query(crime_test_coord)
# #looks sensible
# print(crime_test_coord)
# print(HadUK_latlon_grid_points[i,:])


# %% Now map the crime points to the nearest neighbour 
_, idx = tree.query(crime_lat_lons_mapping,k=1)
mapped_data = HadUK_latlon_grid_points[idx]
# the weather data is stored as lat/lon equivalent to y/x
# so up first then across
weather_grid_y, weather_grid_x = np.unravel_index(idx, grid_shape)

# append the mapped data to the DataFrame
crime_lat_lons_mapping['Latitude_HadUK'] = mapped_data[:,0]
crime_lat_lons_mapping['Longitude_HadUK'] = mapped_data[:,1]
crime_lat_lons_mapping['weather_grid_y'] = weather_grid_y
crime_lat_lons_mapping['weather_grid_x'] = weather_grid_x


# #check distance mapping
# (np.abs((crime_lat_lons_mapping['Latitude']-crime_lat_lons_mapping['Latitude_HadUK']))>max_hadUK_lat).sum()
# # all latitudes within one gridcell

# ((np.abs(crime_lat_lons_mapping['Longitude']-crime_lat_lons_mapping['Longitude_HadUK'])) > 3*max_hadUK_lon).sum()
# #32603 over one grid cell away (~1km)
# #9009 over two grid cells away (~2km)
# # All within three gridcells (~3km)

## since the crime data lat/lon points are anonymysed with data points
# over 20km away being discarded, this is adding only around a 10%
# margin of error versus the anonymysation
# Currently acceptable

############################
## Save Lookup
#
if make_table:
        con.register(view_name='coords_mapping_df', python_object=crime_lat_lons_mapping)
        con.execute(query="""CREATE OR REPLACE TABLE crimetology_coords_lookup AS
                                SELECT * 
                                FROM coords_mapping_df;""")

# # check the table is stored in the duckdb
# con.execute(query="SELECT * FROM crimetology_coords_lookup LIMIT 30;").df()



#####################################################################
#
# Step Three: create a weather data lookup table
#
#####################################################################

## find weather vars as a list and store location of data files

# make an empty dict to store the variable 
# as a key and files with data as values
weather_files_dict: dict={}
for item in Path.iterdir(self=weather_data_dir):
        if item.is_dir():
                key: str = item.name
                files_list: list[Path] = list(item.glob(pattern='*.nc'))
                weather_files_dict[key]=files_list

# # have a look at the vars
# weather_vars: list = [key for key in weather_files_dict.keys()]
# weather_vars[5]
# weather_files_dict[weather_vars[5]]

## helper functions for pulling the weather data for 
# the crimetology subset table

def get_weather_files(month:str) -> dict:
        year: str = month.split(sep='-')[0]
        filtered_dict: dict= {key: [p for p in paths if year in str(object=p)] for key, paths in weather_files_dict.items()}
        return(filtered_dict)

def get_coords(month:str) -> DataFrame:
        one_month_coords_lookup_query:str = f"""SELECT DISTINCT
                                                weather_grid_y,   --latitude
                                                weather_grid_x,   --longitude
                                        FROM crimetology_NS AS crime
                                        LEFT JOIN crimetology_coords_lookup AS coords
                                                ON crime.Longitude = coords.Longitude 
                                                AND crime.Latitude = coords.Latitude
                                        WHERE Month IN ('{month}');"""
        all_coords: DataFrame = con.execute(query=one_month_coords_lookup_query).df()
        return all_coords

def create_weather_df(month_in:str) -> DataFrame:
        # location on net cdf files
        file_locs: dict = get_weather_files(month=month_in)
        # 
        grid_indicies: DataFrame = get_coords(month_in)
        y_idx = xr.DataArray(data=grid_indicies['weather_grid_y'].values,dims='points')
        x_idx = xr.DataArray(data=grid_indicies['weather_grid_x'].values,dims='points')

        # collect up data over all weather variables for that month
        data_list: list = []
        for var, data_path in file_locs.items():
                # there should only be one file per date stamp
                # so check this and raise an error if something has gone
                # wrong
                if len(data_path)!=1: 
                        raise ValueError(f"Expected 1 file for {var}, but found {len(data_path)}")
                with xr.open_dataset(filename_or_obj=data_path[0]) as ds:
                    # slice over month as i dont know what dummy index is used
                    sliced_ds: Dataset = ds.sel(time=slice(month_in+'-01',month_in+'-28'))
                    #data_list.append(sliced_ds)
                    # pull only data into memory that we actually need
                    filtered_data: Dataset = sliced_ds.isel(projection_y_coordinate=y_idx,
                                                            projection_x_coordinate=x_idx)
                    data_list.append(filtered_data)
        #NOTE: some of these weather vars do not have the same time bounds
        # so override the comparibility test as this does not matter
        # for our purposes here
        all_data: xr.DataArray = xr.merge(objects=data_list,compat='override')
        # dont need the metadata - drop it if its there
        all_data: xr.DataArray = all_data.drop_vars(names=["time_bnds",
                                                        "transverse_mercator",
                                                        "projection_y_coordinate_bnds",
                                                        "projection_x_coordinate_bnds"], 
                                                        errors="ignore")
        # this part is memory intensive
        all_data: DataFrame = all_data.to_dataframe().reset_index()
        # finally concat on to coords so we can merge back to duck
        result: DataFrame = pd.concat(objs=[grid_indicies, all_data], axis=1)
        return(result)



# %% 
def update_month_by_month() -> list:
        ###########################
        # setup ready for updates
        ###########################
        # find all months
        months: ndarray= np.array(object=con.execute(query="SELECT DISTINCT Month FROM crimetology_NS;").df()).flatten()
        # find all weather vars
        weather_vars: list = [key for key in weather_files_dict.keys()]
        #create these as a list for our later SQL SET command
        # !need to map new crime col to staged data column
        # with an '='
        new_cols: str = ", ".join([f"{var} = staged.{var}" for var in weather_vars])
        # update the crimetology_NS table with columns needed
        # otherwise the UPDATE wont work
        existing_cols: list = [row[0] for row in con.execute("DESCRIBE crimetology_NS;").fetchall()]
        for var in weather_vars:
            if var not in existing_cols:
                print(f"Adding missing column '{var}' to crimetology_NS")
                con.execute(query=f"ALTER TABLE crimetology_NS ADD COLUMN {var} FLOAT;")
        
        ###########################
        # Attempt updates
        ###########################
        # keep a record of which months are done
        completed_months: set = set()
        # set how many retires are allowed
        max_retries = 3
        for month in months:
            # check to see if this is already ingested
            if month in completed_months:
                print(f"Month {month} already completed. Skipping.")
                continue
            attempt = 0
            success = False
            while attempt < max_retries and not success:
                try:
                    attempt += 1
                    print(f"Processing month {month} (Attempt {attempt}/{max_retries})...")
                    # Start safe transaction
                    con.execute(query="BEGIN TRANSACTION;")
                    # for each month of data extract the corresponding weather
                    # data 
                    weather_staging:DataFrame = create_weather_df(month_in=month)
                    # register this as a tmp table
                    # (lets duckdb do the heavy lifting)
                    con.register(view_name='tmp_weather_table', python_object=weather_staging)
                    # join to the crimetology_NS subset
                    join_data_query:str = f"""UPDATE crimetology_NS AS crime
                                              SET {new_cols}
                                              FROM crimetology_coords_lookup AS coords,
                                                  tmp_weather_table AS staged
                                              WHERE crime.Longitude = coords.Longitude 
                                                  AND crime.Latitude = coords.Latitude
                                                  AND coords.weather_grid_y = staged.weather_grid_y
                                                  AND coords.weather_grid_x = staged.weather_grid_x
                                                  AND crime.Month = '{month}';"""
                    con.execute(query=join_data_query)
                    con.execute(query="COMMIT;")
                    # Log completion
                    success = True
                    completed_months.add(month)
                    print('******************************')
                    print(f'Run for month {month}')
                    print(f"Success at attempt {attempt}")
                    print('******************************')                
                except (duckdb.Error, Exception) as e:
                    print(f"Error on month {month} during attempt {attempt}: {e}")
                    # Attempt to rollback month that has an issue
                    try:
                        con.execute(query="ROLLBACK;")
                    except (duckdb.Error, Exception) as e:
                       print(f"Error on roll back of month {month} during attempt {attempt}: {e}")
                       pass
                    if attempt < max_retries:
                        print("Retrying in 10 seconds...")
                        time.sleep(10)
                        continue
            if not success:
                print(f"Month {month} failed permanently after {max_retries} attempts.")        
        # unsuccesful months
        hard_fails: list = [month for month in months if month not in completed_months]
        #done all months now exit
        return (hard_fails)


#####################################################################
#
# Step Four: Run update routine to join weather to crime data
#
#####################################################################

##
### Main 'entry point function' here
##

if make_table:
    # run update routine
    failures: list = update_month_by_month()
    if len(failures) !=0:
        print('****************************************************')
        print(' !! WARNING !!')
        print(f' Update Routine Failed for {len(failures)} months.')
        print(' These are: ')
        for failure in failures:
                print(f' {failure}\n ')
        print('****************************************************')

con.close()