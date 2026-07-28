import { json, methodNotAllowed, parseJsonBody } from "./shared/http.mjs";
import { normalizeCalendarBase } from "./shared/calendar.mjs";
import { getPushStore, subscriptionKey } from "./shared/store.mjs";

function isValidSubscription(sub) {
  return (
    sub &&
    typeof sub.endpoint === "string" &&
    sub.endpoint.startsWith("https://") &&
    sub.keys &&
    typeof sub.keys.p256dh === "string" &&
    typeof sub.keys.auth === "string"
  );
}

export async function handler(event) {
  if (event.httpMethod === "OPTIONS") {
    return json(204, {});
  }
  if (event.httpMethod !== "POST") {
    return methodNotAllowed("POST");
  }

  const body = parseJsonBody(event);
  if (!body || !isValidSubscription(body.subscription)) {
    return json(400, { error: "invalid_subscription" });
  }

  const calendarId = normalizeCalendarBase(body.calendarId);
  if (!calendarId || !String(calendarId).startsWith("calendars/")) {
    return json(400, { error: "invalid_calendar" });
  }

  let hour = Number(body.hour);
  if (!Number.isInteger(hour) || hour < 0 || hour > 23) hour = 20;

  const now = new Date().toISOString();
  const key = subscriptionKey(body.subscription.endpoint);
  const store = getPushStore();
  const existing = await store.get(key, { type: "json" });

  const record = {
    subscription: {
      endpoint: body.subscription.endpoint,
      keys: {
        p256dh: body.subscription.keys.p256dh,
        auth: body.subscription.keys.auth,
      },
    },
    calendarId,
    hour,
    tz: "Europe/Rome",
    createdAt: (existing && existing.createdAt) || now,
    updatedAt: now,
    lastSentDate: (existing && existing.lastSentDate) || null,
  };

  await store.setJSON(key, record);
  return json(200, { ok: true, key });
}
