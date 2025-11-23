"use client";

import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  CircleMarker,
  Polygon
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Blue shelter icon
const shelterIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

// Red marker for encampments - using a custom data URL
const encampmentIcon = L.icon({
  iconUrl: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='25' height='41' viewBox='0 0 25 41'%3E%3Cpath fill='%23e74c3c' stroke='%23000' stroke-width='1' d='M12.5 0C5.6 0 0 5.6 0 12.5c0 8.4 12.5 28.5 12.5 28.5S25 20.9 25 12.5C25 5.6 19.4 0 12.5 0z'/%3E%3Ccircle cx='12.5' cy='12.5' r='6' fill='%23fff'/%3E%3C/svg%3E",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

// Function to get color based on avg_shelter_distance
const getClusterColor = (avgDistance) => {
  if (avgDistance < 1) return "#2ecc71"; // Green - good coverage
  if (avgDistance < 1.5) return "#f39c12"; // Orange - moderate
  if (avgDistance < 2) return "#e67e22"; // Dark orange - concerning
  return "#e74c3c"; // Red - poor coverage
};

export default function TorontoMap() {
  const [shelters, setShelters] = useState([]);
  const [demand, setDemand] = useState([]);
  const [clusters, setClusters] = useState([]);

  useEffect(() => {
    async function loadData() {
      try {
        const sheltersRes = await fetch("http://127.0.0.1:8000/shelters");
        const clustersRes = await fetch("http://127.0.0.1:8000/clusters");
        const demandRes = await fetch("http://127.0.0.1:8000/homeless");

        setShelters(await sheltersRes.json());
        setClusters(await clustersRes.json());
        setDemand(await demandRes.json());
      } catch (err) {
        console.error("Failed to fetch:", err);
      }
    }
    loadData();
  }, []);

  return (
    <MapContainer center={[43.7, -79.4]} zoom={11} style={{ height: "100vh", width: "100%" }}>
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Render clusters with color coding */}
      {clusters.map((c, i) => {
        const color = getClusterColor(c.avg_shelter_distance_km);
        return (
          <Polygon 
            key={i} 
            positions={c.boundary} 
            color={color}
            weight={3} 
            fillColor={color}
            fillOpacity={0.15}
            opacity={0.8}
          >
            <Popup>
              <b>Cluster #{c.cluster_id}</b><br />
              Population: {(c.population_weighted ?? 0).toFixed(1)}<br />
              Avg Distance to Shelter: <b>{(c.avg_shelter_distance_km ?? 0).toFixed(2)} km</b><br />
              <span style={{color: color, fontWeight: 'bold'}}>
                {c.avg_shelter_distance_km < 1 ? '✓ Good Coverage' : 
                 c.avg_shelter_distance_km < 2 ? '⚠ Moderate Coverage' : 
                 '⚠ Poor Coverage - Needs Shelter'}
              </span>
            </Popup>
          </Polygon>
        );
      })}

      {/* Shelters with blue markers */}
      {shelters.map((s, i) => (
        <Marker key={`shelter-${i}`} position={[s.lat, s.lon]} icon={shelterIcon}>
          <Popup>
            <b>🏠 SHELTER: {s.name}</b><br />
            Capacity: {s.capacity}<br />
            Occupied: {s.occupied}<br />
            Occupancy Rate: <b>{(s.occ_rate ?? 0).toFixed(1)}%</b>
            {s.occ_rate > 95 && <span style={{color: 'red'}}> (Nearly Full!)</span>}
          </Popup>
        </Marker>
      ))}

      {/* Encampments with red markers */}
      {demand.map((d, i) => (
        <Marker
          key={`encampment-${i}`}
          position={[d.lat, d.lon]}
          icon={encampmentIcon}
        >
          <Popup>
            <b>⛺ ENCAMPMENT: {d.point_name}</b><br />
            Estimated Population: <b>{d.weight}</b><br />
            <span style={{color: '#e74c3c'}}>Homeless demand point</span>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}