/** Accent-insensitive lowercase trim for comune/via search. */
export function normalizeSearch(s) {
  return String(s || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

/** 0 exact, 1 prefix, 2 substring. */
export function searchRank(normalizedName, q) {
  if (normalizedName === q) return 0;
  if (normalizedName.startsWith(q)) return 1;
  return 2;
}

/** Prefer the place name so labels like "Torino (Torino)" do not match on provincia. */
export function itemSearchText(it) {
  return it.name || it.label;
}

export const SEARCH_LIMIT = 80;

/**
 * Filter items whose search text includes q; rank exact > prefix > substring.
 * Empty query: first `limit` items (picker empty-open behavior).
 * @template T
 * @param {T[]} items
 * @param {string} filter
 * @param {(it: T) => string} [getText]
 * @param {number} [limit]
 * @returns {T[]}
 */
export function matchAndRankItems(
  items,
  filter,
  getText = itemSearchText,
  limit = SEARCH_LIMIT
) {
  const q = normalizeSearch(filter);
  if (!q) return items.slice(0, limit);
  const matched = items.filter((it) =>
    normalizeSearch(getText(it)).includes(q)
  );
  matched.sort((a, b) => {
    const ta = getText(a);
    const tb = getText(b);
    const rank =
      searchRank(normalizeSearch(ta), q) - searchRank(normalizeSearch(tb), q);
    if (rank) return rank;
    return String(ta).localeCompare(String(tb), "it");
  });
  return matched.slice(0, limit);
}
