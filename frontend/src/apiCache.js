const API_CACHE_TTL_MS = 5 * 60_000;
const MAX_MEMORY_ENTRIES = 50;
const MAX_SESSION_ENTRY_CHARS = 100_000;
const STORAGE_PREFIX = 'cofc_api_cache:v2:';
const responseCache = new Map();
const requestsInFlight = new Map();

export async function cachedApiFetch(apiBase, path) {
  const cacheKey = `${apiBase}${path}`;
  const now = Date.now();
  const memoryEntry = responseCache.get(cacheKey);
  if (memoryEntry && now - memoryEntry.cachedAt < API_CACHE_TTL_MS) {
    responseCache.delete(cacheKey);
    responseCache.set(cacheKey, memoryEntry);
    return memoryEntry.data;
  }

  const storageKey = `${STORAGE_PREFIX}${cacheKey}`;
  try {
    const stored = JSON.parse(window.sessionStorage.getItem(storageKey));
    if (stored && now - stored.cachedAt < API_CACHE_TTL_MS) {
      responseCache.set(cacheKey, stored);
      trimMemoryCache();
      return stored.data;
    }
  } catch {
    // Storage may be unavailable or contain an entry from an older schema.
  }

  if (requestsInFlight.has(cacheKey)) return requestsInFlight.get(cacheKey);

  const request = fetch(cacheKey)
    .then(res => {
      if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
      return res.json();
    })
    .then(data => {
      const entry = { cachedAt: Date.now(), data };
      responseCache.set(cacheKey, entry);
      trimMemoryCache();
      try {
        const serialized = JSON.stringify(entry);
        if (serialized.length <= MAX_SESSION_ENTRY_CHARS) {
          window.sessionStorage.setItem(storageKey, serialized);
        }
      } catch {
        // The in-memory cache still provides request deduplication.
      }
      return data;
    })
    .finally(() => requestsInFlight.delete(cacheKey));

  requestsInFlight.set(cacheKey, request);
  return request;
}

function trimMemoryCache() {
  while (responseCache.size > MAX_MEMORY_ENTRIES) {
    responseCache.delete(responseCache.keys().next().value);
  }
}
