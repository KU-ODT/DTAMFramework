"""odt_Integration에서 사용하는 기본 메시지 목록.

payload 값은 각 메시지 generator에 넘기는 keyword argument로 사용한다.
"""

DEFAULT_MESSAGES = [
    {
        "id": "0001",
        "name": "모듈 세팅 정보",
        "name_en": "Module Setting Info",
        "protocol": "udp",
        "payload": {},
    },
    {
        "id": "0002",
        "name": "모듈 상태 보고",
        "name_en": "Module Status",
        "protocol": "udp",
        "payload": {},
    },
    {
        "id": "0003",
        "name": "공통 시간 정보",
        "name_en": "Common Time Info",
        "protocol": "udp",
        "payload": {},
    },
    {
        "id": "1001",
        "name": "시뮬레이션 모드 설정",
        "name_en": "Sim Mode Setup",
        "protocol": "udp",
        "payload": {},
    },
    {
        "id": "1002",
        "name": "시뮬레이션 통제",
        "name_en": "Simulation Control",
        "protocol": "udp",
        "payload": {},
    },
    {
        "id": "1003",
        "name": "시나리오 설정",
        "name_en": "Scenario Setup",
        "protocol": "udp",
        "payload": {},
    },
    {
        "id": "2001",
        "name": "비행계획 생성 요청",
        "name_en": "Flight Plan Request",
        "protocol": "tcp",
        "payload": {},
    },
    {
        "id": "2002",
        "name": "DTAM 실행",
        "name_en": "DTAM Execute",
        "protocol": "tcp",
        "payload": {},
    },
    {
        "id": "3001",
        "name": "정기편 정보",
        "name_en": "Scheduled Flight",
        "protocol": "tcp",
        "payload": {
            "num_segments": 11,
        },
    },
    {
        "id": "3002",
        "name": "전략 분리 명령",
        "name_en": "Strategic Separation Command",
        "protocol": "tcp",
        "payload": {},
    },
    {
        "id": "3003",
        "name": "전술 분리 명령",
        "name_en": "Tactical Separation Command",
        "protocol": "tcp",
        "payload": {},
    },
    {
        "id": "4001",
        "name": "비행체 상태 정보",
        "name_en": "Vehicle Status",
        "protocol": "udp",
        "payload": {
            "num_vehicles": 1,
            "vehicle_id_prefix": "UAM",
        },
    },
    {
        "id": "4101",
        "name": "카메라 이미지 데이터",
        "name_en": "Camera Image Data",
        "protocol": "tcp",
        "payload": {},
    },
]
