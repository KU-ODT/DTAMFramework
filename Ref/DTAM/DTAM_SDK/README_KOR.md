# DTAM SDK 사용법

버전: `0.0.1`

이 프로젝트는 GUI 없이도 쓸 수 있는 DTAM 모듈 통신 SDK입니다.
모듈 개발자는 데이터를 dict로 만들고 `DtamClient`에 넘기면 됩니다.

## 1. 가장 쉬운 사용법

```python
from dtam_client import DtamClient

dtam = DtamClient.module(
    my_ip="0.0.0.0",        # 내 모듈이 받을 IP. 보통 0.0.0.0
    my_port=17000,          # 내 UDP 수신 포트. TCP는 17001 자동 사용
    peer_ip="203.252.161.43",
    peer_port=17000,        # 상대 UDP 수신 포트. TCP는 17001 자동 사용
    auto_listen=True,
)

payload = dtam.sample("4001")
dtam.push_vehicle_status_async(payload)
```

기억할 것은 하나입니다.

- `my_*`: 상대가 나에게 보낼 때 쓰는 내 수신 설정
- `peer_*`: 내가 상대에게 보낼 때 쓰는 상대 수신 설정
- UDP는 입력한 `port`, TCP는 `port + 1`

## 2. config 파일로 쓰기

`dtam_config.json`:

```json
{
  "my": {
    "name": "my_module",
    "ip": "0.0.0.0",
    "port": 17000
  },
  "peer": {
    "name": "peer_module",
    "ip": "203.252.161.43",
    "port": 17000
  }
}
```

Python:

```python
from dtam_client import DtamClient

dtam = DtamClient.from_config("dtam_config.json", auto_listen=True)
dtam.push_sample_async("4001")
```

## 3. 수신 callback

```python
from dtam_client import DtamClient

dtam = DtamClient.from_config("dtam_config.json", auto_listen=False)

@dtam.on("4001")
def on_vehicle_status(result):
    print(result.to_dict())

dtam.listen(block=True)
```

## 4. 같은 컴퓨터에서 여러 모듈 실행

같은 컴퓨터에서는 같은 포트를 두 모듈이 동시에 받을 수 없습니다.
모듈마다 `my.port`를 다르게 주세요.

예시:

- Module A: `my.port = 17000`, TCP는 자동 `17001`
- Module B: `my.port = 17100`, TCP는 자동 `17101`

서로 보내려면 상대의 `my.port`를 내 `peer.port`에 적습니다.

Module A config:

```json
{
  "my": {"ip": "0.0.0.0", "port": 17000},
  "peer": {"ip": "127.0.0.1", "port": 17100}
}
```

Module B config:

```json
{
  "my": {"ip": "0.0.0.0", "port": 17100},
  "peer": {"ip": "127.0.0.1", "port": 17000}
}
```

## 5. TCP 실패 때문에 멈추지 않게 하기

시뮬레이션 루프에서는 `_async` 함수를 권장합니다. 상대 수신부가 아직
준비되지 않아도 내 루프가 오래 멈추지 않습니다.

```python
def on_send_error(result):
    print(result)

dtam.on_send_error = on_send_error
dtam.push_dtam_execute_async(dtam.sample("2002"))
```

## 6. 메시지 규격

ICD 문서는 SDK 안에 같이 들어 있습니다.

- 한국어: `dtam_client/icd/KOR`
- 영어: `dtam_client/icd/ENG`

`message/` 폴더는 사용자 payload 생성 예제입니다. 소켓 코드, schema,
receiver, ICD 문서는 `dtam_client/`에만 둡니다.
