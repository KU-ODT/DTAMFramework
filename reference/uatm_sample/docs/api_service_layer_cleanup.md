# API Service-Layer Cleanup

Updated: 2026-02-10

## Goal
- Remove FastAPI's inheritance dependency on legacy `WebRequestHandler`.
- Consolidate CSV datafile mutations into a dedicated service module shared by HTTP/ASGI servers.

## Changes
- Added `app/datafile_service.py` with `DatafileService`.
  - Handles: clone/append/update/delete/apply/resolve for vertiport/corridor/basestation CSV files.
- `app/fastapi_server.py`
  - Removed `DatafileService(WebRequestHandler)` inheritance adapter.
  - `ServerContext` now owns a shared `DatafileService` instance.
  - `/api/logs.zip` and `/api/datafiles/*` now call `ctx.datafiles.*` directly.
- `app/web_server.py`
  - `WebHTTPServer` now owns `self.datafile_service`.
  - `WebRequestHandler` datafile endpoints delegate to that service.
  - Legacy in-handler CSV mutation implementation block removed from active path.

## Expected Effect
- API layer is clearer: request handlers orchestrate, service module owns file business logic.
- FastAPI no longer couples to legacy HTTP handler inheritance.
- Datafile behavior is consistent across both servers because they share one implementation.
