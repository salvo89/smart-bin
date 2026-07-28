import { createHash } from "node:crypto";
import { getStore } from "@netlify/blobs";

const STORE_NAME = "push-subscriptions";

export function subscriptionKey(endpoint) {
  return createHash("sha256").update(String(endpoint)).digest("hex");
}

export function getPushStore() {
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
