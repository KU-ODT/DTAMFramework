# Unreal DT World ???? ?? ????

?? ??: 2026-05-22 02:02:48  
?? ??: `D:\DTAMFramework`

## ??

Unreal Editor?? Play ?? ??? ????/?? ??? `.umap` ??? ????? ?? ?? ???, DTAMVisualization ????? `Data/coordinateDB` CSV? ?? ???? ????. ??? Editor? ?? ?? ???? ??? ?? ???, ?? CSV?? ??? Editor preview? ????.

- ???? ?? ?? ??: `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Data\coordinateDB\vertiport_UE.csv`
- ?? ? ??? ??: `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Data\coordinateDB\vertiportMap_KU.csv`
- ????? Gate/FATO/Taxi ?? ??: `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Data\coordinateDB\resources_vp.csv`
- MissionModule ???: `D:\DTAMFramework\MissionModule\data\resources_vp.csv`

## ??? ???

| ?? | ?? |
|---|---|
| `D:\DTAMFramework\docs\unreal_vertiport_resource_points.csv` | ?? ????? Gate/FATO/Taxi ?? 255?. LLA, X/Y/Z, ??? AirSim spawn down ?? |
| `D:\DTAMFramework\docs\unreal_vertiport_actor_placements.csv` | ???? ?? Anchor LLA/Yaw 17? |
| `D:\DTAMFramework\docs\unreal_vertiport_groundmap_KU_template.csv` | KU ???? ?? ? ??? ?? ?? 29? |
| `D:\DTAMFramework\docs\unreal_vertiport_coordinate_inventory.md` | ? ?? ?? |

## Unreal Editor preview? ??? ?? ??

1. `DTAMVisualizationFlightCorridorActor`? ??? ??? ???. ????? `ProjectDir/Data/coordinateDB`??.
2. `vertiport_UE.csv`? ?? ???? ?? Actor? ???.
3. ? ??? `CesiumGlobeAnchor.MoveToLongitudeLatitudeHeight(lon, lat, 60m)`? ?? ?, ?/?? LineTrace? ?? ?? ??? ???. ?? ?? lift? `8 cm`??.
4. `DTAMVisualizationVertiportPreviewActor`? `vertiportMap_KU.csv`? ?? ??? ?? ?? marker? ???. Editor label? `U X/Y/Z`? ???? ? ?????.
5. `resources_vp.csv`? ? ????? KU ???? ??? Gate/FATO/Taxi? ??? ?? ?????. ?? ??/?? ??? FATO ??? ??? ?? ?? ????.

## ?? ?? ??

### `resources_vp.csv`

| ?? | ?? |
|---|---|
| `pt_lat_deg`, `pt_lon_deg`, `pt_h_m` | ?? ?? ??? LLA/??. Mission route? ?? ?? ?? |
| `X_cm`, `Y_cm` / `X_m`, `Y_m` | DTAM/ODT Unreal-AirSim ?? ??. OperationModule? resource point? ??? ? X/Y? settings spawn? ?? ?? |
| `Z_cm`, `Z_m` | ???? pad/deck ?? ??. Cesium ?? world Z? ??? ??? ?? |
| `Yaw_deg` | ?? ??. FATO? ?? ?? ?? ??? ??? |

### AirSim settings spawn Z ??

?? OperationModule? resource point ?? ?? ?? D/down ??? ?? ??? ????.

```text
AirSimSpawnDown_m = CesiumOriginHeight_m - (pt_h_m + Z_m) - 1.0
```

?? Cesium origin height? `350.0 m`??. ??? FATO ?? ?? pad ??? `X_m/Y_m`? CSV?? ?? ??, `Z/down`? ? ??? ????.

??: `Z_m`? mesh/deck ????, `pt_h_m`? ??/???? ?? ???? ?? ???? ?? ??.

## ??? ??? ??

| label | exists | sha256 | path |
| --- | --- | --- | --- |
| Unreal source coordinateDB | True | 9a48cc05d2ab2939bff2c301bc3c540081b245c121475cf5643b42012abc69f0 | D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization\Data\coordinateDB\resources_vp.csv |
| Unreal runtime coordinateDB | True | 942a96a2a8cd8910948ff8bdbf0f6027f93325534c9451a691b04b838d21a93d | D:\DTAMFramework\VisualizationModule\runtime\Unreal\Environments\DTAMVisualization\Data\coordinateDB\resources_vp.csv |
| MissionModule data | True | 9a48cc05d2ab2939bff2c301bc3c540081b245c121475cf5643b42012abc69f0 | D:\DTAMFramework\MissionModule\data\resources_vp.csv |

?? ????? runtime ???? source/MissionModule? ????, ?? ?? ?? ?? `resources_vp.csv` 255? ??? `X/Y/Z`, `LLA`, `Yaw` ?? source/runtime/MissionModule ? ????. ?? ??? ?? ??/??/BOM ??? ?? ??.

## ????? ?? ?? ??

| vertiport | class | angle_deg | actor_lat | actor_lon | FATO | GATE | TAXI |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 가산 | hub | 87 | 37.489091000000002 | 126.878809 | 2 | 8 | 5 |
| 강남 | hub | 69 | 37.496290999999999 | 127.023303 | 2 | 8 | 5 |
| 광화문 | hub | 130 | 37.569009999999999 | 126.97360399999999 | 2 | 8 | 5 |
| 마곡 | hub | 45 | 37.563535000000002 | 126.791805 | 2 | 8 | 5 |
| 망우 | hub | 344 | 37.596919 | 127.08485400000001 | 2 | 8 | 5 |
| 목동 | port | 10 | 37.526342999999997 | 126.876243 | 2 | 8 | 5 |
| 미아 | port | 74 | 37.630206999999999 | 127.026053 | 2 | 8 | 5 |
| 봉천 | port | 8 | 37.482832000000002 | 126.942245 | 2 | 8 | 5 |
| 사당 | port | 10 | 37.475766999999998 | 126.982185 | 2 | 8 | 5 |
| 상암 | port | 38 | 37.562282000000003 | 126.890156 | 2 | 8 | 5 |
| 성수 | port | 295 | 37.538916999999998 | 127.041635 | 2 | 8 | 5 |
| 수서 | hub | 222 | 37.487440999999997 | 127.10060300000001 | 2 | 8 | 5 |
| 연신내 | port | 43 | 37.611145 | 126.922747 | 2 | 8 | 5 |
| 영등포 | port | 322 | 37.526513000000001 | 126.922845 | 2 | 8 | 5 |
| 용산 | port | 76 | 37.529096000000003 | 126.95839100000001 | 2 | 8 | 5 |
| 잠실 | port | 83 | 37.514368 | 127.069068 | 2 | 8 | 5 |
| 천호 | port | 110 | 37.545732999999998 | 127.11923 | 2 | 8 | 5 |

## FATO ?? ??

?? ?? ??/??? ??? ? ? ?? ?? ?? ?? ???. ?? Gate/Taxi?? ??? 255? ??? `D:\DTAMFramework\docs\unreal_vertiport_resource_points.csv`? ??.

| vertiport | label | lat | lon | h_m | X_m | Y_m | Z_local_m | spawn_D_m | yaw |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 영등포 | FATO 2 | 37.52737823 | 126.92381130 | 30.005 | -4830.009 | 4374.510 | 18.783 | 300.212 | 322.0 |
| 영등포 | FATO 1 | 37.52708339 | 126.92409660 | 30.012 | -4804.782 | 4407.232 | 18.783 | 300.205 | 322.0 |
| 잠실 | FATO 2 | 37.51409724 | 127.06938760 | 33.673 | 8043.853 | 5843.487 | 4.037 | 311.290 | 83.0 |
| 잠실 | FATO 1 | 37.51405460 | 127.06892340 | 33.603 | 8002.812 | 5848.258 | 4.037 | 311.360 | 83.0 |
| 상암 | FATO 2 | 37.56183252 | 126.89141100 | 31.916 | -7693.143 | 550.417 | 20.723 | 296.361 | 38.0 |
| 상암 | FATO 1 | 37.56154031 | 126.89112090 | 31.927 | -7718.789 | 582.810 | 20.723 | 296.350 | 38.0 |
| 용산 | FATO 2 | 37.52815711 | 126.95898560 | 27.882 | -1719.906 | 4288.783 | 14.316 | 306.802 | 76.0 |
| 용산 | FATO 1 | 37.52806927 | 126.95853140 | 27.876 | -1760.059 | 4298.520 | 14.316 | 306.808 | 76.0 |
| 목동 | FATO 2 | 37.52639689 | 126.87765400 | 28.520 | -8910.366 | 4479.261 | 10.535 | 309.945 | 10.0 |
| 목동 | FATO 1 | 37.52603046 | 126.87757010 | 28.543 | -8917.802 | 4519.903 | 10.535 | 309.922 | 10.0 |
| 미아 | FATO 2 | 37.62931596 | 127.02671750 | 44.236 | 4255.868 | -6933.089 | 28.134 | 276.630 | 74.0 |
| 미아 | FATO 1 | 37.62921580 | 127.02626670 | 44.174 | 4216.079 | -6921.957 | 28.134 | 276.692 | 74.0 |
| 봉천 | FATO 2 | 37.48294539 | 126.94367240 | 39.631 | -3074.207 | 9305.796 | 31.637 | 277.731 | 8.0 |
| 봉천 | FATO 1 | 37.48257689 | 126.94360430 | 39.679 | -3080.221 | 9346.673 | 31.637 | 277.684 | 8.0 |
| 사당 | FATO 2 | 37.47583933 | 126.98361050 | 38.370 | 459.823 | 10093.830 | 24.539 | 286.091 | 10.0 |
| 사당 | FATO 1 | 37.47547297 | 126.98352620 | 38.418 | 452.386 | 10134.472 | 24.539 | 286.043 | 10.0 |
| 성수 | FATO 2 | 37.54003366 | 127.04205090 | 34.143 | 5622.320 | 2969.472 | 15.693 | 299.164 | 295.0 |
| 성수 | FATO 1 | 37.53987385 | 127.04247300 | 34.198 | 5659.653 | 2987.175 | 15.693 | 299.109 | 295.0 |
| 연신내 | FATO 2 | 37.61061493 | 126.92394280 | 32.672 | -4817.716 | -4859.552 | 17.839 | 298.489 | 43.0 |
| 연신내 | FATO 1 | 37.61034404 | 126.92362160 | 32.647 | -4846.088 | -4829.517 | 17.839 | 298.514 | 43.0 |
| 천호 | FATO 2 | 37.54474286 | 127.11904870 | 39.495 | 12428.752 | 2437.783 | -0.761 | 310.266 | 110.0 |
| 천호 | FATO 1 | 37.54487303 | 127.11861080 | 39.399 | 12390.019 | 2423.402 | -0.761 | 310.362 | 110.0 |
| 광화문 | FATO 2 | 37.56814714 | 126.97297850 | 37.982 | -486.223 | -145.242 | 35.381 | 275.637 | 130.0 |
| 광화문 | FATO 1 | 37.56838837 | 126.97262240 | 37.977 | -517.702 | -172.004 | 35.381 | 275.641 | 130.0 |
| 강남 | FATO 2 | 37.49542722 | 127.02405610 | 35.261 | 4036.533 | 7918.953 | 16.472 | 297.267 | 69.0 |
| 강남 | FATO 1 | 37.49529617 | 127.02361880 | 35.231 | 3997.866 | 7933.510 | 16.472 | 297.297 | 69.0 |
| 가산 | FATO 2 | 37.48809625 | 126.87916390 | 32.408 | -8779.292 | 8728.475 | 12.367 | 304.224 | 87.0 |
| 가산 | FATO 1 | 37.48807877 | 126.87869740 | 32.446 | -8820.566 | 8730.372 | 12.367 | 304.187 | 87.0 |
| 마곡 | FATO 2 | 37.56297897 | 126.79297810 | 34.470 | -16390.214 | 408.773 | 0.437 | 314.093 | 45.0 |
| 마곡 | FATO 1 | 37.56271680 | 126.79264590 | 34.524 | -16419.618 | 437.800 | 0.437 | 314.039 | 45.0 |
| 망우 | FATO 2 | 37.59746657 | 127.08614690 | 38.683 | 9510.289 | -3406.505 | 6.732 | 303.584 | 344.0 |
| 망우 | FATO 1 | 37.59710779 | 127.08627210 | 38.672 | 9521.421 | -3366.716 | 6.732 | 303.595 | 344.0 |
| 수서 | FATO 2 | 37.48811511 | 127.09952670 | 45.991 | 10713.520 | 8723.773 | 13.922 | 289.088 | 222.0 |
| 수서 | FATO 1 | 37.48838995 | 127.09984210 | 46.019 | 10741.363 | 8693.247 | 13.922 | 289.060 | 222.0 |

## ??/?? ??? ? ? ?? ??

1. **??? ???? ?? ??**: `vertiport_UE.csv`? `Latitude/Longitude/AngleDegrees`? Cesium line trace ??.
2. **?? FATO/GATE/TAXI ??**: `resources_vp.csv`? `pt_lat_deg/pt_lon_deg/pt_h_m`, `X_m/Y_m/Z_m`.
3. **AirSim ?? ??**: FATO 2 ?? `X_m/Y_m` + ? `AirSimSpawnDown_m` ???.
4. **?? ?? LLA**: MissionModule routeData? `departureTakeoff`, `arrivalTouchdown`, `points`, `missionWaypoints`.
5. **??? ??**: `MissionModule/app/domain/coord_transform.py`? affine GCP ?? `wgs84_to_airsim_ned()`? resource CSV ?? X/Y ?? ??? ???? ??.

## ??? ???

- ???? ?? LLA? FATO LLA? ???. ?? ??? ?? ??? ??? `FATO 2`? ?? ??.
- `Z_m`? ?? ???? ???? ? ??. ?? runtime spawn Z? `pt_h_m + Z_m`? Cesium origin height?? ?? ??? ???.
- `vertiportMap_KU.csv`? ?? ???? ?? ????. ?? ????? ??/?? ???? ??? ??? Gate/FATO/Taxi? `resources_vp.csv`? ?? ??.
- Editor?? label? ??? `U X/Y/Z`? ?? Actor WorldLocation??. ?? Actor? ?? ? Cesium terrain line trace? ?? ????. CSV? ? preview? ??? ?? ????, ?? ?? ?? ?? world Z? Cesium terrain ??? ?? ??? ? ??.
