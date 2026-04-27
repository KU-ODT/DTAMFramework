"""DTAM Core Server package.

Cloud-bound control plane: ICD docs, sequence diagram serving, and
module process lifecycle management. Spawns DTAM_SimulationState as
a child process for actual data-plane traffic handling.

Module roles handled by the framework:
  - mission     (DTAM_MissionPlanner)
  - monitoring  (DTAMOperationsConsole)
  - vehicle     (DTAMAirMobility)
  - visual      (DTAMVisualization)
  - sim_state   (DTAM_SimulationState)

See ``DTAM_CoreServer/app/web/data/sequence_diagram.json`` for the
reference message flow.
"""
