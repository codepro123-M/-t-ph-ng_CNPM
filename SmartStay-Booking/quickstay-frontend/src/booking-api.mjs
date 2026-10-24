import { ApiError, normalizeBase } from "./api.mjs";

export function newRequestId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) crypto.getRandomValues(bytes);
  else for (let i = 0; i < 16; i++) bytes[i] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const s = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${s.slice(0, 8)}-${s.slice(8, 12)}-${s.slice(12, 16)}-${s.slice(16, 20)}-${s.slice(20)}`;
}

export function createBookingClient(
  base,
  onSession = () => {},
  { admin = false, fetcher = fetch } = {},
) {
  base = normalizeBase(base);
  const auth = admin ? "/admin/auth" : "/api/v1/auth";
  let session = null,
    refreshing = null;
  function update(value) {
    session = value;
    onSession(value);
    return value;
  }
  function tokens(result) {
    if (!result.user || !result.access_token || !result.refresh_token)
      throw new ApiError("Invalid sign-in response", 502);
    return {
      user: result.user,
      accessToken: result.access_token,
      refreshToken: result.refresh_token,
    };
  }
  async function raw(path, { method = "GET", body, token, signal } = {}) {
    const response = await fetcher(base + path, {
      method,
      credentials: "omit",
      cache: "no-store",
      signal: signal || AbortSignal.timeout(20000),
      headers: {
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: "Bearer " + token } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (response.status === 204) return null;
    let data;
    if (response.headers.get("content-type")?.includes("application/json"))
      data = await response.json();
    if (!response.ok) {
      const message =
        typeof data?.detail === "string"
          ? data.detail
          : Array.isArray(data?.detail)
            ? data.detail.map((e) => e.msg).join("; ")
            : "SmartStay request failed";
      throw new ApiError(message, response.status);
    }
    if (data === undefined)
      throw new ApiError(
        "The API returned a web page instead of JSON. Check the backend URL.",
        502,
      );
    return data;
  }
  async function refresh() {
    if (!refreshing) {
      const current = session;
      refreshing = raw(auth + "/refresh", {
        method: "POST",
        body: { refresh_token: current.refreshToken },
      })
        .then(async (result) => {
          const value = tokens(result);
          const me = await raw(auth + "/me", { token: value.accessToken });
          if (session !== current)
            throw new ApiError("Session changed. Please sign in again.", 401);
          return update({ ...value, user: me });
        })
        .catch((error) => {
          if (session === current && [400, 401, 403].includes(error.status))
            update(null);
          throw error;
        })
        .finally(() => {
          refreshing = null;
        });
    }
    return refreshing;
  }
  async function request(path, options = {}) {
    if (!session) throw new ApiError("Please sign in to continue.", 401);
    try {
      return await raw(path, { ...options, token: session.accessToken });
    } catch (error) {
      if (error.status !== 401 || !session?.refreshToken) throw error;
      await refresh();
      return raw(path, { ...options, token: session.accessToken });
    }
  }
  return {
    async login(username, password) {
      const result = await raw(
        admin ? "/admin/auth/login" : "/api/v1/auth/session",
        { method: "POST", body: { username, password, mode: "bearer" } },
      );
      const value = tokens(result);
      const me = await raw(auth + "/me", { token: value.accessToken });
      return update({ ...value, user: me });
    },
    register: (body) => raw("/api/v1/auth/register", { method: "POST", body }),
    async logout() {
      const value = session;
      update(null);
      if (value?.refreshToken)
        await raw(auth + "/logout", {
          method: "POST",
          body: { refresh_token: value.refreshToken },
        });
    },
    clear: () => update(null),
    availability: (params, signal) =>
      raw("/bookings/availability?" + new URLSearchParams(params), { signal }),
    create: (body) => request("/bookings", { method: "POST", body }),
    mine: (page = 1) =>
      request("/bookings?" + new URLSearchParams({ page, limit: 20 })),
    cancel: (id, revision) =>
      request("/bookings/" + encodeURIComponent(id) + "/cancel", {
        method: "PATCH",
        body: { expected_revision: revision },
      }),
    list: ({ page = 1, status = "", search = "" } = {}) =>
      request(
        "/admin/bookings?" +
          new URLSearchParams({
            page,
            limit: 20,
            ...(status ? { status } : {}),
            ...(search ? { search } : {}),
          }),
      ),
    change: (id, revision, status) =>
      request("/admin/bookings/" + encodeURIComponent(id), {
        method: "PATCH",
        body: { expected_revision: revision, status },
      }),
    createProperty: (body) => request("/poi", { method: "POST", body }),
    createRoom: (body) =>
      request("/admin/menu-items", { method: "POST", body }),
  };
}
