import pandas as pd

df = pd.read_csv("shelters.csv")

print("Data availability analysis:")
print("="*60)

capacity_cols = [
    "CAPACITY_ACTUAL_BED",
    "CAPACITY_FUNDING_BED", 
    "CAPACITY_ACTUAL_ROOM",
    "CAPACITY_FUNDING_ROOM",
    "OCCUPIED_BEDS",
    "OCCUPIED_ROOMS",
    "OCCUPANCY_RATE_BEDS",
    "OCCUPANCY_RATE_ROOMS"
]

for col in capacity_cols:
    if col in df.columns:
        non_null = df[col].notna().sum()
        total = len(df)
        pct = (non_null / total) * 100
        print(f"{col:30s}: {non_null:5d}/{total:5d} ({pct:5.1f}%)")
    else:
        print(f"{col:30s}: NOT FOUND")