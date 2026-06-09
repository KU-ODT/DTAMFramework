# DTAM SDK Guide

Version: `0.0.1`

This SDK lets DTAM modules exchange data without the GUI. A module creates a
message payload as a Python dict, then sends it through `DtamClient`.

## 1. Simplest Usage

```python
from dtam_client import DtamClient

dtam = DtamClient.module(
    my_ip="0.0.0.0",        # where this module listens
    my_port=17000,          # UDP port; TCP is 17001 by default
    peer_ip="203.252.161.43",
    peer_port=17000,        # peer UDP port; peer TCP is 17001 by default
    auto_listen=True,
)

payload = dtam.sample("4001")
dtam.push_vehicle_status_async(payload)
```

Only remember this rule:

- `my_*` is where this module receives data.
- `peer_*` is where this module sends data.
- UDP uses `port`; TCP uses `port + 1`.

## 2. Config File Usage

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

## 3. Receive Callbacks

```python
from dtam_client import DtamClient

dtam = DtamClient.from_config("dtam_config.json", auto_listen=False)

@dtam.on("4001")
def on_vehicle_status(result):
    print(result.to_dict())

dtam.listen(block=True)
```

## 4. Multiple Modules On One Computer

Two modules on the same computer cannot listen on the same port. Give every
module a different `my.port`.

Example:

- Module A: `my.port = 17000`, TCP automatically uses `17001`
- Module B: `my.port = 17100`, TCP automatically uses `17101`

To send between them, put the other module's `my.port` into your `peer.port`.

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

## 5. Non-Blocking Sends

For simulation loops, prefer `_async` send methods. If the peer listener is
not ready, your module loop will not be blocked for long.

```python
def on_send_error(result):
    print(result)

dtam.on_send_error = on_send_error
dtam.push_dtam_execute_async(dtam.sample("2002"))
```

## 6. ICD Documents

ICD documents are distributed with the SDK:

- Korean: `dtam_client/icd/KOR`
- English: `dtam_client/icd/ENG`

The `message/` folder is a user-side payload builder example. Socket code,
schemas, receivers, and ICD documents belong in `dtam_client/`.
