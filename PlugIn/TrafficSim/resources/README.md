# TrafficSim 리소스 (Git 제외)

이 폴더에는 **TrafficSim 플러그인이 사용하는 대용량 시뮬레이션 데이터** 가
들어간다. 약 **735 MB**.

## 들어가야 할 내용

```
resources/
├── traffic_scenarios/                      # 시나리오 정의 (JSON)
├── airspace_data/                          # 공역 메타데이터 (csv/parquet)
├── historic_traces/                        # 과거 트래픽 trace
└── ml_models/                              # 학습된 ML 모델 (pkl/onnx)
```

## 어떻게 얻나

팀 내부 데이터 저장소에서 받기. README 가 위치한 폴더 (`PlugIn/TrafficSim/
resources/`) 에 압축 해제하면 됨.

> `.gitignore` 가 `PlugIn/TrafficSim/resources/**` 와 `PlugIn/TrafficSim/log/**`
> 를 무시.
