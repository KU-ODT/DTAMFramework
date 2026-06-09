# Same Computer Example

Run two modules on one computer by giving each module a different receive
port.

Module A `dtam_config.json`:

```json
{
  "my": {"name": "module_a", "ip": "0.0.0.0", "port": 17000},
  "peer": {"name": "module_b", "ip": "127.0.0.1", "port": 17100}
}
```

Module B `dtam_config.json`:

```json
{
  "my": {"name": "module_b", "ip": "0.0.0.0", "port": 17100},
  "peer": {"name": "module_a", "ip": "127.0.0.1", "port": 17000}
}
```

UDP uses `port`. TCP uses `port + 1`.
