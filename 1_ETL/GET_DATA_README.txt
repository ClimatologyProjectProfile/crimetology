Order in which to run inline scripts to extract crime data (/or update), the a selection of weather data and then combine to two

1. get_crime_data.py
2. get_ceda_data.py (depends on access_ceda_data.py)
3. combine_crime_ceda_data.py

Would be better for there to be an orchestation script that imports the core functions and runs these automatically. 
As a first pass it is being run manually. 