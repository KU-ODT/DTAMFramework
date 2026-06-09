# DTAM SDK

Version: `0.0.1`

DTAM SDK is a small Python package for module-to-module DTAM data exchange.
It can run without the GUI. Configure your own receive endpoint and the peer
endpoint, then send validated DTAM messages through `DtamClient`.

- Korean guide: [README_KOR.md](README_KOR.md)
- English guide: [README_ENG.md](README_ENG.md)
- ICD documents: [dtam_client/icd](dtam_client/icd)
- Basic config: [dtam_config.example.json](dtam_config.example.json)

Quick start:

```python
from dtam_client import DtamClient

dtam = DtamClient.module(
    my_ip="0.0.0.0",
    my_port=17000,
    peer_ip="192.168.0.43",
    peer_port=17000,
    auto_listen=True,
)

dtam.push_vehicle_status_async(dtam.sample("4001"))
```

Port rule:

- UDP uses `port`.
- TCP uses `port + 1`.
- Use a different `my_port` for each module running on the same computer.
