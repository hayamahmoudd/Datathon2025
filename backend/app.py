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
# CLUSTERS WITH RECOMMENDATIONS
# -------------------------------------
@app.get("/clusters")
def clusters():
    df = pd.read_csv(csv("clusters_out.csv"))
    df = df.fillna(0)

    results = []
    for _, row in df.iterrows():
        recommended_lat = safe_float(row.get("recommended_lat", 0))
        recommended_lon = safe_float(row.get("recommended_lon", 0))
        distance = safe_float(row.get("distance_to_nearest_shelter_km", 1.0))

        results.append({
            "cluster_id": int(row["cluster_id"]),
            "recommended_lat": recommended_lat,
            "recommended_lon": recommended_lon,
            "avg_severity_index": safe_float(row.get("avg_severity_index", 0)),
            "distance_to_nearest_shelter_km": distance,
            "need_score": safe_float(row.get("need_score", 0)),
            "priority": str(row.get("priority", "UNKNOWN")),
            "boundary": make_circle(recommended_lat, recommended_lon, radius_km=distance)
        })

    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)