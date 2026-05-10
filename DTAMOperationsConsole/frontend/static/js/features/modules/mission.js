// Feature loader for the mission module overview.
import { getJSON } from "../../api/client.js";

export function loadMission(endpoint) {
  return getJSON(endpoint);
}
