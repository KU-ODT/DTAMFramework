// Feature loader for the system module overview.
import { getJSON } from "../../api/client.js";

export function loadSystem(endpoint) {
  return getJSON(endpoint);
}
