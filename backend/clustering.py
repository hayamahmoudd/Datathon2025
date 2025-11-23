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
    "CAPACITY_FUNDING_BED",
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
# 2) AGGREGATE SHELTER DATA (IMPROVED NULL HANDLING)
# ============================================================
print("Aggregating shelter data...")

# Remove nulls BEFORE aggregation
df_clean = df[df["CAPACITY_FUNDING_BED"].notna() & 
              df["OCCUPIED_BEDS"].notna()].copy()

print(f"Rows with valid bed data: {len(df_clean)}/{len(df)} ({len(df_clean)/len(df)*100:.1f}%)")

agg = df_clean.groupby(["LOCATION_NAME", "LOCATION_ADDRESS"], as_index=False).agg(
    avg_capacity_beds=("CAPACITY_FUNDING_BED", "mean"),
    avg_occupied_beds=("OCCUPIED_BEDS", "mean"),
    avg_occ_rate_beds=("OCCUPANCY_RATE_BEDS", "mean")
)

# Recalculate ALL occupancy rates (don't trust the original data)
agg["occ_rate"] = (agg["avg_occupied_beds"] / agg["avg_capacity_beds"]) * 100
agg["occ_rate"] = agg["occ_rate"].clip(0, 100).fillna(0)

print(f"Unique shelter locations: {len(agg)}")


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

print(f"Shelters with valid geocoded locations: {len(agg)}")


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
# 5) LOAD ENCAMPMENTS AS DEMAND POINTS (NO SHELTERS IN CLUSTERING)
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

enc["source"] = "encampment"

# ONLY use encampments for clustering
demand = enc[["name", "lat", "lon", "weight", "source"]].copy()

print(f"Clustering {len(demand)} encampment locations...")


# ============================================================
# 6) WEIGHTED K-MEANS ON ENCAMPMENTS ONLY
# ============================================================
print("Clustering homeless demand points...")

expanded = []
for _, r in demand.iterrows():
    try:
        w = float(r["weight"])
    except Exception:
        w = 0.0
    if np.isnan(w):
        w = 0.0
    reps = max(1, int(round(w * 10)))
    row_dict = r.to_dict()
    for _ in range(reps):
        expanded.append(row_dict)

expanded = pd.DataFrame(expanded)
coords = expanded[["lat", "lon"]]

kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init="auto")
expanded["cluster_id"] = kmeans.fit_predict(coords)

centroids = kmeans.cluster_centers_

# assign clusters to original encampment points
def nearest_cluster(lat, lon):
    dists = [geodesic((lat, lon), (c[0], c[1])).km for c in centroids]
    return int(np.argmin(dists))

demand["cluster_id"] = demand.apply(
    lambda r: nearest_cluster(r["lat"], r["lon"]),
    axis=1
)


# ============================================================
# 7) BUILD CLUSTER SUMMARY WITH SHELTER GAP ANALYSIS
# ============================================================
print("Analyzing shelter coverage gaps...")

def nearest_shelter_dist(lat, lon):
    if len(agg) == 0:
        return 999.0
    return float(min(
        geodesic((lat, lon), (row.lat, row.lon)).km
        for _, row in agg.iterrows()
    ))

cluster_rows = []
for cid in range(N_CLUSTERS):
    centroid_lat, centroid_lon = centroids[cid]
    
    # Calculate AVERAGE severity in this cluster (keeps 0-100 scale)
    cluster_demand = demand[demand["cluster_id"] == cid]
    avg_severity = cluster_demand["weight"].mean() if len(cluster_demand) > 0 else 0.0
    
    # Distance to nearest existing shelter
    dist = nearest_shelter_dist(centroid_lat, centroid_lon)
    
    # Calculate raw need score
    need_score_raw = avg_severity * dist
    
    cluster_rows.append({
        "cluster_id": cid,
        "recommended_lat": float(centroid_lat),
        "recommended_lon": float(centroid_lon),
        "avg_severity_index": float(avg_severity),
        "distance_to_nearest_shelter_km": float(dist),
        "need_score_raw": float(need_score_raw),
        "priority": ""
    })

clusters_out = pd.DataFrame(cluster_rows)

# Normalize need scores to 0-100 scale
max_need = clusters_out["need_score_raw"].max()
if max_need > 0:
    clusters_out["need_score"] = (clusters_out["need_score_raw"] / max_need) * 100
else:
    clusters_out["need_score"] = 0

# Rank by need score
clusters_out = clusters_out.sort_values("need_score", ascending=False).reset_index(drop=True)

# Assign priority levels
priorities = ["HIGH", "MEDIUM-HIGH", "MEDIUM", "MEDIUM-LOW", "LOW"]
for i, priority in enumerate(priorities):
    if i < len(clusters_out):
        clusters_out.loc[i, "priority"] = priority

# Drop the raw score column (we only need normalized)
clusters_out = clusters_out.drop(columns=["need_score_raw"])

print("\n" + "="*80)
print("SHELTER RECOMMENDATION ANALYSIS")
print("="*80)
print(clusters_out.to_string(index=False))
print("\nRECOMMENDATIONS:")
print("-" * 80)

for _, row in clusters_out.iterrows():
    print(f"\n[{row['priority']}] Cluster {int(row['cluster_id'])}:")
    print(f"  Location: ({row['recommended_lat']:.6f}, {row['recommended_lon']:.6f})")
    print(f"  Average Severity Index: {row['avg_severity_index']:.1f}/100")
    print(f"  Distance to Nearest Shelter: {row['distance_to_nearest_shelter_km']:.2f} km")
    print(f"  Need Score: {row['need_score']:.1f}/100")


# ============================================================
# 8) BIGQUERY UPLOAD
# ============================================================
print("\n" + "="*80)
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
    print("SUCCESS! Uploaded homeless_points, shelters, and clusters.")
except Exception as e:
    print("Upload failed:", e)
finally:
    # Always write local CSVs for inspection
    try:
        homeless_df.to_csv("demand_out.csv", index=False)
        shelters_out.to_csv("shelters_out.csv", index=False)
        clusters_out.to_csv("clusters_out.csv", index=False)
        print("\nWrote local CSVs: demand_out.csv, shelters_out.csv, clusters_out.csv")
        print("="*80)
    except Exception as e:
        print("Failed to write local CSVs:", e)