# VehicleModule 런타임 로그 (Git 제외)

이 폴더에는 **VehicleModule 실행 시 자동 생성되는 로그 파일** 이 쌓인다.
실측 파일 크기 예시: `vfds_dynamics_autostart.log` ~ 205 MB.

## 들어가는 파일 (자동 생성)

```
logs/
├── vfds_dynamics_autostart.log             # vfds_dynamics 백엔드 stdout/stderr
├── am_runtime_YYYY-MM-DD.log               # 시계열 로그 (rotation)
└── ...
```

## 정리 정책

런타임이 길어지면 GB 단위로 자라므로:
- 일 1회 / 100MB 단위 rotation (logging.handlers.RotatingFileHandler 권장)
- 1주 이상 된 파일은 자동 삭제

> `.gitignore` 가 `VehicleModule/logs/**` 를 무시 (이 README 만 보존).
