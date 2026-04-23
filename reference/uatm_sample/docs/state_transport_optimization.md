# State Transport Optimization

Updated: 2026-02-10

## What changed
- Added incremental state transport for `/api/state` using `positions_rev`.
- Added client-side adaptive polling intervals based on runtime state.

## API behavior
- Request:
  - `GET /api/state`
  - optional query: `positions_rev=<int>`
- Response fields:
  - `positions_rev`: latest server revision for traffic positions
  - `positions_mode`: one of `full`, `delta`, `none`
  - `positions` when mode is `full`
  - `positions_updates` and `positions_removed` when mode is `delta`

## Delta notes
- Position identity uses `name`.
- Server keeps a short in-memory revision history window.
- If client revision is too old (or unavailable), server falls back to `full`.
- When a selected aircraft exists, server forces `full` to keep prediction/hold overlays consistent.

## Frontend polling policy
- Active simulation: `300ms`
- Idle (not running): `900ms`
- Hidden tab: `1800ms`

The frontend now merges `delta` payloads into a local position cache and only applies map updates when data actually changes.

