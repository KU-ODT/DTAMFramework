# DTAMSDK

DTAMSDK는 DTAMFramework의 모든 모듈이 공통으로 사용하는 Python SDK, ICD schema, ICD 문서, 모듈 작성 규칙을 담는다.

## 이 폴더에서 유지하는 문서

| 문서 | 역할 |
| --- | --- |
| `README.md` | SDK 개요와 빠른 사용법. 이 파일 하나를 메인 README로 사용한다. |
| `MODULE_AUTHORING.md` | DTAM 모듈 표준 폴더 구조와 책임 분리 규칙. |
| `CHANGELOG.md` | SDK/문서 변경 이력. |
| `dtam_client/NEW_MESSAGE_PROMPT.md` | 신규 ICD 메시지를 추가할 때 따라야 하는 체크리스트. |
| `dtam_client/icd/` | 메시지별 ICD 상세 문서. |

`README_KOR.md`, `README_ENG.md`, `dtam_client/README.md`는 중복 문서라 제거한다. 앞으로 README는 이 파일 하나만 유지한다.

## 핵심 원칙

- 각 모듈의 실행 코드는 해당 모듈의 `app/` 안에 둔다.
- 코드가 아닌 입력/출력/저장 데이터는 `data/` 안에 둔다.
- DTAM SDK/ICD 통신 코드는 각 모듈의 `app/dtam/`에 격리한다.
- 모듈 간 기능 데이터 교환은 StateServerModule의 `/ws/dtam`과 ICD 메시지를 기준으로 한다.
- `domain/`은 순수 로직 영역으로 두고 FastAPI, WebSocket, SDK를 직접 알지 않도록 한다.

자세한 모듈 폴더 규칙은 [MODULE_AUTHORING.md](MODULE_AUTHORING.md)를 기준으로 한다.

## SDK 빠른 사용 예시

```python
from dtam_client import DtamModule, Role, on_receive
from dtam_client.schema import Msg4001_VehicleStatus

class Vehicle(DtamModule):
    role = Role.VEHICLE

    @on_receive("3001")
    def on_plan(self, plan):
        ...

svc = Vehicle(server_url="ws://127.0.0.1:8096/ws/dtam", heartbeat=True)
svc.send(Msg4001_VehicleStatus(timestamp="...", vehicles={}))
```

## 주요 패키지 구성

```text
DTAMSDK/
  README.md
  MODULE_AUTHORING.md
  CHANGELOG.md
  VERSION
  pyproject.toml
  requirements.txt

  dtam_client/
    __init__.py
    module.py
    _ws_client.py
    rest.py
    catalog.py
    identity.py
    policy.py
    ports.py
    samples.py
    role_modules.py
    schema/
    icd/
    NEW_MESSAGE_PROMPT.md

  examples/
```

| 경로 | 역할 |
| --- | --- |
| `dtam_client/module.py` | `DtamModule`, `on_receive`, strict dataclass 송신 모드. |
| `dtam_client/_ws_client.py` | low-level WebSocket transport. |
| `dtam_client/rest.py` | `DtamRest` helper. |
| `dtam_client/catalog.py` | message catalog. `mid -> alias -> phase -> db_folder`. |
| `dtam_client/identity.py` | `Role`, `KNOWN_MODULES`, module identity. |
| `dtam_client/policy.py` | forwarding/subscription rule. |
| `dtam_client/schema/` | ICD dataclass 원본. |
| `dtam_client/icd/` | ICD markdown 문서. |
| `dtam_client/samples.py` | 테스트/예시용 sample payload. |

## 신규 ICD 메시지 추가

신규 ICD를 추가할 때는 [dtam_client/NEW_MESSAGE_PROMPT.md](dtam_client/NEW_MESSAGE_PROMPT.md)를 따른다.

요약:

1. `catalog.py`에 mid, alias, direction, phase, db_folder 추가
2. `schema/msg_phaseN.py`에 dataclass 추가 후 `schema/icd_registry.py` 등록
3. `policy.py`에 forwarding/subscription 필요 여부 반영
4. `icd/KOR`, `icd/ENG`에 문서 추가
5. `samples.py`에 sample payload 추가
6. StateServerModule sequence diagram/문서와 동기화

## 빌드/설치 참고

개발 중에는 각 모듈에서 framework root와 `DTAMSDK`를 `sys.path`에 추가해 import한다. 패키지 설치가 필요한 경우:

```powershell
pip install -e D:\DTAMFramework\DTAMSDK
```
