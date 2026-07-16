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
import os
from pathlib import Path

import xarray as xr
from xarray.core.dataset import Dataset
from pandas.core.frame import DataFrame
import numpy as np
from numpy import ndarray

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
make_table:bool = False






#####################################################################
#
# Step One: Create a subset of crime data for the project
# (this forms the base of out new data table)
#
#####################################################################
# %%
# set up duck db connection
con: DuckDBPyConnection = duckdb.connect(database=crime_db)

# introspect
con.execute(query="SHOW TABLES").fetchall()
con.execute(query="SELECT * FROM street_data LIMIT 5;").df()
con.execute(query="SELECT COUNT(*) FROM street_data;").df()

# Look at data type for later filtering
con.execute(query="""SELECT column_name, 
                            data_type 
                     FROM information_schema.columns 
                     WHERE table_name = 'street_data' 
                        AND column_name = 'Month';"""
             ).fetchall()
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


#now open and have a look
con.execute(query="SHOW TABLES").fetchall()
con.execute(query="SELECT * FROM crimetology_NS LIMIT 15;").df()
con.execute(query="SELECT COUNT(*) FROM crimetology_NS;").df()



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

crime_lat_lons_mapping.shape
# 56205 distinct lat, lon entries 

# have a look at an entry
crime_lat_lons_mapping.head()
#introspect
crime_lat_lons_mapping.info()

#data quality check (if nans / inf the tree wont work)
np.isnan(crime_lat_lons_mapping).sum()
# 0 
np.isinf(crime_lat_lons_mapping).sum()
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

# have a look
HadUK_lats
HadUK_lons
#both have shape (1450,900)
#expected ravelled length is 1305000

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

# test nearest neigbour lookup on one point
crime_test_coord = crime_lat_lons_mapping.iloc[25]
_,i = tree.query(crime_test_coord)
#looks sensible
print(crime_test_coord)
print(HadUK_latlon_grid_points[i,:])


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


#check distance mapping
(np.abs((crime_lat_lons_mapping['Latitude']-crime_lat_lons_mapping['Latitude_HadUK']))>max_hadUK_lat).sum()
# all latitudes within one gridcell

((np.abs(crime_lat_lons_mapping['Longitude']-crime_lat_lons_mapping['Longitude_HadUK'])) > 3*max_hadUK_lon).sum()
#32603 over one grid cell away (~1km)
#9009 over two grid cells away (~2km)
# All within three gridcells (~3km)

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

# check the table is stored in the duckdb
con.execute(query="SELECT * FROM crimetology_coords_lookup LIMIT 30;").df()



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

# have a look at the vars
weather_vars: list = [key for key in weather_files_dict.keys()]
weather_vars[5]
weather_files_dict[weather_vars[5]]

# month by month
months: ndarray= np.array(object=con.execute(query="SELECT DISTINCT Month FROM crimetology_NS;").df()).flatten()

def get_weather_files(month:str) -> dict:
        year: str = month.split(sep='-')[0]
        filtered_dict: dict= {key: [p for p in paths if year in str(object=p)] for key, paths in weather_files_dict.items()}
        return(filtered_dict)

def create_weather_df(month_in:str) -> xr.Dataset:
        file_locs: dict = get_weather_files(month=month_in)
        # collect up data over all weather variables for that month
        data_list: list = []
        for var, data_path in file_locs.items():
                # there should only be one file per date stamp
                # so check this and raise an error if something has gone
                # wrong
                if len(data_path)!=1: 
                        raise ValueError(f"Expected 1 file for {var}, but found {len(data_path)}")
                with xr.open_dataset(filename_or_obj=data_path[0]) as ds:
                        # slice over full month as i dont know what dummy index is used
                    sliced_ds: Dataset = ds.sel(time=slice(month_in+'-01',month_in+'-28'))
                    data_list.append(sliced_ds)
        #NOTE: some of these weather vars do not have the same time bounds
        # so override the comparibility test as this does not matter
        # for our purposes here
        return(xr.merge(objects=data_list,compat='override'))



# randomly check one variable
test: Dataset = create_weather_df(month_in=months[25])
#test['tasmax'].plot()
# test['tasmin'].plot()
# test['snowLying'].plot()
# test['rainfall'].plot()
# test['hurs'].plot()
# test['sfcWind'].plot()
# test['groundfrost'].plot()
# test['sun'].plot()


#get one month of the subset crime data
# and join HadUK coords via lookup
one_month_crime_query:str = f"""SELECT
                                    "Crime ID",
                                    Month,
                                    crime.Latitude,
                                    Latitude_HadUK,
                                    crime.Longitude,
                                    Longitude_HadUK,
                               FROM crimetology_NS AS crime
                               LEFT JOIN crimetology_coords_lookup AS coords
                                   ON crime.Longitude = coords.Longitude 
                                   AND crime.Latitude = coords.Latitude
                               WHERE Month IN ('{months[23]}');"""

con.execute(query=one_month_crime_query).df()



one_month_coords_lookup_query:str = f"""SELECT DISTINCT
                                                Latitude_HadUK,
                                                Longitude_HadUK,
                                        FROM crimetology_NS AS crime
                                        LEFT JOIN crimetology_coords_lookup AS coords
                                                ON crime.Longitude = coords.Longitude 
                                                AND crime.Latitude = coords.Latitude
                                        WHERE Month IN ('{months[23]}');"""
all_coords: DataFrame = con.execute(query=one_month_coords_lookup_query).df()
#flatten for the vertorised lookup
lats = xr.DataArray(data=all_coords['Latitude_HadUK'].values, dims='points')
lons = xr.DataArray(data=all_coords['Longitude_HadUK'].values, dims='points')






test: Dataset = create_weather_df(month_in=months[23])

for var in test.data_vars:
        #skip meta vars
        if var in ['transverse_mercator', \
                   'time_bnds', \
                   'projection_y_coordinate_bnds', \
                   'projection_x_coordinate_bnds']:
                   continue
        print(var)

test['tasmax'].sel(latitude=lats,longitude=lons,method='nearest')





# %%
