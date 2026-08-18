
# README  

This repo contains an open source Data Science project as part of a BPP Apprenticeship based Data Science BSc.

## Project Hypothesis


 - **HO, Null hypothesis**:   
    "The maximum ambient temperature (tasmax) and relative humidity (hurs) have no statistically significant effect on the odds of a crime occuring in a Leiure cluster versus a Retail cluster. Spatial distrubtions of crime occurence across land use contexts is independent of weather variables."  
      
 - **H1, Alternative hypothesis**:  
    "Increases in maximum ambient air temperature and humidity significantly increase the odds of a crime occuring in a Leisure cluster versus a retail cluster."   

Background Reading:    

[Statsmodels Logit](https://www.statsmodels.org/stable/generated/statsmodels.discrete.discrete_model.Logit.html#statsmodels.discrete.discrete_model.Logit)  
[A.L Nelson, R.D.F Bromley & C.J Thomas (2000)](https://doi.org/10.1016/S0143-6228(01)00008-X)  
[Brunsdon, C., Corcoran, J., Higgs, G. & Ware, A. (2009).](https://doi.org/10.1068/b32133)  
[Narushige Shiode, Shino Shiode, Hayato Nishi & Kimihiro Hino (2023)](https://doi.org/10.1007/s43762-023-00094-x)  
[Supression effect paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC2819361/pdf/nihms-173346.pdf)  
 
*Important Note:* this project is looking at the inference of 'does weather imapact crime event occurance is leisure/retail zones' and not 'can we predict if crime will occur in a leisure or retail zone'.


## Project Structure


 **1. Extract Transform Load Steps**   

 All files and subprocesses are included in folder "1_ETL".   

 These steps pull UK wide police archives data via [get_crime_data.py](1_ETL/get_crime_data.py) and a user specified subset of monthly averaged UK weather data, sourced from the met office, via [get_ceda_data.py](1_ETL/get_ceda_data.py). This process uses a CEDA access token to validate the request; however, I dont think this is technically needed but better to be polite. 

 The [exploratory data analysis notebook](1_ETL/crime_weather_EDA.ipynb) highlighed a spatial data quality issue that needed addressing before finally loading the dataset as *crimetology_NS_clean*, which is used for the remainder of the project into local workspace. 
 
 *Note*: There are residual data quality issues regarding the covid lockdown periods and syntheic ID (potential duplication) prevalence that persist into the analysis and should be kept in mind. 

**2. Spatial Clustering**

Spatial desity based clustering is applied in [spatial_clustering.ipynb](2_spatial_clusters/spatial_clustering.ipynb) to locate spatially clustered areas where crimes have been recorded in Norfolk and Suffolk between Jan 2016 to Dec 2025.

**3. Context Lables**

Context lables are assigned to spatial clusters via crime types presence in [context_labels.ipynb](3_context_lables/context_lables.ipynb).   

Crimes are bucketed via 'Leisure', 'Retail' or 'Other' typologies. When a cluster is in the top 10% of 'Leisure' or 'Retail' crime typology it is assigned that typologies context label. 

*Note*: this method has many limitations as no crime type will ever fall only within 'Leisure' or 'Retail' zones exclusively. It also stuggled with high volume low spatial range areas when considereing Norfolk and Suffolk as a whole. It is deemed acceptable for this general open source project that is solely an academic exercise.

**4. Logistic Regression**

Hypothesis testing is carried out in the final notebook, [logistic_regression.ipynb](4_logistic_regression/logistic_regression.ipynb). 

This uses logistic regression to form predictor variable weights and pvalues to test whether tasmax and hurs are related to one cluster typology more than the other. 



-----
 ## Conda Env Note  

The file [crime_weather_env.yaml](crime_weather_env.yaml) containes dependencies for the conda env 'crime_weather_env' used to run the .py and .ipynb files found in this repo. 

-----
 ## Data Note

The inital data extraction is resource intensive so a copy of the open source data post extraction is available via Zenodo. 

Crime data for this project is downloaded from [police archives UK](https://data.police.uk/data/archive/) with a copy made avaiable openly available via [Zenodo](https://doi.org/10.5281/zenodo.20798154)

Combined weather and crime project dataset aviablable via [Zendodo](https://doi.org/10.5281/zenodo.21415972)  

The subset dataset of just Norfolk and Suffolk is not on Zenodo but easily extracted once the above files exist on a local device. 

-----