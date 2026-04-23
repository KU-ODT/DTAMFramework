# Map Tilt Loading Optimization

Updated: 2026-02-10

## Goal
- Reduce perceived loading delay when switching from 2D view to tilted 3D view.

## Applied Changes
- Added MapLibre worker prewarm before map creation.
- Added background tile warmup (vector + DEM) after map load:
  - Prefetches around current center and Seoul area.
  - Runs with idle/delayed scheduling and bounded concurrency.
  - Uses bounded tile budget to avoid excessive network load.
- Added terrain toggle hysteresis:
  - `pitchEnableThreshold`: 8
  - `pitchDisableThreshold`: 5
  - Prevents rapid on/off toggling near the threshold.
- Hillshade visibility now follows active terrain state.

## Tunable Config
Location: `app/web/app.js`
- `config.perf.prefetch.maxTiles`
- `config.perf.prefetch.concurrency`
- `config.perf.prefetch.vectorZooms`
- `config.perf.prefetch.demZooms`
- `config.perf.prefetch.seoulBounds`
- `config.dem.pitchEnableThreshold`
- `config.dem.pitchDisableThreshold`

## Notes
- This improves first tilt responsiveness by warming likely-needed tiles in advance.
- If startup network traffic is too high, reduce `maxTiles` or `concurrency`.
