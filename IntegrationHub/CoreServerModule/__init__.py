"""DTAM Core Server package.

Cloud-bound control plane: ICD docs, sequence diagram serving, and
module process lifecycle management. Spawns StateServerModule as
a child process for actual data-plane traffic handling.

Module roles handled by the framework:
  - mission     (MissionModule)
  - monitoring  (OperationModule)
  - vehicle     (VehicleModule)
  - visual      (VisualizationModule)
  - sim_state   (StateServerModule)

See ``CoreServerModule/app/web/data/sequence_diagram.json`` for the
reference message flow.
"""
