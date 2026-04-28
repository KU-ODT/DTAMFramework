# Changelog

## Unreleased — WebSocket-only refactor

- Removed every UDP/TCP module-to-module path. All modules now connect as
  WebSocket clients to `DTAM_SimulationState` at `/ws/dtam` (port 8096).
- Replaced the old `DtamClient` (`my_*` / `peer_*`) API with `DtamModule`
  (subclass + `@on_receive("MID")` decorator) and a small `DtamRest`
  helper for one-shot REST calls.
- Single message catalog (`catalog.py`) is now authoritative; the server
  and all modules import from it instead of carrying their own copies.
- Single identity table (`identity.py`) for `Role` enum and module sources
  — replaces five duplicate hardcodes (server config, AirMobility,
  MissionPlanner, OperationsConsole, etc.).
- Dataclass-first send/receive. `module.send(Msg4001_VehicleStatus(...))`
  applies `to_wire()` for messages whose ICD layout differs from the
  dataclass shape (4001 has flat per-vehicle keys at the top level).
  `module.send_legacy(mid, dict)` is deprecated — toggle
  `set_strict_dataclass(True)` to forbid it outright.
- ICD `0001 Module Setting Info` simplified to `Timestamp` / `ModuleName`
  / `Role` (legacy `IP` / `UDPPort` / `TCPPort` removed; the WebSocket
  handshake already carries endpoint info).
- CoreServer config: dropped `udp_port` / `tcp_port` from
  `ServerEndpoint` / `ModuleEndpoint`; modules are now registered by
  `role` + `expected_source` only.

## 0.0.1

Initial DTAM SDK baseline (UDP/TCP era — superseded).
