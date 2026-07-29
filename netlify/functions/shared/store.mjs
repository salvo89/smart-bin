import { createHash } from "node:crypto";
import { connectLambda, getStore } from "@netlify/blobs";

const STORE_NAME = "push-subscriptions";

export function subscriptionKey(endpoint) {
  return createHash("sha256").update(String(endpoint)).digest("hex");
}

/** Netlify Functions v1 need connectLambda(event) before getStore. */
export function getPushStore(event) {
  if (event) connectLambda(event);

  const siteID = process.env.NETLIFY_SITE_ID || process.env.SITE_ID;
  const token =
    process.env.NETLIFY_BLOBS_TOKEN ||
    process.env.NETLIFY_AUTH_TOKEN ||
    process.env.NETLIFY_PERSONAL_ACCESS_TOKEN;

  if (siteID && token) {
    return getStore({ name: STORE_NAME, siteID, token });
  }

  return getStore(STORE_NAME);
}

/**
 * @param {import('@netlify/blobs').Store} store
 * @returns {Promise<Array<{ key: string, record: object }>>}
 */
export async function listAllSubscriptions(store) {
  const out = [];
  let cursor;
  do {
    const page = await store.list({ cursor });
    for (const blob of page.blobs || []) {
      const record = await store.get(blob.key, { type: "json" });
      if (record && record.subscription && record.subscription.endpoint) {
        out.push({ key: blob.key, record });
      }
    }
    cursor = page.cursor;
  } while (cursor);
  return out;
}
