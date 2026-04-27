# 새 DTAM 메시지 추가 가이드

DTAM 통신은 WebSocket(`/ws/dtam`) 단일 채널이고, 메시지 메타는 단일 카탈로그
(`dtam_client.catalog.CATALOG`)가 권위입니다. 새 메시지 `XXXX_name` 을 추가
하려면 다음 4 단계만 거치면 됩니다.

## 1. 스키마 정의 (정적 검증용)

`dtam_client/schema/msg_XXXX.py` 추가. 기존 메시지 (예: `msg_4001.py`)를
템플릿으로 복사한 뒤 dataclass 필드 + `validate_message()` 작성.

```python
from dataclasses import dataclass, field

@dataclass
class MyNewMessage:
    timestamp: str = ""
    aircraftId: str = ""
    # ...추가 필드...

def validate_message(payload: dict) -> tuple[bool, list[str], list[str]]:
    errors, warnings = [], []
    # ICD 명세 기반 검증 로직
    return (not errors), errors, warnings
```

## 2. 카탈로그에 등록

`dtam_client/catalog.py` 의 `CATALOG` 딕셔너리에 `MessageSpec` 한 줄 추가:

```python
"XXXX": MessageSpec(
    mid="XXXX", alias="my_new_message",
    name_en="My New Message", name_ko="내 새 메시지",
    direction="vehicle->server",     # 또는 mission->server, user->server 등
    rate_hz=0.0,                      # 주기 메시지면 hz 명시
    phase=5,                          # 시퀀스 다이어그램의 phase
    icd_proto="ws",
    db_folder="MyNewMessage",
    has_image_payload=False,          # 4101 같은 binary tail 이면 True
),
```

## 3. (필요시) Forwarding 정책 추가

서버가 이 메시지를 다른 모듈에게 자동 전달해야 한다면
`dtam_client/policy.py` 의 `FORWARD_RULES` 갱신:

```python
"XXXX": [Role.VEHICLE, Role.VISUAL],     # 어느 역할들에게 전달할지
```

전달 안 하고 단순 저장만 한다면 생략. (서버의 `on_event` 가 모든 메시지를
DB 에 기록.)

## 4. ICD 마크다운

사람용 명세 문서:
- `dtam_client/icd/KOR/XXXX_name.md`
- `dtam_client/icd/ENG/XXXX_name.md`

## 끝.

이걸로:
- 클라이언트: `mod.send("my_new_message", payload)` / `mod.on("my_new_message", cb)` 즉시 사용 가능 (alias 자동 변환).
- 서버: `/ws/dtam` 으로 들어오면 ICD 검증 → registry 갱신 → forwarding → DB 저장 자동.
- REST: `POST /api/msg/XXXX` 도 자동 등록 (서버가 카탈로그 순회로 동적 라우트 생성).
- Swagger UI: phase 별 태그 + ICD payload 예제 자동 노출.

## 권장 사항

- `alias` 는 영어 snake_case (예: `vehicle_status`).
- `name_ko` / `name_en` 는 ICD 명세서의 공식 이름.
- `direction` 은 시퀀스 다이어그램 표기를 그대로 (`vehicle->server`).
- 4101 처럼 binary payload (이미지 등) 가 붙는 메시지는 `has_image_payload=True`.
- 카탈로그에 spec 만 추가하면 `samples.py` 의 `sample_payload(mid)` 도 동작
  하도록 sample 함수 한 개를 함께 추가해 두는 것이 디버깅에 편함.

## 무엇을 *하지 말아야* 하나

- ❌ `_client.py`, `_listener.py`, `msg/`, `receiver/` 는 이제 없음 (Phase 5에서 제거).
- ❌ "push 함수" 같은 별도 sender 작성 불필요. `DtamModule.send` 가 alias 로 통일.
- ❌ "콜백 등록 attribute" (예: `on_my_new_message = ...`) 도 불필요. `mod.on(alias, cb)`.
- ❌ 카탈로그 사본을 모듈에 따로 박지 말 것 — `from dtam_client import CATALOG` 그대로 import.
