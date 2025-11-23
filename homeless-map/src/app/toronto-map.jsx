"use client";

import { useEffect, useState } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  Circle
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Blue shelter icon (existing shelters)
const shelterIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

// Red marker for encampments
const encampmentIcon = L.icon({
  iconUrl: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='25' height='41' viewBox='0 0 25 41'%3E%3Cpath fill='%23e74c3c' stroke='%23000' stroke-width='1' d='M12.5 0C5.6 0 0 5.6 0 12.5c0 8.4 12.5 28.5 12.5 28.5S25 20.9 25 12.5C25 5.6 19.4 0 12.5 0z'/%3E%3Ccircle cx='12.5' cy='12.5' r='6' fill='%23fff'/%3E%3C/svg%3E",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});

// Green star for recommended new shelter locations
const recommendedIcon = L.icon({
  iconUrl: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 24 24'%3E%3Cpath fill='%2327ae60' stroke='%23000' stroke-width='1' d='M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z'/%3E%3C/svg%3E",
  iconSize: [32, 32],
  iconAnchor: [16, 32],
});

// Get severity classification from index (0-100)
const getSeverityLevel = (index) => {
  if (index >= 80) return { 
    level: "CRITICAL", 
    color: "#c0392b",
    description: "Very large encampment with urgent needs"
  };
  if (index >= 60) return { 
    level: "HIGH", 
    color: "#e74c3c",
    description: "Large encampment requiring attention"
  };
  if (index >= 40) return { 
    level: "MODERATE", 
    color: "#f39c12",
    description: "Medium-sized encampment"
  };
  if (index >= 20) return { 
    level: "LOW", 
    color: "#3498db",
    description: "Small encampment"
  };
  return { 
    level: "MINIMAL", 
    color: "#95a5a6",
    description: "Very small or isolated location"
  };
};

// Get color based on priority
const getPriorityColor = (priority) => {
  switch(priority) {
    case "HIGH": return "#e74c3c";
    case "MEDIUM-HIGH": return "#e67e22";
    case "MEDIUM": return "#f39c12";
    case "MEDIUM-LOW": return "#3498db";
    case "LOW": return "#95a5a6";
    default: return "#95a5a6";
  }
};

// Get need score level (0-100 scale)
const getNeedLevel = (score) => {
  if (score >= 80) return { label: "CRITICAL", color: "#c0392b" };
  if (score >= 60) return { label: "URGENT", color: "#e74c3c" };
  if (score >= 40) return { label: "HIGH", color: "#f39c12" };
  if (score >= 20) return { label: "MODERATE", color: "#3498db" };
  return { label: "LOW", color: "#95a5a6" };
};

export default function TorontoMap() {
  const [shelters, setShelters] = useState([]);
  const [demand, setDemand] = useState([]);
  const [recommendations, setRecommendations] = useState([]);

  useEffect(() => {
    async function loadData() {
      try {
        const sheltersRes = await fetch("http://127.0.0.1:8000/shelters");
        const demandRes = await fetch("http://127.0.0.1:8000/homeless");
        const clustersRes = await fetch("http://127.0.0.1:8000/clusters");

        setShelters(await sheltersRes.json());
        setDemand(await demandRes.json());
        setRecommendations(await clustersRes.json());
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

      {/* Existing Shelters - Blue markers */}
      {shelters.map((s, i) => (
        <Marker key={`shelter-${i}`} position={[s.lat, s.lon]} icon={shelterIcon}>
          <Popup>
            <div style={{minWidth: '200px'}}>
              <h3 style={{margin: '0 0 8px 0', fontSize: '14px'}}>🏠 {s.name}</h3>
              <div style={{fontSize: '12px'}}>
                <strong>Address:</strong> {s.address}<br/>
                <strong>Capacity:</strong> {s.avg_capacity_beds ? Math.round(s.avg_capacity_beds) : 'N/A'} beds<br/>
                <strong>Occupied:</strong> {s.avg_occupied_beds ? Math.round(s.avg_occupied_beds) : 'N/A'} beds<br/>
                <strong>Occupancy Rate:</strong> <span style={{color: s.occ_rate > 95 ? 'red' : 'green'}}>{(s.occ_rate || 0).toFixed(0)}%</span>
                {s.occ_rate > 95 && <div style={{color: 'red', fontWeight: 'bold', marginTop: '4px'}}>⚠ Nearly Full!</div>}
              </div>
            </div>
          </Popup>
        </Marker>
      ))}

      {/* Encampments - Red markers with severity */}
      {demand.map((d, i) => {
        const severity = getSeverityLevel(d.weight);
        return (
          <Marker
            key={`encampment-${i}`}
            position={[d.lat, d.lon]}
            icon={encampmentIcon}
          >
            <Popup>
              <div style={{minWidth: '220px'}}>
                <h3 style={{margin: '0 0 8px 0', fontSize: '14px'}}>⛺ {d.point_name}</h3>
                <div style={{
                  backgroundColor: severity.color,
                  color: 'white',
                  padding: '6px 10px',
                  borderRadius: '4px',
                  fontWeight: 'bold',
                  marginBottom: '8px',
                  textAlign: 'center',
                  fontSize: '13px'
                }}>
                  {severity.level} SEVERITY
                </div>
                <div style={{fontSize: '12px'}}>
                  <strong>Severity Index:</strong> {Math.round(d.weight)}/100<br/>
                  <strong>Classification:</strong> {severity.level}<br/>
                  <div style={{
                    marginTop: '8px',
                    padding: '8px',
                    backgroundColor: '#f8f9fa',
                    borderRadius: '4px',
                    fontSize: '11px',
                    color: '#555'
                  }}>
                    📊 {severity.description}
                  </div>
                </div>
              </div>
            </Popup>
          </Marker>
        );
      })}

      {/* Recommended New Shelter Locations */}
      {recommendations.map((rec, i) => {
        const color = getPriorityColor(rec.priority);
        const needLevel = getNeedLevel(rec.need_score);
        return (
          <div key={`rec-${i}`}>
            <Circle
              center={[rec.recommended_lat, rec.recommended_lon]}
              radius={rec.distance_to_nearest_shelter_km * 1000}
              pathOptions={{
                color: color,
                fillColor: color,
                fillOpacity: 0.1,
                weight: 2,
                dashArray: '5, 5'
              }}
            />
            
            <Marker 
              position={[rec.recommended_lat, rec.recommended_lon]} 
              icon={recommendedIcon}
            >
              <Popup>
                <div style={{minWidth: '260px'}}>
                  <h3 style={{margin: '0 0 8px 0', fontSize: '16px', color: '#27ae60'}}>
                    ⭐ RECOMMENDED NEW SHELTER
                  </h3>
                  <div style={{
                    backgroundColor: color,
                    color: 'white',
                    padding: '6px 12px',
                    borderRadius: '4px',
                    fontWeight: 'bold',
                    marginBottom: '8px',
                    textAlign: 'center'
                  }}>
                    {rec.priority} PRIORITY
                  </div>
                  <div style={{fontSize: '12px'}}>
                    <strong>Cluster ID:</strong> {rec.cluster_id}<br/>
                    <strong>Avg Severity Index:</strong> {Math.round(rec.avg_severity_index)}/100<br/>
                    <strong>Distance to Nearest Shelter:</strong> {rec.distance_to_nearest_shelter_km?.toFixed(2)} km<br/>
                    
                    <div style={{
                      marginTop: '8px',
                      padding: '8px',
                      backgroundColor: needLevel.color,
                      color: 'white',
                      borderRadius: '4px',
                      fontWeight: 'bold',
                      textAlign: 'center'
                    }}>
                      NEED: {needLevel.label}
                    </div>
                    
                    <div style={{
                      marginTop: '4px',
                      fontSize: '11px',
                      textAlign: 'center',
                      color: '#666'
                    }}>
                      Need Score: {Math.round(rec.need_score)}/100
                    </div>

                    <div style={{
                      marginTop: '10px',
                      padding: '8px',
                      backgroundColor: '#f8f9fa',
                      borderRadius: '4px',
                      fontSize: '11px'
                    }}>
                      💡 <strong>Recommendation:</strong><br/>
                      {rec.priority === 'HIGH' && 'Build shelter here ASAP - significant need!'}
                      {rec.priority === 'MEDIUM-HIGH' && 'Strong candidate for new shelter'}
                      {rec.priority === 'MEDIUM' && 'Consider for future expansion'}
                      {rec.priority === 'MEDIUM-LOW' && 'Lower priority - monitor situation'}
                      {rec.priority === 'LOW' && 'Well-served area - no immediate need'}
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          </div>
        );
      })}

      {/* Main Legend */}
      <div style={{
        position: 'absolute',
        bottom: '30px',
        right: '10px',
        backgroundColor: 'white',
        padding: '14px',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
        zIndex: 1000,
        fontSize: '12px',
        maxWidth: '280px'
      }}>
        <div style={{fontWeight: 'bold', marginBottom: '10px', fontSize: '13px'}}>Map Legend</div>
        
        {/* Map Markers */}
        <div style={{marginBottom: '12px'}}>
          <div style={{display: 'flex', alignItems: 'center', marginBottom: '6px'}}>
            <div style={{width: '14px', height: '14px', backgroundColor: '#3498db', marginRight: '10px', borderRadius: '50%'}}></div>
            <span>Existing Shelters</span>
          </div>
          <div style={{display: 'flex', alignItems: 'center', marginBottom: '6px'}}>
            <div style={{width: '14px', height: '14px', backgroundColor: '#e74c3c', marginRight: '10px', borderRadius: '50%'}}></div>
            <span>Encampments</span>
          </div>
          <div style={{display: 'flex', alignItems: 'center', marginBottom: '6px'}}>
            <span style={{marginRight: '10px', fontSize: '14px'}}>⭐</span>
            <span>Recommended Sites</span>
          </div>
        </div>

        {/* Severity Index Scale */}
        <div style={{
          borderTop: '1px solid #ddd',
          paddingTop: '10px',
          marginTop: '10px'
        }}>
          <div style={{fontWeight: 'bold', marginBottom: '8px', fontSize: '12px'}}>
            Severity Index (0-100)
          </div>
          <div style={{fontSize: '11px', lineHeight: '1.6'}}>
            <div style={{display: 'flex', alignItems: 'center', marginBottom: '4px'}}>
              <div style={{
                width: '12px',
                height: '12px',
                backgroundColor: '#c0392b',
                marginRight: '8px',
                borderRadius: '2px'
              }}></div>
              <span><strong>80-100:</strong> Critical</span>
            </div>
            <div style={{display: 'flex', alignItems: 'center', marginBottom: '4px'}}>
              <div style={{
                width: '12px',
                height: '12px',
                backgroundColor: '#e74c3c',
                marginRight: '8px',
                borderRadius: '2px'
              }}></div>
              <span><strong>60-79:</strong> High</span>
            </div>
            <div style={{display: 'flex', alignItems: 'center', marginBottom: '4px'}}>
              <div style={{
                width: '12px',
                height: '12px',
                backgroundColor: '#f39c12',
                marginRight: '8px',
                borderRadius: '2px'
              }}></div>
              <span><strong>40-59:</strong> Moderate</span>
            </div>
            <div style={{display: 'flex', alignItems: 'center', marginBottom: '4px'}}>
              <div style={{
                width: '12px',
                height: '12px',
                backgroundColor: '#3498db',
                marginRight: '8px',
                borderRadius: '2px'
              }}></div>
              <span><strong>20-39:</strong> Low</span>
            </div>
            <div style={{display: 'flex', alignItems: 'center'}}>
              <div style={{
                width: '12px',
                height: '12px',
                backgroundColor: '#95a5a6',
                marginRight: '8px',
                borderRadius: '2px'
              }}></div>
              <span><strong>0-19:</strong> Minimal</span>
            </div>
          </div>
        </div>

        {/* Need Score Info */}
        <div style={{
          marginTop: '10px',
          paddingTop: '8px',
          borderTop: '1px solid #ddd',
          fontSize: '10px',
          color: '#666',
          fontStyle: 'italic'
        }}>
          Need Score = Severity × Distance (normalized to 0-100)
        </div>
      </div>
    </MapContainer>
  );
}