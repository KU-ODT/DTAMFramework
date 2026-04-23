// Feature loader for the operations module overview.
import { getJSON } from "../../api/client.js";

export function loadOperations(endpoint) {
  return getJSON(endpoint);
}
