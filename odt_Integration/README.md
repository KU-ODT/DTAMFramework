# odt_Integration

`odt_Integration` is the GUI operation/test program for the sibling
`DTAM_SDK` project.

The GUI does not carry its own SDK copy anymore. DTAM message send/receive,
schema validation, receiver parsing, ICD-backed message helpers, and sample
payload generators are loaded from:

```text
../DTAM_SDK/
```

## Folder Role

```text
odt_Integration/
  main.py              GUI launcher
  app/                 FastAPI routes and GUI communication bridge
  static/              CSS, JS, operation/data-flow assets
  templates/           HTML
  config.json          GUI state: self receiver, targets, message options

../DTAM_SDK/
  dtam_client/         real SDK package
  message/             SDK payload generator examples
  dtam_config.json     SDK-only config example
```

## Run

```bash
pip install -r requirements.txt
python main.py
```

Default URL:

```text
http://127.0.0.1:8001
```

Use another web port:

```bash
python main.py --port 8002
```

Use a different GUI state file:

```bash
python main.py --config config_192.json
```

## Network Rule

The GUI follows the SDK convention:

- UDP uses `port`.
- TCP uses `port + 1`.
- Self Receiver is this GUI/module receive endpoint.
- Target is the peer module receive endpoint.

For two modules on one computer, give each module a different Self Receiver
port, for example `17000` and `17100`.
