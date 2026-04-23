# Server Host Strategy

Updated: 2026-02-10

## Purpose
- Replace fixed public-IP defaults with safer environment-based defaults.
- Keep local development private by default, while allowing explicit production exposure.

## Default Resolution
Host values are resolved in this order:
1. Explicit env var (`UATM_SERVER_HOST`, `UATM_TILE_HOST`, `UATM_FRONTEND_HOST`)
2. Environment default from `UATM_ENV`

`UATM_ENV` defaults:
- `local` (default): bind to `127.0.0.1`
- `dev` / `development` / `staging`: bind to `127.0.0.1`
- `prod` / `production`: bind to `0.0.0.0`
- unknown values: treated as `local`

## Recommended Values
- Local desktop use: `UATM_ENV=local` (or unset), keep `127.0.0.1`.
- Shared dev server: set explicit private host IP (for example `10.x.x.x`) with firewall allowlist.
- Production: use `UATM_ENV=prod` and apply network controls (security groups/firewall/reverse proxy).

## Examples
Windows PowerShell:
```powershell
$env:UATM_ENV = "local"
python app.py all
```

Linux/macOS:
```bash
export UATM_ENV=prod
python app.py all
```

