
#import module
from get_ceda_data import get_file  #code orignally from ceda github


"""
You will be prompted to provide your CEDA username and password the first time the script is run and
again if the token cached from a previous attempt has expired.
"""

#test with one file
url = "https://dap.ceda.ac.uk/badc/ukmo-hadobs/data/insitu/MOHC/HadOBS/HadUK-Grid/v1.3.2.ceda/1km/tas/mon/v20260512/tas_hadukgrid_uk_1km_mon_202501-202512.nc"
var_id = "tas"

get_file(url,var_id)

