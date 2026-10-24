import test from "node:test";
import assert from "node:assert/strict";
import { createBookingClient, newRequestId } from "../src/booking-api.mjs";

const me = {
  id: "customer",
  full_name: "Test Guest",
  realm: "auth_users",
  permissions: ["poi.read"],
};
const tokens = (access = "access-1", refresh = "refresh-1") => ({
  user: me,
  access_token: access,
  refresh_token: refresh,
});
const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });

test("booking request IDs remain valid UUIDs", () => {
  const ids = new Set(Array.from({ length: 100 }, newRequestId));
  assert.equal(ids.size, 100);
  for (const id of ids)
    assert.match(
      id,
      /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/,
    );
});

test("customer reservations require sign in and send the original request ID without a client price", async () => {
  const calls = [];
  const api = createBookingClient("/api", () => {}, {
    fetcher: async (url, options) => {
      calls.push({ url, options });
      if (url.endsWith("/session")) return json(tokens());
      if (url.endsWith("/me")) return json(me);
      return json({ id: "booking-1" }, 201);
    },
  });
  await assert.rejects(
    () => api.create({}),
    (e) => e.status === 401,
  );
  assert.equal(calls.length, 0);
  await api.login("guest", "password");
  const body = {
    request_id: newRequestId(),
    room_type_id: "room",
    check_in: "2027-01-01",
    check_out: "2027-01-02",
  };
  await api.create(body);
  assert.equal(calls.at(-1).url, "/api/bookings");
  assert.equal(calls.at(-1).options.headers.Authorization, "Bearer access-1");
  assert.deepEqual(JSON.parse(calls.at(-1).options.body), body);
  assert.equal(calls.at(-1).options.credentials, "omit");
});

test("simultaneous expired-token requests share one refresh and retain administrator permissions", async () => {
  let refreshes = 0,
    current;
  const admin = {
    ...me,
    realm: "admin_users",
    permissions: ["booking.read", "booking.update"],
  };
  const api = createBookingClient(
    "/api",
    (v) => {
      current = v;
    },
    {
      admin: true,
      fetcher: async (url, options) => {
        if (url.endsWith("/login")) return json(tokens());
        if (url.endsWith("/me")) return json(admin);
        if (url.endsWith("/refresh")) {
          refreshes++;
          await new Promise((resolve) => setTimeout(resolve, 5));
          return json(tokens("access-2", "refresh-2"));
        }
        return options.headers.Authorization === "Bearer access-1"
          ? json({ detail: "expired" }, 401)
          : json({ items: [], total: 0 });
      },
    },
  );
  await api.login("admin", "password");
  await Promise.all([api.list(), api.list()]);
  assert.equal(refreshes, 1);
  assert.equal(current.refreshToken, "refresh-2");
  assert.deepEqual(current.user.permissions, admin.permissions);
});

test("availability is public and preserves the date and room query contract", async () => {
  let path;
  const api = createBookingClient("/api", () => {}, {
    fetcher: async (url) => {
      path = url;
      return json({ available: true, remaining: 1 });
    },
  });
  await api.availability({
    poi_id: "poi",
    room_type_id: "room",
    check_in: "2027-01-01",
    check_out: "2027-01-02",
    guests: 2,
  });
  const url = new URL(path, "http://test");
  assert.equal(url.pathname, "/api/bookings/availability");
  assert.equal(url.searchParams.get("room_type_id"), "room");
  assert.equal(url.searchParams.get("guests"), "2");
});

test("inventory conflicts and lost responses never automatically resubmit a reservation", async () => {
  let writes = 0;
  const api = createBookingClient("/api", () => {}, {
    fetcher: async (url) => {
      if (url.endsWith("/session")) return json(tokens());
      if (url.endsWith("/me")) return json(me);
      writes++;
      return json(
        { detail: "Room is fully booked for one or more selected nights" },
        409,
      );
    },
  });
  await api.login("guest", "password");
  await assert.rejects(
    () => api.create({ request_id: newRequestId() }),
    (e) => e.status === 409 && e.message.includes("fully booked"),
  );
  assert.equal(writes, 1);
});

test("logout clears customer access even when the backend is unreachable", async () => {
  let current;
  const api = createBookingClient(
    "/api",
    (v) => {
      current = v;
    },
    {
      fetcher: async (url) => {
        if (url.endsWith("/session")) return json(tokens());
        if (url.endsWith("/me")) return json(me);
        throw new TypeError("Network unavailable");
      },
    },
  );
  await api.login("guest", "password");
  await assert.rejects(() => api.logout());
  assert.equal(current, null);
  await assert.rejects(
    () => api.mine(),
    (e) => e.status === 401,
  );
});
