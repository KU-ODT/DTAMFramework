# dtam_client

`dtam_client` is the SDK package. It is independent from any GUI.

Recommended API:

```python
from dtam_client import DtamClient

dtam = DtamClient.module(
    my_ip="0.0.0.0",
    my_port=17000,
    peer_ip="192.168.0.43",
    peer_port=17000,
    auto_listen=True,
)
```

Config-file API:

```python
dtam = DtamClient.from_config("dtam_config.json", auto_listen=True)
```

Port convention:

- UDP uses `port`.
- TCP uses `port + 1`.
- `my_*` is this module's receive endpoint.
- `peer_*` is the endpoint this module sends to.

Main operations:

```python
dtam.on("4001", lambda result: print(result.to_dict()))
dtam.push_vehicle_status(data)
dtam.push_vehicle_status_async(data)
dtam.push_sample("4001")
```

ICD documents are included under `dtam_client/icd/KOR` and
`dtam_client/icd/ENG`.
