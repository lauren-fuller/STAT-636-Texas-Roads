# STAT-636-Texas-Roads

## build_texas_road_network.py
This script: 
- Loads the Geofabrik Texas roads shapefile
- Filters to drivable road types
- Computes segment length and estimated travel time
- Builds a directed NetworkX road network
- Saves the resulting graph as:
  - texas_roads.graphml  (standard format, slower to load)
  - texas_roads.pkl      (pickled NetworkX graph, faster for notebooks)


## STAT636_Austin_Network.ipynb:
This section contains the code used to:
- construct the Austin road network from the Texas OSM shapefile,
- extract the Downtown/Central Austin study area, and
- compute centrality, robustness, and repair-order results for that subnetwork.
