# User Message Workspace

This package is intentionally small. It represents the user/module side of the
project: create payload data, then send it through `dtam_client`.

The SDK owns the protocol details:

- schema validation: `dtam_client/schema`
- send functions: `dtam_client/msg`
- receive parsing: `dtam_client/receiver`
- ICD documents: `dtam_client/icd`
- high-level API: `dtam_client.DtamClient`

## Generate And Send

```python
from dtam_client import DtamClient
from message.generator import module_status

dtam = DtamClient.module(
    my_ip="0.0.0.0",
    my_port=17000,
    peer_ip="REMOTE_MODULE_IP",
    peer_port=17000,
    auto_listen=True,
)

payload = module_status.generate(source="MyModule")
dtam.push_module_status_async(payload)
```

Because the generator filenames begin with message IDs, direct imports by file
name are awkward. In application code, either use the app registry or import a
specific file by path. For simple tests, use SDK samples instead:

```python
from dtam_client import DtamClient

dtam = DtamClient.module(peer_ip="REMOTE_MODULE_IP", auto_listen=True)
dtam.push_sample_async("4001")
```

## What Belongs Here

Keep user-authored payload builders here. Do not add socket code, ICD docs,
schema definitions, or receive parsers to `message`; those belong in
`dtam_client`.
