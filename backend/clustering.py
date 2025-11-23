import pandas as pd
import numpy as np
import time
from sklearn.cluster import KMeans
from geopy.distance import geodesic
from google.cloud import bigquery
import logging

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ----------------------------
# CONFIG
# ----------------------------
SHELTER_CSV = "shelters.csv"
ENCAMPMENT_CSV = "encampments.csv"

PROJECT_ID = "vocal-invention-479123-j1"
DATASET_ID = "homeless_data"

HOMELESS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.homeless_points"
SHELTERS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.shelters"
CLUSTERS_TABLE = f"{PROJECT_ID}.{DATASET_ID}.clusters"

N_CLUSTERS = 5


# ============================================================
# 1) LOAD RAW SHELTER DATA
# ============================================================
print("Loading shelter data...")

df = pd.read_csv(SHELTER_CSV)

cols_needed = [
    "LOCATION_NAME",
    "LOCATION_ADDRESS",
    "CAPACITY_FUNDING_BEDS",
    "OCCUPIED_BEDS",
    "OCCUPANCY_RATE_BEDS"
]

for c in cols_needed:
    if c not in df.columns:
        df[c] = np.nan

df = df[cols_needed].copy()

df["LOCATION_NAME"] = df["LOCATION_NAME"].astype(str).str.strip()
df["LOCATION_ADDRESS"] = df["LOCATION_ADDRESS"].astype(str).str.strip()


# ============================================================
# 2) AGGREGATE SHELTER DATA
# ============================================================
print("Aggregating shelter data...")

agg = df.groupby(["LOCATION_NAME", "LOCATION_ADDRESS"], as_index=False).agg(
    avg_capacity_beds=("CAPACITY_FUNDING_BEDS", "mean"),
    avg_occupied_beds=("OCCUPIED_BEDS", "mean"),
    avg_occ_rate_beds=("OCCUPANCY_RATE_BEDS", "mean")
)

agg["occ_rate"] = agg["avg_occ_rate_beds"]
missing = agg["occ_rate"].isna()
agg.loc[missing, "occ_rate"] = (
    agg.loc[missing, "avg_occupied_beds"] /
    agg.loc[missing, "avg_capacity_beds"]
) * 100

agg["occ_rate"] = agg["occ_rate"].clip(0, 100)


# ============================================================
# 3) GEOCODE (SSL BYPASS + CACHING)
# ============================================================
print("Geocoding addresses (with SSL bypass)...")

# ---- SSL Fix ----
import ssl
ssl_context = ssl._create_unverified_context()

from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

geolocator = Nominatim(
    user_agent="toronto-homeless-datathon",
    ssl_context=ssl_context
)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# ---- Remove rows w/ invalid addresses ----
agg = agg.dropna(subset=["LOCATION_ADDRESS"])
agg = agg[agg["LOCATION_ADDRESS"].str.strip().str.lower() != "nan"]
agg = agg[agg["LOCATION_ADDRESS"].str.len() > 5]
agg = agg.reset_index(drop=True)

# ---- Load cache ----
cache_file = "geocode_cache.csv"
try:
    cache = pd.read_csv(cache_file)
except:
    cache = pd.DataFrame(columns=["LOCATION_ADDRESS", "lat", "lon"])


def geocode_address(addr):
    # Check cache
    row = cache[cache["LOCATION_ADDRESS"] == addr]
    if len(row) > 0:
        return float(row.iloc[0]["lat"]), float(row.iloc[0]["lon"])

    query = f"{addr}, Toronto, ON, Canada"

    try:
        loc = geocode(query, timeout=10)
    except:
        loc = None

    if loc:
        lat, lon = loc.latitude, loc.longitude
    else:
        lat, lon = np.nan, np.nan

    cache.loc[len(cache)] = [addr, lat, lon]
    return lat, lon


# ---- Apply geocoding ----
lats, lons = [], []

for addr in agg["LOCATION_ADDRESS"]:
    lat, lon = geocode_address(addr)
    lats.append(lat)
    lons.append(lon)

agg["lat"] = lats
agg["lon"] = lons

cache.to_csv(cache_file, index=False)

agg = agg.dropna(subset=["lat", "lon"]).reset_index(drop=True)


# ============================================================
# 4) BUILD SHELTERS TABLE FOR BIGQUERY
# ============================================================
print("Preparing shelters table...")

shelters_out = agg.rename(columns={
    "LOCATION_NAME": "name",
    "LOCATION_ADDRESS": "address"
})[[
    "name", "address", "lat", "lon",
    "avg_capacity_beds", "avg_occupied_beds", "occ_rate"
]]


# ============================================================
# 5) LOAD ENCAMPMENTS + COMBINE AS DEMAND POINTS
# ============================================================
print("Loading encampment data...")

enc = pd.read_csv(ENCAMPMENT_CSV)

enc["lat"] = enc["lat"].astype(float)
enc["lon"] = enc["lon"].astype(float)
# ensure encampment weights are numeric; default to 1.0 when missing
if "weight" not in enc.columns:
    enc["weight"] = 1.0
else:
    enc["weight"] = pd.to_numeric(enc["weight"], errors="coerce").fillna(1.0)

# Shelter points
shelter_points = agg.copy()
# compute shelter weights from occupancy rate; default to 0 when unknown
shelter_points["weight"] = (shelter_points["occ_rate"] / 100).clip(0, 1).fillna(0.0)
shelter_points["source"] = "shelter"
shelter_points["name"] = shelter_points["LOCATION_NAME"]

enc_points = enc.copy()
enc_points["source"] = "encampment"

demand = pd.concat([
    shelter_points[["name", "lat", "lon", "weight", "source"]],
    enc_points[["name", "lat", "lon", "weight", "source"]]
]).reset_index(drop=True)


# ============================================================
# 6) WEIGHTED K-MEANS
# ============================================================
print("Clustering demand points...")

expanded = []
for _, r in demand.iterrows():
    # defensively handle missing or NaN weights
    try:
        w = float(r["weight"])
    except Exception:
        w = 0.0
    if np.isnan(w):
        w = 0.0
    reps = max(1, int(round(w * 10)))
    # append plain dicts (avoid keeping pandas Series objects repeated)
    row_dict = r.to_dict()
    for _ in range(reps):
        expanded.append(row_dict)

expanded = pd.DataFrame(expanded)
coords = expanded[["lat", "lon"]]

kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init="auto")
expanded["cluster_id"] = kmeans.fit_predict(coords)

centroids = kmeans.cluster_centers_

# assign clusters to original points
def nearest_cluster(lat, lon):
    dists = [geodesic((lat, lon), (c[0], c[1])).km for c in centroids]
    return int(np.argmin(dists))

demand["cluster_id"] = demand.apply(
    lambda r: nearest_cluster(r["lat"], r["lon"]),
    axis=1
)


# ============================================================
# 7) BUILD CLUSTER SUMMARY
# ============================================================
print("Building cluster summary...")

def nearest_shelter_dist(lat, lon):
    return float(min(
        geodesic((lat, lon), (row.lat, row.lon)).km
        for _, row in agg.iterrows()
    ))

cluster_rows = []
for cid in range(N_CLUSTERS):
    centroid_lat, centroid_lon = centroids[cid]
    pop = demand[demand["cluster_id"] == cid]["weight"].sum()
    dist = nearest_shelter_dist(centroid_lat, centroid_lon)

    cluster_rows.append({
        "cluster_id": cid,
        "centroid_lat": float(centroid_lat),
        "centroid_lon": float(centroid_lon),
        "population_weighted": float(pop),
        "avg_shelter_distance_km": float(dist)
    })

clusters_out = pd.DataFrame(cluster_rows)


# ============================================================
# 8) BIGQUERY UPLOAD
# ============================================================
print("Uploading results to BigQuery...")

client = None
try:
    client = bigquery.Client()
except Exception:
    log.exception("Could not create BigQuery client; continuing without upload")

def upload(df, table_id):
    if client is None:
        log.info("Skipping upload to %s (no BigQuery client)", table_id)
        return
    job = client.load_table_from_dataframe(
        df,
        table_id,
        job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    )
    job.result()

homeless_df = demand.rename(columns={"name": "point_name"})[["point_name", "lat", "lon", "weight", "source", "cluster_id"]]

try:
    upload(homeless_df, HOMELESS_TABLE)
    upload(shelters_out, SHELTERS_TABLE)
    upload(clusters_out, CLUSTERS_TABLE)
    print("\nSUCCESS! Uploaded homeless_points, shelters, and clusters.")
    print(clusters_out)
except Exception as e:
    print("Upload failed:", e)
finally:
    # Always write local CSVs for inspection
    try:
        homeless_df.to_csv("demand_out.csv", index=False)
        shelters_out.to_csv("shelters_out.csv", index=False)
        clusters_out.to_csv("clusters_out.csv", index=False)
        print("Wrote local CSVs: demand_out.csv, shelters_out.csv, clusters_out.csv")
    except Exception as e:
        print("Failed to write local CSVs:", e)
