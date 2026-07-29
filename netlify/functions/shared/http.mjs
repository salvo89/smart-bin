/** @param {Record<string, string>} [extra] */
export function json(statusCode, body, extra = {}) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Content-Type, X-Dispatch-Secret, Authorization",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      ...extra,
    },
    body: JSON.stringify(body),
  };
}

export function methodNotAllowed(allow) {
  return json(405, { error: "method_not_allowed" }, { Allow: allow });
}

/** @param {import('@netlify/functions').HandlerEvent} event */
export function parseJsonBody(event) {
  if (!event.body) return null;
  const raw = event.isBase64Encoded
    ? Buffer.from(event.body, "base64").toString("utf8")
    : event.body;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}
