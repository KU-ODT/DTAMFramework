# 새 DTAM 메시지 추가 가이드

DTAM 통신은 WebSocket(`/ws/dtam`) 단일 채널이고, 메시지 메타는 단일 카탈로그
(`dtam_client.catalog.CATALOG`)가 권위입니다. ICD payload 형태는 `dtam_client.schema`
의 dataclass 가 단일 권위입니다. 새 메시지 `XXXX` 를 추가하려면 다음 4 단계.

## 1. ICD dataclass 정의

`dtam_client/schema/msg_phaseN.py` (해당 phase 파일)에 dataclass 추가:

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class MsgXXXX_MyNewMessage:
    timestamp: str = ""
    aircraftId: str = ""
    # ...추가 필드 (모두 type annotation 필수)...
```

복합 sub-dataclass 가 필요하면 같은 파일 안에 정의 (또는 `icd_common.py` 에).
`__post_init__` 으로 range 검증 등 가능.

## 2. icd_registry 에 등록

`dtam_client/schema/icd_registry.py` 의 `ICD_REGISTRY` dict 에 한 줄 추가:

```python
ICD_REGISTRY: Dict[str, Type] = {
    ...,
    "XXXX": MsgXXXX_MyNewMessage,
}
```

`__init__.py` 의 export 목록에도 dataclass 이름 추가:

```python
from .msg_phaseN import MsgXXXX_MyNewMessage
__all__ = [..., "MsgXXXX_MyNewMessage"]
```

## 3. 카탈로그에 메타 등록

`dtam_client/catalog.py` 의 `CATALOG` 에 `MessageSpec` 한 줄 추가:

```python
"XXXX": MessageSpec(
    mid="XXXX", alias="my_new_message",
    name_en="My New Message", name_ko="내 새 메시지",
    direction="vehicle->server",     # 또는 mission->server, user->server 등
    rate_hz=0.0,
    phase=5,
    icd_proto="ws",
    db_folder="MyNewMessage",
    has_image_payload=False,          # 4101 처럼 binary tail 이면 True
),
```

## 4. (필요시) Forwarding 정책 + ICD 마크다운

서버가 이 메시지를 다른 모듈에게 자동 전달해야 한다면
`dtam_client/policy.py` 의 `FORWARD_RULES` 갱신:

```python
"XXXX": [Role.VEHICLE, Role.VISUAL],
```

사람용 명세 문서:
- `dtam_client/icd/KOR/XXXX_my_new_message.md`
- `dtam_client/icd/ENG/XXXX_my_new_message.md`

## 끝.

이걸로:
- 클라이언트 송신: `mod.send(MsgXXXX_MyNewMessage(...))` 즉시 사용 가능.
- 클라이언트 수신: 서브클래스에 `@on_receive("XXXX") def my_handler(self, msg: MsgXXXX_MyNewMessage)` 만 작성하면 자동 등록.
- 서버: `/ws/dtam` 수신 시 ICD 검증 → registry 갱신 → forwarding → DB 저장 자동.
- REST: `POST /api/msg/XXXX` 도 자동 등록 (서버가 카탈로그 순회로 동적 라우트 생성).
- Swagger UI: phase 별 태그 + ICD payload 예제 자동 노출.

## 권장 사항

- dataclass 필드는 모두 **type annotation 필수** + 기본값 권장 (`str = ""`, `float = 0.0`, `List[X] = field(default_factory=list)`).
- `alias` 는 영어 snake_case, `name_ko` / `name_en` 는 ICD 명세서의 공식 이름.
- 4101 처럼 binary payload 가 붙는 메시지는 `has_image_payload=True`.
- 송신 코드에서 dict 직접 만들지 말 것 — 항상 dataclass 인스턴스 생성 후 `mod.send(...)`.

## 무엇을 *하지 말아야* 하나

- ❌ Field 기반 검증 스키마 작성 금지 (구 `schema/msg_XXXX.py` 패턴은 폐기됨).
- ❌ "push 함수" 같은 별도 sender 작성 불필요. `DtamModule.send` 가 dataclass 로 통일.
- ❌ 카탈로그/dataclass 사본을 모듈에 따로 박지 말 것 — `from dtam_client.schema import ...` 그대로 import.
- ❌ dict 송신: `mod.send({"timestamp": ...})` 는 strict 모드에서 거부됨.
