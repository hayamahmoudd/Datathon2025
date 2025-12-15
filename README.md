# ShelterMap Toronto (Sheridan Datathon 2025)

ShelterMap Toronto is a full stack web app built during a 24 hour datathon to help city planners quickly spot high pressure neighbourhoods for shelter placement. We cleaned and joined Toronto homelessness related datasets, then visualized high pressure areas on an interactive map.

## Demo
YouTube demo: https://www.youtube.com/watch?v=xvR5SX63CX0

## Repo structure
- `homeless-map/` Frontend map app (interactive map UI)
- `backend/` Data processing and backend logic (cleaning, joining, serving data)

## What it does
- Cleans and joins multiple homelessness related datasets into one usable dataset
- Computes a high pressure view to highlight areas that may need attention
- Visualizes results on an interactive map so users can explore neighbourhoods quickly

## Tech stack
- Frontend: Next.js + Leaflet (map)
- Backend: data processing + API (see `backend/`)
- Cloud: Google Cloud (used during the datathon)

## Getting started (local)

### Prerequisites
- Node.js 18+ (or 20+)
- Python 3.10+ 

### 1) Clone
```bash
git clone https://github.com/hayamahmoudd/Datathon2025.git
cd Datathon2025