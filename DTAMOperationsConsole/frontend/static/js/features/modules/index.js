// Registry that maps each dashboard module slug to its frontend loader.
import { loadEnvironment } from "./environment.js";
import { loadMission } from "./mission.js";
import { loadOperations } from "./operations.js";
import { loadSimulation } from "./simulation.js";
import { loadSystem } from "./system.js";

export const moduleLoaders = {
  simulation: loadSimulation,
  mission: loadMission,
  environment: loadEnvironment,
  operations: loadOperations,
  system: loadSystem,
};
