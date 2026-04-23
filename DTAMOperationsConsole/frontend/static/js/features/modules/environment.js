// Feature loader for the environment module overview.
import { getJSON } from "../../api/client.js";

export function loadEnvironment(endpoint) {
  return getJSON(endpoint);
}
