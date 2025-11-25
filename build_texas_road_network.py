"""
build_texas_road_network.py

STAT 636 project starter:
- Loads Geofabrik Texas roads shapefile
- Filters to drivable roads
- Computes length and travel time
- Builds a directed NetworkX graph
- Does a quick degree-centrality sanity check
- Saves graph to:
    - texas_roads.graphml  (standard, but slow to load)
    - texas_roads.pkl      (fast pickle for notebooks)
"""

import os
import pickle

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString
import networkx as nx


# ========== USER CONFIGURATION ==========

# Path to the roads shapefile (from texas-latest-free.shp.zip)
ROADS_SHP_PATH = "gis_osm_roads_free_1.shp"

# Output graph files
OUTPUT_GRAPHML = "texas_roads.graphml"
OUTPUT_PICKLE = "texas_roads.pkl"

# Whether to restrict to a bounding box (e.g., focus on a region instead of all Texas)
USE_BBOX = False
# Example bounding box in WGS84 (lon_min, lon_max, lat_min, lat_max)
BBOX = (-98.0, -95.0, 29.0, 31.0)  # roughly Houston area if you ever turn this on

# Default speeds (kph) for each road class (fclass/highway) if maxspeed is missing
DEFAULT_SPEEDS_KPH = {
    # Major roads
    "motorway": 110,
    "trunk": 100,
    "primary": 90,
    "secondary": 80,
    "tertiary": 70,
    # Minor roads
    "unclassified": 60,
    "residential": 40,
    "living_street": 25,
    "pedestrian": 10,
    # Links
    "motorway_link": 80,
    "trunk_link": 70,
    "primary_link": 70,
    "secondary_link": 60,
    "tertiary_link": 50,
    # Small roads & tracks
    "service": 30,
    "track": 30,
    "track_grade1": 40,
    "track_grade2": 35,
    "track_grade3": 30,
    "track_grade4": 25,
    "track_grade5": 20,
    # Paths
    "bridleway": 10,
    "cycleway": 20,
    "footway": 5,
    "path": 8,
    "steps": 3,
    # Busway
    "busway": 50,
}


# ========== HELPER FUNCTIONS ==========

def parse_maxspeed(value):
    """
    Parse a maxspeed value into kph (float).
    Geofabrik usually stores maxspeed as numeric km/h, but this handles weird strings safely.
    """
    if value is None:
        return None

    s = str(value).lower().strip()
    if s == "" or s in {"nan", "none"}:
        return None

    num = ""
    for ch in s:
        if ch.isdigit() or ch == ".":
            num += ch
        elif num:
            break

    if num == "":
        return None

    speed = float(num)

    # catch 'mph' just in case
    if "mph" in s:
        speed = speed * 1.60934

    return speed


def infer_speed_kph(row):
    """
    Decide on a speed for this road segment:
    1) Try maxspeed if available (km/h)
    2) Otherwise use DEFAULT_SPEEDS_KPH based on fclass/highway
    3) If unknown, fall back to 50 kph
    """
    # 1) Try maxspeed column
    maxspeed_col = None
    for col in row.index:
        if col.lower() == "maxspeed":
            maxspeed_col = col
            break

    speed = None
    if maxspeed_col is not None:
        val = row[maxspeed_col]
        if val is not None and str(val).strip() != "":
            try:
                speed = float(val)
            except ValueError:
                speed = parse_maxspeed(val)

    # 2) If still None, use fclass/highway defaults
    if speed is None:
        highway_col = None
        for col in row.index:
            if col.lower() in ("highway", "fclass"):
                highway_col = col
                break

        if highway_col is not None:
            road_type = row[highway_col]
            speed = DEFAULT_SPEEDS_KPH.get(road_type, 50.0)

    # 3) Final fallback
    if speed is None:
        speed = 50.0

    return speed


def get_oneway_code(row):
    """
    Read Geofabrik 'oneway' flag for roads layer.

    Values (per docs):
      'F' - only along the geometry (forward)
      'T' - only against the geometry (reverse)
      'B' or empty - both directions

    If column is missing or unknown, default to 'B'.
    """
    oneway_col = None
    for col in row.index:
        if col.lower() == "oneway":
            oneway_col = col
            break

    if oneway_col is None:
        return "B"

    val = str(row[oneway_col]).strip().upper()

    if val in {"F", "T", "B"}:
        return val

    # If something odd, assume bidirectional
    return "B"


def geometry_to_segments(geom):
    """
    Given a geometry (LineString or MultiLineString),
    yield one or more (start_point, end_point, length_m) segments.

    start_point and end_point are (x, y) in projected coordinates.
    Note: this uses only the endpoints of each linestring for a single segment.
    """
    if geom is None or geom.is_empty:
        return

    if isinstance(geom, LineString):
        coords = list(geom.coords)
        if len(coords) >= 2:
            yield coords[0], coords[-1], geom.length

    elif isinstance(geom, MultiLineString):
        for line in geom:
            coords = list(line.coords)
            if len(coords) >= 2:
                yield coords[0], coords[-1], line.length


# ========== MAIN SCRIPT ==========

def main():
    if not os.path.exists(ROADS_SHP_PATH):
        raise FileNotFoundError(f"Could not find {ROADS_SHP_PATH} — check your path.")

    print("Loading roads shapefile...")
    roads = gpd.read_file(ROADS_SHP_PATH)
    print(f"Total road records in shapefile: {len(roads)}")

    # Ensure we are in WGS84 initially (EPSG:4326)
    if roads.crs is None:
        print("WARNING: roads CRS is None. Assuming EPSG:4326 (WGS84).")
        roads.set_crs(epsg=4326, inplace=True)

    # Optionally filter to a bounding box (in WGS84)
    if USE_BBOX:
        lon_min, lon_max, lat_min, lat_max = BBOX
        print(f"Filtering to bounding box: {BBOX}")
        roads = roads.cx[lon_min:lon_max, lat_min:lat_max]
        print(f"Road records after BBOX filter: {len(roads)}")

    # Road class column: 'highway' (OSM-style) or 'fclass' (Geofabrik)
    highway_col = None
    for col in roads.columns:
        if col.lower() in ("highway", "fclass"):
            highway_col = col
            break

    if highway_col is None:
        raise ValueError("Could not find a 'highway' or 'fclass' column in the roads data.")

    print(f"Using '{highway_col}' as the road class column.")

    # Drivable classes per Geofabrik docs (roads layer)
    driveable_classes = [
        "motorway", "trunk", "primary", "secondary", "tertiary",
        "unclassified", "residential", "living_street", "pedestrian",
        "motorway_link", "trunk_link", "primary_link",
        "secondary_link", "tertiary_link",
        "service", "track",
        "track_grade1", "track_grade2", "track_grade3", "track_grade4", "track_grade5",
        "bridleway", "cycleway", "footway", "path", "steps",
        "busway",
    ]

    roads = roads[roads[highway_col].isin(driveable_classes)]
    print(f"Road records after filtering to drivable classes: {len(roads)}")

    # Project to a metric CRS for accurate length (Web Mercator EPSG:3857 is fine)
    print("Projecting to EPSG:3857 for length calculation...")
    roads_proj = roads.to_crs(epsg=3857)

    # Explode MultiLineStrings into simple LineStrings
    if "geometry" in roads_proj.columns:
        print("Exploding multi-part geometries (if any)...")
        roads_proj = roads_proj.explode(ignore_index=True)

    # Compute length in meters
    print("Computing segment lengths...")
    roads_proj["length_m"] = roads_proj.geometry.length

    # Compute speed and travel time
    print("Inferring speeds and travel times...")
    roads_proj["speed_kph"] = roads_proj.apply(infer_speed_kph, axis=1)

    # Avoid zero or negative speeds
    roads_proj.loc[roads_proj["speed_kph"] <= 0, "speed_kph"] = 50.0

    # travel_time = length / (speed [m/s]) ; convert kph -> m/s by * 1000/3600
    roads_proj["travel_time_s"] = roads_proj["length_m"] / (
        roads_proj["speed_kph"] * 1000 / 3600
    )

    print("Example of processed attributes:")
    print(roads_proj[[highway_col, "length_m", "speed_kph", "travel_time_s"]].head())

    # Build a directed graph
    print("Building NetworkX directed graph (this may take a while)...")
    G = nx.DiGraph()

    for idx, row in roads_proj.iterrows():
        geom = row.geometry

        for start, end, length_m in geometry_to_segments(geom):
            sx, sy = start
            ex, ey = end

            u = (sx, sy)
            v = (ex, ey)

            speed_kph = row["speed_kph"]
            tt_s = row["travel_time_s"]
            road_type = row[highway_col]
            oneway_code = get_oneway_code(row)

            # 'F' or 'B' → forward edge u -> v
            if oneway_code in ("F", "B"):
                G.add_edge(
                    u,
                    v,
                    length_m=length_m,
                    speed_kph=speed_kph,
                    travel_time_s=tt_s,
                    highway=road_type,
                )

            # 'T' or 'B' → reverse edge v -> u
            if oneway_code in ("T", "B"):
                G.add_edge(
                    v,
                    u,
                    length_m=length_m,
                    speed_kph=speed_kph,
                    travel_time_s=tt_s,
                    highway=road_type,
                )

    print(f"Graph built with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")

    # Simple degree centrality as a quick sanity check
    print("Computing degree centrality for a sanity check (this is fast)...")
    degree_centrality = nx.degree_centrality(G)
    top_10 = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:10]
    print("Top 10 nodes by degree centrality:")
    for node, dc in top_10:
        print(f"Node {node}: degree centrality = {dc:.5f}")

    # Save the graph (GraphML)
    print(f"Saving graph to {OUTPUT_GRAPHML} ...")
    nx.write_graphml(G, OUTPUT_GRAPHML)
    print("Saved GraphML.")

    # Save fast-loading pickle
    print(f"Saving fast-loading pickle version to {OUTPUT_PICKLE} ...")
    with open(OUTPUT_PICKLE, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("Saved pickle. You can now load this graph quickly in notebooks.")


if __name__ == "__main__":
    main()
