import { json, methodNotAllowed } from "./shared/http.mjs";

export async function handler(event) {
  if (event.httpMethod !== "GET") {
    return methodNotAllowed("GET");
  }

  const publicKey = process.env.VAPID_PUBLIC_KEY;
  if (!publicKey) {
    return json(503, { error: "vapid_not_configured" });
  }

  return json(200, { publicKey }, { "Cache-Control": "public, max-age=3600" });
}
