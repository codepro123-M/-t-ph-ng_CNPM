// Public, read-only API client. Never embeds credentials or admin tokens.
export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function normalizeBase(value = "/api") {
  const base = String(value).trim().replace(/\/+$/, "") || "/api";
  if (base.startsWith("/") && !base.startsWith("//") && !/[?#\\\s]/.test(base))
    return base;
  let url;
  try {
    url = new URL(base);
  } catch {
    throw new ApiError("Invalid API URL");
  }
  if (
    !["https:", "http:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  )
    throw new ApiError("Invalid API URL");
  return url.href.replace(/\/+$/, "");
}

export function mediaUrl(path, base = "/api") {
  if (typeof path !== "string" || !/^\/media\/[a-f0-9]{24}$/i.test(path))
    return null;
  return normalizeBase(base) + path;
}

export async function fetchJSON(
  url,
  {
    signal,
    headers = {},
    fetcher = fetch,
    timeout = 15000,
    method = "GET",
    body,
  } = {},
) {
  const controller = new AbortController();
  const abort = () => controller.abort(signal?.reason);
  if (signal?.aborted) abort();
  signal?.addEventListener("abort", abort, { once: true });
  const timer = setTimeout(
    () =>
      controller.abort(new DOMException("Request timed out", "TimeoutError")),
    timeout,
  );
  try {
    const response = await fetcher(url, {
      method,
      ...(body ? { body: JSON.stringify(body) } : {}),
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      credentials: "omit",
      cache: "no-store",
    });
    if (response.status === 304)
      return { status: 304, etag: response.headers.get("etag") };
    if (!response.ok) throw new ApiError("API request failed", response.status);
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError("API returned a web page instead of JSON", 502);
    return {
      status: response.status,
      data: await response.json(),
      etag: response.headers.get("etag"),
    };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}

function validPoi(row) {
  return (
    row &&
    typeof row.id === "string" &&
    /^[a-f0-9]{24}$/i.test(row.id) &&
    typeof row.name === "string" &&
    typeof row.address === "string" &&
    Array.isArray(row.images) &&
    Array.isArray(row.menu_items)
  );
}

export function createClient(base = "/api", fetcher = fetch) {
  base = normalizeBase(base);
  const cache = new Map();
  const request = (path, options) =>
    fetchJSON(base + path, { fetcher, ...options });
  const query = (path, values) =>
    path +
    "?" +
    new URLSearchParams(
      Object.entries(values).filter(([, value]) => value != null),
    );
  async function loadAll(language = "vi", { signal, fresh = false } = {}) {
    const old = fresh ? null : cache.get(language);
    const rows = new Map(old?.rows || []);
    let cursor = old?.checkpoint || null;
    const startingCursor = cursor;
    let firstEtag = null;
    try {
      for (let page = 0; page < 200; page++) {
        const headers =
          page === 0 && old?.requestCursor === cursor && old?.requestEtag
            ? { "If-None-Match": old.requestEtag }
            : {};
        const response = await request(
          query("/poi/load-all", { language, limit: 100, cursor }),
          { signal, headers },
        );
        if (response.status === 304) {
          if (!old || page > 0)
            throw new ApiError("Unexpected empty API response", 502);
          return {
            items: [...old.rows.values()],
            asOf: old.asOf,
            unchanged: true,
          };
        }
        const data = response.data;
        if (
          !Array.isArray(data.items) ||
          !data.items.every(validPoi) ||
          !Array.isArray(data.removed_poi_ids) ||
          typeof data.sync_cursor !== "string" ||
          typeof data.has_more !== "boolean"
        )
          throw new ApiError("Invalid content response", 502);
        if (page === 0) {
          firstEtag = response.etag;
          if (data.mode === "full") rows.clear();
        }
        for (const id of data.removed_poi_ids) rows.delete(id);
        for (const row of data.items) rows.set(row.id, row);
        if (!data.has_more) {
          cache.set(language, {
            rows,
            checkpoint: data.sync_cursor,
            requestCursor: startingCursor,
            requestEtag: firstEtag,
            asOf: data.as_of,
          });
          return {
            items: [...rows.values()],
            asOf: data.as_of,
            unchanged: false,
          };
        }
        if (cursor === data.sync_cursor)
          throw new ApiError("Repeated page cursor", 502);
        cursor = data.sync_cursor;
      }
      throw new ApiError("Dataset too large for this client", 413);
    } catch (error) {
      // An expired page/reset dataset gets one clean full sync; never keep a partial page.
      if (!fresh && [400, 409].includes(error.status))
        return loadAll(language, { signal, fresh: true });
      throw error;
    }
  }
  return {
    base,
    loadAll,
    async detail(id, language, { signal } = {}) {
      if (!/^[a-f0-9]{24}$/i.test(id)) throw new ApiError("Unknown stay", 404);
      const response = await request(
        query("/poi/" + encodeURIComponent(id), { language }),
        { signal },
      );
      if (!validPoi(response.data))
        throw new ApiError("Invalid stay response", 502);
      return response.data;
    },
    async prepareGuide(id, language, { signal } = {}) {
      if (!/^[a-f0-9]{24}$/i.test(id)) throw new ApiError("Unknown stay", 404);
      const response = await request("/localizations/on-demand", {
        method: "POST",
        body: { poi_id: id, lang: language },
        signal,
      });
      if (typeof response.data.status !== "string")
        throw new ApiError("Invalid audio preparation response", 502);
      return response.data;
    },
    async guideStatus(id, language, { signal } = {}) {
      if (!/^[a-f0-9]{24}$/i.test(id)) throw new ApiError("Unknown stay", 404);
      const response = await request(
        query("/localizations/poi/" + encodeURIComponent(id) + "/status", {
          lang: language,
        }),
        { signal },
      );
      if (typeof response.data.status !== "string")
        throw new ApiError("Invalid audio status response", 502);
      return response.data;
    },
    async menus(id, { signal } = {}) {
      const response = await request(
        "/poi/" + encodeURIComponent(id) + "/menu-items",
        { signal },
      );
      if (!Array.isArray(response.data))
        throw new ApiError("Invalid room response", 502);
      return response.data;
    },
    async nearby(latitude, longitude, radius, language, { signal } = {}) {
      const response = await request(
        query("/poi/nearby", {
          latitude,
          longitude,
          radius_m: radius,
          language,
          limit: 200,
        }),
        { signal },
      );
      if (
        !Array.isArray(response.data.items) ||
        !response.data.items.every(validPoi)
      )
        throw new ApiError("Invalid nearby response", 502);
      return response.data;
    },
    async check({ signal } = {}) {
      const response = await request("/health/ready", { signal });
      if (response.data.status !== "ready")
        throw new ApiError("Backend not ready", 503);
      return response.data;
    },
  };
}
