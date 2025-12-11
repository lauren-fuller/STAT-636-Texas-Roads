# STAT 636 — Texas Road Network Analysis

This repository contains code and notebooks for analyzing the robustness and recovery of road networks in Texas using OpenStreetMap (OSM) data.
The project evaluates how transportation networks in the Austin, Texas area respond to random and targeted failures and how network efficiency can be restored.

## File Descriptions

### `Data Format.pdf`  
A PDF file documenting the format and attributes of the dataset being used.

### `STAT 636_Leander_Cedar_Park_Network.ipynb`  
Jupyter Notebook containing the primary analysis for the Leander & Cedar Park area.

### `STAT636_Austin_Network.ipynb`  
Jupyter Notebook containing the primary analysis for the Austin area.

### `build_texas_road_network.py`  
Python script that reads the Texas OpenStreetMap road shapefile using GeoPandas and builds a graph representation of the road network. This script is used to preprocess raw spatial data and generate derived network files used by the notebooks.


## Data Source

This project uses OpenStreetMap road data provided by Geofabrik. Due to the size of the dataset, raw shapefiles are not included in this repository and must be downloaded separately.

### Downloading the Data

1. Navigate to the Geofabrik North America download page:
   https://download.geofabrik.de/north-america.html

2. Download the Texas dataset in GIS (shapefile) format. The file name will be similar to:
   texas-latest-free.shp.zip

3. Unzip the downloaded file. The extracted folder will contain multiple shapefile layers. All shapefile components must be stored in the same directory as the python files.

## Reproducing the Analysis

1. After placing the required shapefiles in the proper directory, run the following script to construct the road network:

   python build_texas_road_network.py

   This script generates derived network files used by the analysis notebooks.

2. Open and run the analysis notebooks.


