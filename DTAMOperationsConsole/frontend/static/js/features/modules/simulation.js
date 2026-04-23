// Feature loader for the simulation module overview.
import { getJSON } from "../../api/client.js";

export function loadSimulation(endpoint) {
  return getJSON(endpoint);
}
