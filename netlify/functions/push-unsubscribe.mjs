import { json, methodNotAllowed, parseJsonBody } from "./shared/http.mjs";
import { getPushStore, subscriptionKey } from "./shared/store.mjs";

export async function handler(event) {
  if (event.httpMethod === "OPTIONS") {
    return json(204, {});
  }
  if (event.httpMethod !== "POST") {
    return methodNotAllowed("POST");
  }

  const body = parseJsonBody(event);
  const endpoint =
    (body && body.endpoint) ||
    (body && body.subscription && body.subscription.endpoint);
  if (!endpoint || typeof endpoint !== "string") {
    return json(400, { error: "missing_endpoint" });
  }

  const store = getPushStore();
  await store.delete(subscriptionKey(endpoint));
  return json(200, { ok: true });
}
