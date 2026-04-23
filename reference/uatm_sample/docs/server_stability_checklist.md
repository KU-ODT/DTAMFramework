# Server Stability Checklist

Created: 2026-02-10

## Scope
- Improve server/runtime stability in the current 3-service architecture (`api`, `tiles`, `frontend`).
- Execute in order, starting from item 1.

## Checklist
- [x] 1) Frontend proxy async conversion
  - Replace blocking `urllib` proxy calls with async HTTP client (`httpx.AsyncClient`).
  - Reuse connection pool via app lifespan.
  - Keep proxy behavior equivalent (status/body/headers pass-through).

- [x] 2) `run_all.py` failure propagation and supervision policy
  - Return non-zero exit code when any child service exits unexpectedly.
  - Define restart/no-restart policy and logs.

- [x] 3) Safer host default strategy
  - Revisit default host binding from fixed public IP to safer defaults by environment.
  - Document recommended local/dev/prod host values.

- [x] 4) State transport optimization
  - Review 300ms polling load under high traffic.
  - Consider incremental state or websocket path.

- [x] 5) Logging I/O decoupling
  - Decouple sync file writes from simulation loop with queue/writer worker.
  - Protect sim tick from disk latency spikes.

- [x] 6) API service-layer cleanup
  - Remove inheritance coupling to legacy handler utilities where possible.
  - Isolate datafile logic into explicit service module(s).

## Progress Log
- 2026-02-10: Checklist created. Starting item 1.
- 2026-02-10: Item 1 completed.
  - `app/frontend_server.py`: `urllib` removed, async proxy switched to `httpx.AsyncClient`.
  - `app/frontend_server.py`: shared client managed by FastAPI lifespan.
  - `app/frontend_server.py`: if `httpx` is unavailable, fallback path keeps proxy working via urllib/thread.
  - `app/frontend_server.py`: fixed `httpx` auto-decode vs `Content-Encoding` mismatch by dropping stale encoding header.
  - `requirements.txt`: `httpx==0.28.1` added.
- 2026-02-10: Item 2 completed.
  - `scripts/run_all.py`: supervision policy fixed to "no auto-restart; if one exits, stop all".
  - `scripts/run_all.py`: child exit detection now returns non-zero (`first non-zero child code`, else `1`).
  - `scripts/run_all.py`: graceful shutdown helper added (`terminate -> wait -> kill`) to avoid orphan processes.
  - Verification: forced API port conflict (`--host 127.0.0.1 --api-port 18002`) and confirmed `RUN_ALL_EXIT_CODE=1`.
- 2026-02-10: Item 3 completed.
  - `app/config.py`: removed fixed public-IP default and introduced `UATM_ENV`-based bind host policy.
  - `app/config.py`: default host is `127.0.0.1` for local/dev, `0.0.0.0` for prod.
  - `scripts/run_all.py`: `--host` default now follows the same `UATM_ENV` host policy.
  - `docs/server_host_strategy.md`: documented resolution order and recommended host values for local/dev/prod.
- 2026-02-10: Item 4 completed.
  - `app/web_server.py`: `/api/state` now supports `positions_rev` and returns `positions_mode` (`full`/`delta`/`none`).
  - `app/web_server.py`: added bounded revision history and per-flight patch generation (`positions_updates`, `positions_removed`).
  - `app/fastapi_server.py`: wired `positions_rev` query param through to `SimulationApi.get_state()`.
  - `app/web/app.js`: switched to adaptive polling (active 300ms, idle 900ms, hidden 1800ms) and delta merge cache.
  - `docs/state_transport_optimization.md`: documented protocol and polling policy.
  - Verification: `SimulationApi.get_state(positions_rev=...)` scenario validated (`full -> delta -> none`, selection forces `full`).
- 2026-02-10: Item 5 completed.
  - `app/web_server.py`: `FlightLogger` changed from synchronous write path to queue + writer thread.
  - `app/web_server.py`: `append_positions`/`append_event` now enqueue, and `stop()` drains (`flush`) before close.
  - `app/web_server.py`: log readers (`read_history`, logs zip generation) now flush pending queue work before file read.
  - `app/web_server.py`: `_update_map` passes prebuilt snapshot to logger queue, removing direct disk I/O from tick path.
  - `docs/logging_io_decoupling.md`: documented queue behavior and expected impact.
  - Verification: temporary-session smoke test confirmed event/track files written after async enqueue + flush.
- 2026-02-10: Item 6 completed.
  - `app/datafile_service.py`: introduced dedicated `DatafileService` for datafile clone/append/update/delete/apply/resolve.
  - `app/fastapi_server.py`: removed `WebRequestHandler` inheritance coupling; datafile endpoints now use `ctx.datafiles`.
  - `app/web_server.py`: datafile endpoints now delegate to shared `DatafileService` instance on server context.
  - `docs/api_service_layer_cleanup.md`: documented service-layer extraction and expected impact.
  - Verification: `py_compile` passed and service smoke test validated clone/append/resolve/apply flow.
