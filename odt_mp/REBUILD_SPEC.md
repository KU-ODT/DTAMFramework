# ODT Mission Planner - Complete Rebuild Specification

## Overview
Rebuild the current Qt-based UAM mission planner into a modern **FastAPI + HTML/CSS/JS** web application.
The app serves local `.mbtiles` vector tiles and `.osm.pbf` building data, provides AirSim integration for mission execution/telemetry, and offers a GCS-quality mission planning interface.

## Architecture

### Backend: FastAPI (Python)
- **Port 8080** (configurable)
- Serve vector tiles from `resources/korea.mbtiles` at `/tiles/{z}/{x}/{y}.pbf`
- Serve building data from `resources/south-korea-260108.osm.pbf` (convert to GeoJSON via osmium or similar at startup, serve as vector tile source or GeoJSON chunks)
- Serve static files from `app/web/` directory
- Serve data files (CSV) from `data/` directory
- REST API endpoints:
  - `GET /api/config` — return map config (center, zoom, tile info, airsim defaults)
  - `GET /api/vertiports` — return vertiport data from CSV
  - `GET /api/waypoints` — return waypoint data from CSV
  - `POST /api/route` — compute route using RoutePlanner (reuse existing `app/route_planner.py`)
  - `POST /api/route/via` — compute route with via points
  - `POST /api/mission/start` — start AirSim mission
  - `POST /api/mission/stop` — stop AirSim mission
  - `POST /api/telemetry/start` — start telemetry streaming
  - `POST /api/telemetry/stop` — stop telemetry
  - `GET /api/settings` — get current settings
  - `PUT /api/settings` — update settings (AirSim host/port, etc.)
- WebSocket endpoint `/ws/telemetry` for real-time vehicle position updates
- Reuse existing Python modules: `app/mbtiles.py`, `app/route_planner.py`, `app/airsim/` (telemetry, mission_runner, coord_transform)

### Frontend: Pure HTML + CSS + JavaScript (NO frameworks)
- Single HTML page with MapLibre GL JS for the map
- Apple-inspired dark/sophisticated design aesthetic
- Color palette: Deep navy/charcoal background (#0a0e1a → #141824), subtle blue accents (#3b82f6), muted warm grays for surfaces
- Smooth, elegant animations everywhere (CSS transitions, requestAnimationFrame)

## Map Requirements

### Base Map (MBTiles - Vector Tiles)
- Use MapLibre GL JS to render vector tiles from local server
- The mbtiles file uses PBF format (vector tiles), NOT raster
- Create a beautiful style with these layer colors:
  - **Light theme**: soft pastels — background #f0f2f5, land #e8ebe4, water #b4cfe0, roads #d4cbb8, parks #c8dfc0
  - **Dark theme**: deep rich tones — background #0a0e1a, land #141824, water #0c1a2e, roads #2a2840, parks #0f2018
- Smooth zoom transitions with `fadeDuration` on layers
- Layers should appear/disappear smoothly based on zoom level (use `minzoom`/`maxzoom` with paint opacity transitions)
- When tilting the view (pitch), transition to 3D perspective smoothly
- DO NOT show 2D and 3D simultaneously — when pitch > 10°, it should feel fully 3D

### Buildings (OSM PBF)
- Parse the OSM PBF file at server startup to extract building footprints as GeoJSON
- Serve buildings as a GeoJSON endpoint or vector tile source
- Render buildings as 3D extrusions when in 3D mode (pitch > 15°)
- Toggle buildings on/off with smooth fade animation
- Building colors: subtle translucent surfaces matching theme
- If the PBF file is too large to parse in memory, use a simplified approach:
  - Extract buildings within the map bounds on demand
  - Or serve pre-processed GeoJSON tiles

### Map Interaction
- Smooth zoom with scroll wheel (with easing)
- Smooth tilt by right-click drag or Ctrl+drag
- Rotation by Ctrl+right-click drag
- Double-click to zoom in with animation
- Pitch transitions should smoothly switch between 2D flat view and 3D perspective
- Map controls: compass (click to reset north), zoom +/-, pitch slider

## UI Design — Apple/GCS Aesthetic

### Layout
- Full-screen map as the canvas
- **Left sidebar** — collapsible, slides in/out with smooth animation (width: 340px when open)
  - Trigger: hamburger icon or < > toggle button at the top-left
  - Sections (accordion style):
    1. **Mission Planning** — main section
    2. **Vertiports** — list/table of vertiports
    3. **Corridors** — waypoint/corridor data
    4. **Settings** — AirSim connection, theme, etc.
- **Top-right corner**: minimal controls
  - Theme toggle (light/dark) — smooth transition
  - Map style selector (satellite idea, but for local tiles just light/dark)
- **Bottom bar**: mission execution controls
  - Connect to AirSim button
  - Play/Pause/Stop mission
  - Telemetry status indicator (green dot when connected)
  - Current vehicle position readout (lat, lon, alt)
- **No ugly standalone buttons** — everything integrated into panels

### Color System (CSS Custom Properties)
```css
:root {
  /* Dark theme (default) */
  --bg-primary: #0a0e1a;
  --bg-secondary: #141824;
  --bg-surface: #1a1f32;
  --bg-surface-hover: #222840;
  --border: rgba(255, 255, 255, 0.06);
  --text-primary: #e8eaf0;
  --text-secondary: #8890a4;
  --text-muted: #5c6478;
  --accent: #3b82f6;
  --accent-hover: #60a5fa;
  --success: #10b981;
  --warning: #f59e0b;
  --danger: #ef4444;
  --sidebar-width: 340px;
  --transition-fast: 150ms ease;
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 400ms cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme="light"] {
  --bg-primary: #f0f2f5;
  --bg-secondary: #ffffff;
  --bg-surface: #f8f9fb;
  --bg-surface-hover: #eef0f4;
  --border: rgba(0, 0, 0, 0.08);
  --text-primary: #1a1d26;
  --text-secondary: #5c6478;
  --text-muted: #8890a4;
}
```

### Typography
- Font: `"SF Pro Display", "Inter", -apple-system, sans-serif`
- Load Inter from Google Fonts as fallback
- Body text: 13px, medium weight
- Headings: 14-16px, semibold
- Monospace data: `"SF Mono", "JetBrains Mono", monospace` for coordinates

### Animations
- All panel open/close: transform + opacity with cubic-bezier easing
- Map layer visibility: opacity transition 300ms
- Building extrusion: height animates from 0 to actual height on appear
- Hover states: subtle scale(1.02) + background shift
- Loading states: subtle pulse animation
- Buttons: press feedback with scale(0.97)
- Sidebar collapse: transform translateX with spring-like easing

## Mission Planning Features

### Mode 1: Vertiport-to-Vertiport Route
- Select departure vertiport from sidebar list or by clicking on map
- Select arrival vertiport
- System auto-calculates shortest path through waypoint network (using existing RoutePlanner)
- Display route on map as a styled polyline with:
  - Animated gradient (departure → arrival)
  - Waypoint markers along the path
  - Altitude profile shown in a mini chart at the bottom of the sidebar

### Mode 2: Free 3D Mission Planning (QGC-style)
- Toggle "3D Mission Input" mode
- Click on map to place mission waypoints
- Each waypoint gets:
  - Lat/Lon from click position
  - Altitude input (adjustable via drag handle in altitude profile view, or numeric input)
- Show altitude profile as an interactive SVG chart:
  - X-axis: horizontal distance
  - Y-axis: altitude
  - Draggable waypoint nodes to adjust altitude
  - Reference lines for common altitudes (500ft, 1000ft, 2000ft)
- 3D polyline on the map showing the mission path with altitude
- Waypoints are draggable on the map
- Right-click waypoint to delete or edit properties

### Route Visualization
- Route line: gradient colored polyline (blue → cyan)
- Active segment highlight
- Direction arrows along the route (animated)
- Waypoint markers:
  - Vertiports: custom icon (helicopter pad style)
  - Waypoints: numbered circles
  - Free mission points: diamond markers
- In 3D view: route shown as a 3D tube/ribbon at actual altitudes

### Mission Table
- In sidebar, show editable table:
  - #, Name, Lat, Lon, Alt(m), Speed, Action
  - Add/Remove/Reorder rows
  - Click row to zoom to that waypoint on map
  - Edit inline

## Settings Panel
- AirSim Connection:
  - IP Address input
  - Port input
  - Connect/Disconnect button
  - Connection status indicator
- Map Settings:
  - Theme selector (Dark/Light)
  - Building layer toggle
  - Corridor visibility toggle
  - 3D terrain toggle
- Mission Settings:
  - Default speed (m/s)
  - Default altitude (m)
  - Coordinate system selector

## Data Files
- Vertiport CSV: `data/vertiport_default.csv` (Korean headers — see existing columns)
- Waypoint CSV: `data/waypoint_default.csv` (Korean headers)
- The CSVs use Korean column names like `Vertiport 명`, `위도`, `경도`, `고도(ft)`, `Link`

## AirSim Integration (via WebSocket)
- Frontend connects WebSocket for real-time telemetry
- Backend handles actual AirSim communication using existing `app/airsim/` modules
- Mission execution flow:
  1. User plans mission (either mode)
  2. Clicks "Execute Mission" button
  3. Backend receives route, converts to AirSim NED coordinates
  4. Executes via existing `AirsimMissionRunner`
  5. Telemetry streams back via WebSocket
  6. Vehicle icon moves on map in real-time

## Implementation Notes
- Keep ALL existing Python business logic (route_planner.py, airsim/*, mbtiles.py, dem.py, coord_transform.py)
- Replace: `main.py`, `app/gui/*` (Qt), `app/tile_server.py` (old HTTP server), `app/web/*` (old HTML/CSS/JS)
- New entry point: `main.py` runs FastAPI with uvicorn
- Frontend is pure vanilla HTML/CSS/JS — no React, no Vue, no build step
- Use MapLibre GL JS v4 from CDN
- Use Chart.js from CDN for altitude profile (or pure SVG)
- The `.mbtiles` file contains PBF (vector) tiles — use `application/vnd.mapbox-vector-tile` content type
- For the vector tile style, create a maplibre style JSON that references the local tile server
- Buildings from OSM PBF: if parsing is too complex, create a simpler approach (GeoJSON bounding box query, or skip buildings initially and add a note)

## File Structure (New)
```
main.py                     # FastAPI app entry point
app/
  server.py                 # FastAPI application with all endpoints
  mbtiles.py                # (keep existing)
  route_planner.py          # (keep existing)
  dem.py                    # (keep existing)
  config.py                 # (update for new server)
  airsim/                   # (keep all existing)
  web/                      # NEW frontend
    index.html              # Main HTML
    css/
      main.css              # All styles
    js/
      app.js                # Main application logic
      map.js                # Map initialization and management
      sidebar.js            # Sidebar panel logic
      mission.js            # Mission planning logic
      altitude-profile.js   # Altitude profile chart
      telemetry.js          # WebSocket telemetry handler
      settings.js           # Settings management
      utils.js              # Utility functions
resources/                  # (keep existing)
data/                       # (keep existing)
requirements.txt            # Add fastapi, uvicorn, etc.
```

## Critical: Vector Tile Style
The MBTiles contain OpenMapTiles-schema vector tiles. The style must reference layers like:
- `water`, `waterway` — blue tones
- `landcover`, `landuse` — green/earth tones
- `transportation` — road styling by class
- `building` — building footprints
- `boundary` — administrative boundaries
- `park` — park areas
- `poi` — points of interest (labels)
- `place` — place name labels

Style the layers with proper zoom-dependent visibility and smooth transitions.

## Existing app.js Analysis (Key Functions to Port)
The existing `app.js` (3900 lines) contains:
1. CSV parsing for vertiport/waypoint data
2. Map style building for light/dark themes with proper vector tile layers
3. Vertiport rendering with custom icons and 3D models (GLB)
4. Corridor/waypoint rendering with lines and markers
5. Flight plan building with altitude profile SVG
6. AirSim bridge communication (via Qt WebChannel — replace with WebSocket/REST)
7. Telemetry display with vehicle position on map
8. Coordinate transforms (WGS84 → ECEF → ENU, Airsim NED)
9. Route calculation via waypoint graph (frontend side — move to backend API)

Many of these coordinate transform functions and map style definitions should be preserved/ported.
