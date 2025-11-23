from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import math
import os

app = FastAPI()

# -------------------------------------
# PATH FIX — ALWAYS READ CSV FROM BACKEND FOLDER
# -------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def csv(path):
    return os.path.join(BASE_DIR, path)

# -------------------------------------
# ENABLE CORS FOR FRONTEND
# -------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "ShelterMap Toronto API is running"}

# -------------------------------------
# HELPER: SAFE FLOAT (avoid NaN JSON crash)
# -------------------------------------
def safe_float(x, default=0.0):
    try:
        x = float(x)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except:
        return default

# -------------------------------------
# HELPER: MAKE CIRCLE AROUND CLUSTER CENTROID
# -------------------------------------
def make_circle(lat, lon, radius_km=1.2):
    points = []
    for angle in range(0, 360, 15):
        theta = math.radians(angle)
        dx = radius_km * 111 * math.cos(theta)
        dy = radius_km * 111 * math.sin(theta)
        points.append([
            lat + dy / 111,
            lon + dx / (111 * math.cos(math.radians(lat)))
        ])
    return points

# -------------------------------------
# SHELTERS
# -------------------------------------
@app.get("/shelters")
def shelters():
    df = pd.read_csv(csv("shelters_out.csv"))
    df = df.fillna(0)
    return df.to_dict(orient="records")

# -------------------------------------
# DEMAND (homeless points)
# -------------------------------------
@app.get("/homeless")
def homeless():
    df = pd.read_csv(csv("demand_out.csv"))
    df = df.fillna(0)
    return df.to_dict(orient="records")

# -------------------------------------
# CLUSTERS WITH FULL METRICS + BOUNDARIES
# -------------------------------------
@app.get("/clusters")
def clusters():
    df = pd.read_csv(csv("clusters_out.csv"))
    df = df.fillna(0)

    results = []
    for _, row in df.iterrows():
        centroid_lat = safe_float(row["centroid_lat"])
        centroid_lon = safe_float(row["centroid_lon"])

        results.append({
            "cluster_id": int(row["cluster_id"]),
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon,
            "population_weighted": safe_float(row.get("population_weighted", 0)),
            "avg_shelter_distance_km": safe_float(row.get("avg_shelter_distance_km", 0)),
            "boundary": make_circle(centroid_lat, centroid_lon)
        })

    return results
