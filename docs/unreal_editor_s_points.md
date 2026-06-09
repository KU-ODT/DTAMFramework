# Unreal Editor Preview S-Point 좌표 추출

- 생성시각: `2026-05-22T02:39:10+09:00`
- Unreal 프로젝트: `D:\DTAMFramework\VisualizationModule_Source\Unreal\Environments\DTAMVisualization`
- 맵: `/Game/FlyingCPP/Maps/FlyingExampleMap`
- 추출 row: `493` = 버티포트 `17`개 × S-point `29`개
- CesiumGeoreference origin LLH: lon `126.978000`, lat `37.566500`, h `350.000 m`, scale `100.0`

## 정정 사항

기존 `unreal_vertiport_resource_points.csv`는 Mission/coordinateDB 리소스 좌표를 섞어 만든 값이라, 에디터에서 보이는 `GroundNodeMarker_*`/`GroundNodeLabel_*` 좌표 그 자체가 아니었습니다. 이번 파일은 Unreal Python으로 실제 `ADTAMVisualizationVertiportPreviewActor`를 생성한 뒤, 에디터에 표시되는 점 컴포넌트의 `get_world_location()` 값을 읽어서 만들었습니다.

## 사용한 Unreal 코드 경로

- 버티포트 배치: `Source/DTAMVisualization/DTAMVisualizationFlightCorridorActor.cpp::SpawnVertiports`
  - `vertiport_UE.csv`의 `Latitude/Longitude/AngleDegrees`를 사용
  - `MoveToLongitudeLatitudeHeight(Longitude, Latitude, 60m)` 후 ESU yaw 회전 적용
- S-point 생성/라벨: `Source/DTAMVisualization/DTAMVisualizationVertiportPreviewActor.cpp::UpdateGroundMapPreview`
  - `vertiportMap_KU.csv`의 29개 `local_x/y/z_cm`로 `GroundNodeMarker_0~28` 생성
  - 라벨의 `U +x / +y / +z`는 `GroundNodeMarker.GetComponentLocation()` 값

## 산출물

- CSV: `D:\DTAMFramework\docs\unreal_editor_s_points.csv`
- 기존 경로 덮어쓴 CSV: `D:\DTAMFramework\docs\unreal_vertiport_resource_points.csv`
- 원본 JSON: `D:\DTAMFramework\output\unreal_editor_dump\unreal_editor_s_points.json`
- 메타: `D:\DTAMFramework\docs\unreal_editor_s_points_meta.json`

## 주의: 고도/trace 상태

이번 commandlet 추출에서는 `493`개 row가 `NO_HIT_COMMANDLET_FALLBACK_H60` 상태입니다. 즉, 현재 배치/회전/S-point 컴포넌트 좌표는 Unreal Editor에서 직접 생성해 읽었지만, Cesium 지형 surface line trace가 commandlet 환경에서 맞지 않아 actor 기준 고도는 C++ 기본 fallback `60 m` 상태로 남아 있습니다. 라이브 에디터에서 Cesium 지형이 로드된 상태로 같은 스크립트를 실행하면 trace 반영 Z까지 다시 떨어집니다.

## 잠실 S01~S29 추출값

| S | semantic | type | marker_x_cm | marker_y_cm | marker_z_cm | LLA lat | LLA lon | h_m | label | trace |
|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| S01 | G8 | gate | 807639.451 | 581835.669 | -29616.966 | 37.514041740 | 127.069351907 | 61.600 | `1 G8 | U +807639 / +581836 / -29617` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S02 | G7 | gate | 807848.262 | 583522.795 | -29618.764 | 37.513889713 | 127.069375340 | 61.600 | `2 G7 | U +807848 / +583523 / -29619` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S03 | G6 | gate | 808055.230 | 585195.035 | -29620.545 | 37.513739027 | 127.069398566 | 61.600 | `3 G6 | U +808055 / +585195 / -29621` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S04 | G5 | gate | 808262.198 | 586867.275 | -29622.327 | 37.513588341 | 127.069421792 | 61.601 | `4 G5 | U +808262 / +586867 / -29622` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S05 |  | taxi | 806403.879 | 581988.594 | -29615.547 | 37.514028070 | 127.069212135 | 61.600 | `5 | U +806404 / +581989 / -29616` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S06 |  | taxi | 806612.690 | 583675.720 | -29617.345 | 37.513876043 | 127.069235568 | 61.600 | `6 | U +806613 / +583676 / -29617` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S07 |  | taxi | 806819.658 | 585347.960 | -29619.127 | 37.513725357 | 127.069258795 | 61.600 | `7 | U +806820 / +585348 / -29619` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S08 |  | taxi | 807026.627 | 587020.200 | -29620.908 | 37.513574670 | 127.069282021 | 61.601 | `8 | U +807027 / +587020 / -29621` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S09 |  | taxi | 804835.845 | 582182.667 | -29613.747 | 37.514010721 | 127.069034753 | 61.600 | `9 | U +804836 / +582183 / -29614` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S10 |  | taxi | 805044.655 | 583869.793 | -29615.545 | 37.513858694 | 127.069058187 | 61.600 | `10 | U +805045 / +583870 / -29616` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S11 |  | taxi | 805251.624 | 585542.033 | -29617.326 | 37.513708008 | 127.069081414 | 61.600 | `11 | U +805252 / +585542 / -29617` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S12 |  | taxi | 805458.592 | 587214.273 | -29619.108 | 37.513557322 | 127.069104641 | 61.601 | `12 | U +805459 / +587214 / -29619` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S13 | G4 | gate | 803600.273 | 582335.592 | -29612.328 | 37.513997051 | 127.068894982 | 61.600 | `13 G4 | U +803600 / +582336 / -29612` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S14 | G3 | gate | 803809.084 | 584022.718 | -29614.126 | 37.513845023 | 127.068918416 | 61.600 | `14 G3 | U +803809 / +584023 / -29614` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S15 | G2 | gate | 804016.052 | 585694.958 | -29615.908 | 37.513694337 | 127.068941643 | 61.600 | `15 G2 | U +804016 / +585695 / -29616` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S16 | G1 | gate | 804223.021 | 587367.197 | -29617.689 | 37.513543651 | 127.068964870 | 61.601 | `16 G1 | U +804223 / +587367 / -29618` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S17 |  | connector | 805619.862 | 582085.630 | -29614.647 | 37.514019396 | 127.069123444 | 61.600 | `17 | U +805620 / +582086 / -29615` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S18 |  | connector | 805828.673 | 583772.757 | -29616.445 | 37.513867368 | 127.069146878 | 61.600 | `18 | U +805829 / +583773 / -29616` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S19 |  | connector | 806035.641 | 585444.996 | -29618.226 | 37.513716682 | 127.069170104 | 61.600 | `19 | U +806036 / +585445 / -29618` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S20 |  | connector | 806242.609 | 587117.236 | -29620.008 | 37.513565996 | 127.069193331 | 61.601 | `20 | U +806243 / +587117 / -29620` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S21 |  | connector | 805724.267 | 582929.194 | -29615.546 | 37.513943382 | 127.069135161 | 61.600 | `21 | U +805724 / +582929 / -29616` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S22 |  | connector | 805932.218 | 584609.373 | -29617.336 | 37.513791980 | 127.069158498 | 61.600 | `22 | U +805932 / +584609 / -29617` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S23 |  | connector | 806139.187 | 586281.613 | -29619.118 | 37.513641294 | 127.069181725 | 61.601 | `23 | U +806139 / +586282 / -29619` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S24 |  | connector | 806370.967 | 588154.323 | -29621.113 | 37.513472544 | 127.069207736 | 61.601 | `24 | U +806371 / +588154 / -29621` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S25 | F2 | pad | 808617.177 | 589735.390 | -29625.383 | 37.513329894 | 127.069461628 | 61.601 | `25 F2 | U +808617 / +589735 / -29625` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S26 | F1 | pad | 804577.999 | 590235.312 | -29620.745 | 37.513285204 | 127.069004708 | 61.601 | `26 F1 | U +804578 / +590235 / -29621` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S27 |  | branch | 806499.324 | 589191.409 | -29622.218 | 37.513379092 | 127.069222140 | 61.601 | `27 | U +806499 / +589191 / -29622` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S28 |  | branch | 807232.741 | 589906.739 | -29623.793 | 37.513314577 | 127.069305018 | 61.601 | `28 | U +807233 / +589907 / -29624` | NO_HIT_COMMANDLET_FALLBACK_H60 |
| S29 |  | branch | 805962.435 | 590063.963 | -29622.335 | 37.513300522 | 127.069161318 | 61.601 | `29 | U +805962 / +590064 / -29622` | NO_HIT_COMMANDLET_FALLBACK_H60 |

## 전체 버티포트 목록

가산, 강남, 광화문, 마곡, 망우, 목동, 미아, 봉천, 사당, 상암, 성수, 수서, 연신내, 영등포, 용산, 잠실, 천호
