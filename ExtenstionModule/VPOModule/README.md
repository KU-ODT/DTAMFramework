# VPOModule — Vertiport Monitoring

`VPOModule`은 버티포트 운영자가 CCTV, 2D 버티포트 레이아웃, 지상 이동 상황, 운영 지표를 한 화면에서 볼 수 있도록 만든 프리미엄 웹 대시보드입니다.

## 주요 기능

- 버티포트 선택 콤보박스와 실시간 날짜/시간 표시
- 가로 스크롤형 CCTV 모니터링 레일
  - 클릭: 활성 CCTV 지정
  - 더블클릭: 별도 CCTV 집중 모니터링 창 열기
- 버티포트 2D 레이아웃과 이동체/패드 상태 실시간 시뮬레이션
- 날씨, 패드 가용률, 출도착 큐, 승객 처리량, 운영 타임라인, 알림 패널
- 외부 장비 연동 전에도 UI/UX 검토가 가능한 자체 Mock API 포함

## 실행

```powershell
python ExtenstionModule/VPOModule/VPO_main.py
```

브라우저를 자동으로 열지 않으려면:

```powershell
python ExtenstionModule/VPOModule/VPO_main.py --no-browser
```

기본 GUI 주소는 `http://127.0.0.1:8110`이며, 포트가 사용 중이면 자동으로 가능한 포트를 선택합니다.

## 구조

```text
ExtenstionModule/VPOModule/
  VPO_main.py
  app/
    server.py
    web/
      index.html
      cctv.html
      css/styles.css
      js/app.js
      js/cctv.js
  requirements.txt
  README.md
```
