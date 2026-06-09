# IntegrationHub

IntegrationHub contains the DTAM server-side modules.

```text
IntegrationHub/
  CoreServerModule/
    DSE_main.py
    app/
    data/
  StateServerModule/
    SS_main.py
    app/
    data/
```

## CoreServerModule

Control plane server. It provides ICD document APIs, module process lifecycle controls, and launches StateServerModule as the data plane.

Default port: `8095`.

## StateServerModule

Data plane server. It owns `/ws/dtam`, message forwarding, file DB logging, simulation time, and the live monitor UI.

Default port: `8096`.

## Run

```powershell
python IntegrationHub/CoreServerModule/DSE_main.py
```

Normally this is started through:

```powershell
python Start_DTAM.py
```
