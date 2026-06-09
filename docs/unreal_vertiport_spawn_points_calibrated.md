# Unreal vertiport Gate/FATO calibrated spawn points

This table is generated from the actual Unreal Editor preview marker coordinates.

## Calibration

- Calibration vertiport: `잠실`
- Target AirSim settings Z at calibration deck: `294.400` m
- Applied global Z bias: `-16.960066` m
- Formula: `Z = 350.0 - (terrain_h_m + deck_h_m) - 1.0 + bias`

## Mapping

- `FATO 1` = `F1` = `S26`
- `FATO 2` = `F2` = `S25`
- `GATE 1..4` = `G1..G4` = `S16..S13`
- `GATE 5..8` = `G5..G8` = `S04..S01`

## Jamsil sample

| point | label | S-id | X(m) | Y(m) | settings Z(m) | yaw(deg) |
|---|---|---:|---:|---:|---:|---:|
| G1 | GATE 1 | S16 | 8042.230206 | 5873.671975 | 294.423318 | 353.000000 |
| G2 | GATE 2 | S15 | 8040.160523 | 5856.949577 | 294.437325 | 353.000000 |
| G3 | GATE 3 | S14 | 8038.090839 | 5840.227179 | 294.451222 | 353.000000 |
| G4 | GATE 4 | S13 | 8036.002731 | 5823.355917 | 294.465257 | 353.000000 |
| G5 | GATE 5 | S04 | 8082.621982 | 5868.672750 | 294.351974 | 173.000000 |
| G6 | GATE 6 | S03 | 8080.552299 | 5851.950353 | 294.366336 | 173.000000 |
| G7 | GATE 7 | S02 | 8078.482616 | 5835.227955 | 294.380229 | 173.000000 |
| G8 | GATE 8 | S01 | 8076.394508 | 5818.356693 | 294.394640 | 173.000000 |
| F1 | FATO 1 | S26 | 8045.779989 | 5902.353120 | 294.399577 | 83.000000 |
| F2 | FATO 2 | S25 | 8086.171766 | 5897.353896 | 294.330122 | 83.000000 |

## Files

- Primary runtime CSV: `D:\DTAMFramework\MissionModule\data\unreal_vertiport_spawn_points.csv`
- Docs CSV: `D:\DTAMFramework\docs\unreal_vertiport_spawn_points_calibrated.csv`
- Visualization copy: `D:\DTAMFramework\VisualizationModule\data\coordinateDB\unreal_vertiport_spawn_points.csv`
- Unreal runtime copy: `D:\DTAMFramework\VisualizationModule\runtime\Unreal\Environments\DTAMVisualization\Data\coordinateDB\unreal_vertiport_spawn_points.csv`
