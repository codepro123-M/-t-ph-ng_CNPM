import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  AlertCircle,
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Hotel,
  Loader2,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Users,
  X,
} from "lucide-react";
import { useApp } from "./context.jsx";
import { money } from "./model.mjs";
import { newRequestId } from "./booking-api.mjs";
import "./bookings.css";

const label = (lang, vi, en) => (lang === "vi" ? vi : en);
const statuses = {
  pending: ["Chờ xác nhận", "Pending"],
  confirmed: ["Đã xác nhận", "Confirmed"],
  cancelled: ["Đã hủy", "Cancelled"],
  completed: ["Đã hoàn thành", "Completed"],
};
export function StatusBadge({ status }) {
  const { lang } = useApp();
  return (
    <span className={"reservation-status status-" + status}>
      <i />
      {statuses[status]?.[lang === "vi" ? 0 : 1] || status}
    </span>
  );
}
function ErrorBox({ error }) {
  return error ? (
    <div className="booking-error" role="alert">
      <AlertCircle size={18} />
      <span>{error}</span>
    </div>
  ) : null;
}
function Spinner() {
  return <Loader2 size={17} className="spin" />;
}
function formatDate(value, lang) {
  return new Date(value + "T12:00:00").toLocaleDateString(
    lang === "vi" ? "vi-VN" : "en-GB",
  );
}
function displayError(error, lang) {
  if (error.status === 401)
    return label(
      lang,
      "Phiên đăng nhập đã hết. Vui lòng đăng nhập lại.",
      "Please sign in again.",
    );
  if (error.status === 403)
    return label(
      lang,
      "Tài khoản không có quyền thực hiện thao tác này.",
      "This account does not have the required permission.",
    );
  if (!error.status)
    return label(
      lang,
      "Không kết nối được máy chủ. Kiểm tra backend rồi thử lại.",
      "Cannot reach the server. Check your backend and retry.",
    );
  const map = {
    "Room is fully booked for one or more selected nights":
      "Phòng đã hết trong khoảng ngày đã chọn. Vui lòng chọn ngày hoặc loại phòng khác.",
    "Booking changed; reload and retry":
      "Đơn vừa được cập nhật. Danh sách sẽ tải lại, bạn kiểm tra trạng thái mới rồi thử lại.",
    "Guest count exceeds the room capacity":
      "Số khách vượt quá sức chứa của phòng.",
    "Untrusted request origin":
      "Thêm địa chỉ website này vào TRUSTED_ORIGINS của backend rồi tạo lại container backend.",
  };
  return lang === "vi" ? map[error.message] || error.message : error.message;
}

// Poll only while the tab is visible; one request at a time and no late responses.
function useOrders(api, enabled, filters, lang) {
  const [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [updated, setUpdated] = useState(null);
  const active = useRef(0),
    pending = useRef(false),
    running = useRef(null);
  const load = useCallback(async () => {
    if (!enabled) return;
    if (pending.current) return running.current;
    const version = active.current;
    pending.current = true;
    setBusy(true);
    const promise = (async () => {
      try {
        const next = filters ? await api.list(filters) : await api.mine(1);
        if (active.current === version) {
          setResult(next);
          setError("");
          setUpdated(new Date());
        }
      } catch (e) {
        if (active.current === version) setError(displayError(e, lang));
      } finally {
        if (active.current === version) {
          pending.current = false;
          setBusy(false);
        }
      }
    })();
    running.current = promise;
    return promise;
  }, [api, enabled, filters?.page, filters?.status, filters?.search, lang]);
  useEffect(() => {
    active.current++;
    pending.current = false;
    setResult(null);
    setError("");
    setBusy(false);
    if (!enabled) return;
    load();
    const refresh = () => {
      if (document.visibilityState === "visible") load();
    };
    const timer = setInterval(refresh, 5000);
    window.addEventListener("focus", refresh);
    return () => {
      active.current++;
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [load, enabled]);
  return { result, error, busy, updated, load };
}

export function Checkout({ reservation, Modal }) {
  const {
    bookingApi,
    session,
    setAuthOpen,
    setBookingModal,
    navigate,
    toast,
    lang,
  } = useApp();
  const { poi, room, search } = reservation;
  const [quote, setQuote] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [requestId, setRequestId] = useState(newRequestId),
    payload = useRef(null);
  const checkQuote = useCallback(async () => {
    setError("");
    try {
      setQuote(
        await bookingApi.availability({
          poi_id: poi.id,
          room_type_id: room.id,
          check_in: search.checkIn,
          check_out: search.checkOut,
          guests: search.guests,
        }),
      );
    } catch (e) {
      setError(displayError(e, lang));
    }
  }, [
    bookingApi,
    poi.id,
    room.id,
    search.checkIn,
    search.checkOut,
    search.guests,
    lang,
  ]);
  useEffect(() => {
    checkQuote();
  }, [checkQuote]);
  async function submit(e) {
    e.preventDefault();
    if (!session) {
      setAuthOpen(true);
      return;
    }
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    const next = {
      poi_id: poi.id,
      room_type_id: room.id,
      check_in: search.checkIn,
      check_out: search.checkOut,
      guests: Number(search.guests),
      ...fields,
    };
    const serialized = JSON.stringify(next);
    const id =
      payload.current && payload.current !== serialized
        ? newRequestId()
        : requestId;
    payload.current = serialized;
    setRequestId(id);
    setBusy(true);
    setError("");
    try {
      const booking = await bookingApi.create({ ...next, request_id: id });
      setBookingModal(null);
      toast(
        label(
          lang,
          "Đã gửi đơn " + booking.code + ". Đang chờ khách sạn xác nhận.",
          "Booking " + booking.code + " saved. Awaiting property confirmation.",
        ),
      );
      navigate("/bookings");
    } catch (e) {
      setError(displayError(e, lang));
      if (e.status === 409) {
        setQuote(null);
        await checkQuote();
        setError(displayError(e, lang));
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={label(lang, "Xác nhận đặt phòng", "Reserve your stay")}
      onClose={() => {
        if (!busy) setBookingModal(null);
      }}
    >
      <div className="checkout-summary">
        <span className="booking-eyebrow">YOUR NEXT STAY</span>
        <h3>{poi.name}</h3>
        <p>
          {room.name} · {search.guests} {label(lang, "khách", "guests")}
        </p>
        <div>
          <CalendarDays size={17} />
          {formatDate(search.checkIn, lang)} —{" "}
          {formatDate(search.checkOut, lang)}
        </div>
      </div>
      {quote && (
        <div className="quote-total">
          <span>
            {quote.nights} {label(lang, "đêm · Tổng tiền", "nights · Total")}
          </span>
          <strong>{money(quote.total_price, quote.currency, lang)}</strong>
        </div>
      )}
      {!quote && !error && (
        <p className="inline-loading">
          <Spinner />
          {label(
            lang,
            "Đang kiểm tra phòng và giá…",
            "Checking availability and price…",
          )}
        </p>
      )}
      {quote && !quote.available && (
        <div className="booking-error">
          <AlertCircle size={18} />
          {label(
            lang,
            "Hết phòng trong khoảng ngày này. Vui lòng chọn ngày khác.",
            "This room is sold out for those dates. Please select different dates.",
          )}
        </div>
      )}
      <ErrorBox error={error} />
      {session ? (
        <form className="checkout-form" onSubmit={submit}>
          <label className="form-label">
            {label(lang, "Họ tên người nhận phòng", "Guest full name")}
            <input
              name="contact_name"
              autoComplete="name"
              defaultValue={session.user.full_name}
              required
              maxLength="100"
              disabled={busy}
            />
          </label>
          <div className="booking-form-grid">
            <label className="form-label">
              Email
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                maxLength="254"
                disabled={busy}
              />
            </label>
            <label className="form-label">
              {label(lang, "Số điện thoại", "Phone number")}
              <input
                type="tel"
                name="phone"
                autoComplete="tel"
                required
                minLength="6"
                maxLength="30"
                disabled={busy}
              />
            </label>
          </div>
          <label className="form-label">
            {label(
              lang,
              "Yêu cầu thêm (không bắt buộc)",
              "Special requests (optional)",
            )}
            <textarea name="notes" maxLength="1000" rows="3" disabled={busy} />
          </label>
          <p className="booking-help">
            {label(
              lang,
              "Đơn được lưu ở khách sạn và chờ xác nhận. Bạn thanh toán trực tiếp với khách sạn; trang này chưa thu tiền trực tuyến.",
              "Your reservation is sent to the property for confirmation. Arrange payment directly with the property; no online payment is collected here.",
            )}
          </p>
          <button
            type="submit"
            className="button button-blue full-button"
            disabled={busy || !quote?.available}
          >
            {busy ? <Spinner /> : <CheckCircle2 size={17} />}{" "}
            {label(lang, "Gửi đặt phòng", "Send reservation")}
          </button>
        </form>
      ) : (
        <div className="checkout-signin">
          <p>
            {label(
              lang,
              "Đăng nhập tài khoản khách để lưu và theo dõi đơn đặt phòng của bạn.",
              "Sign in with your customer account to save and track your booking.",
            )}
          </p>
          <button
            className="button button-blue full-button"
            onClick={() => setAuthOpen(true)}
          >
            {label(lang, "Đăng nhập để tiếp tục", "Sign in to continue")}
            <ArrowRight size={17} />
          </button>
        </div>
      )}
    </Modal>
  );
}

function ReservationDetails({ booking, lang }) {
  return (
    <div className="reservation-details">
      <div>
        <h3>{booking.property_name}</h3>
        <p>{booking.room_name}</p>
        <p>{booking.property_address}</p>
      </div>
      <div>
        <span>{label(lang, "Nhận / trả phòng", "Check-in / check-out")}</span>
        <strong>
          {formatDate(booking.check_in, lang)} —{" "}
          {formatDate(booking.check_out, lang)}
        </strong>
        <p>
          {booking.nights} {label(lang, "đêm", "nights")} · {booking.guests}{" "}
          {label(lang, "khách", "guests")}
        </p>
      </div>
      <div>
        <span>{label(lang, "Tổng tiền", "Total")}</span>
        <strong>{money(booking.total_price, booking.currency, lang)}</strong>
        <p>{label(lang, "Thanh toán với khách sạn", "Pay at the property")}</p>
      </div>
    </div>
  );
}

export function CustomerBookings() {
  const { bookingApi, session, setAuthOpen, lang, navigate, toast } = useApp();
  const { result, error, busy, load } = useOrders(
    bookingApi,
    !!session,
    null,
    lang,
  );
  const [cancel, setCancel] = useState(null),
    [changing, setChanging] = useState(false),
    [actionError, setActionError] = useState("");
  async function cancelOrder(row) {
    setChanging(true);
    setActionError("");
    try {
      await bookingApi.cancel(row.id, row.revision);
      setCancel(null);
      toast(label(lang, "Đã hủy đơn đặt phòng.", "Reservation cancelled."));
    } catch (e) {
      setActionError(displayError(e, lang));
    } finally {
      setChanging(false);
      await load();
    }
  }
  return (
    <main className="container inner-page live-bookings">
      <div className="reservation-heading">
        <div>
          <span className="booking-eyebrow">YOUR JOURNEY</span>
          <h1>{label(lang, "Đặt phòng của tôi", "My reservations")}</h1>
          <p>
            {label(
              lang,
              "Theo dõi kỳ nghỉ của bạn và trạng thái từ khách sạn.",
              "Your upcoming stays, with the latest updates from your host.",
            )}
          </p>
        </div>
        {session && (
          <button
            className="button button-outline"
            onClick={load}
            disabled={busy}
          >
            {busy ? <Spinner /> : <RefreshCw size={16} />}{" "}
            {label(lang, "Làm mới", "Refresh")}
          </button>
        )}
      </div>
      {!session ? (
        <div className="reservation-empty">
          <ShieldCheck size={38} />
          <h2>
            {label(
              lang,
              "Đăng nhập để xem đơn của bạn",
              "Your reservations, all in one place",
            )}
          </h2>
          <p>
            {label(
              lang,
              "Sử dụng tài khoản đã dùng khi đặt phòng.",
              "Use the same account you used to make your reservation.",
            )}
          </p>
          <button
            className="button button-blue"
            onClick={() => setAuthOpen(true)}
          >
            {label(lang, "Đăng nhập", "Sign in")}
          </button>
        </div>
      ) : (
        <>
          <p className="sync-caption">
            <i />
            {label(
              lang,
              "Tự cập nhật mỗi 5 giây khi đang mở trang",
              "Updates every 5 seconds while this page is open",
            )}
          </p>
          <ErrorBox error={error || actionError} />
          {!result && busy && (
            <p className="inline-loading">
              <Spinner />
              {label(lang, "Đang tải đơn…", "Loading reservations…")}
            </p>
          )}
          {result?.items.map((row) => (
            <article className="reservation-card" key={row.id}>
              <div className="reservation-card-top">
                <span className="booking-code">{row.code}</span>
                <StatusBadge status={row.status} />
              </div>
              <ReservationDetails booking={row} lang={lang} />
              <div className="reservation-card-footer">
                <p>
                  {row.contact_name} · {row.phone}
                </p>
                <div>
                  <button
                    className="text-link"
                    onClick={() => navigate("/rooms/" + row.poi_id)}
                  >
                    {label(lang, "Xem khách sạn", "View property")}
                    <ArrowRight size={15} />
                  </button>
                  {["pending", "confirmed"].includes(row.status) && (
                    <button
                      className="button button-outline button-small"
                      onClick={() => {
                        setCancel(row.id);
                        setActionError("");
                      }}
                    >
                      {label(lang, "Hủy đặt phòng", "Cancel reservation")}
                    </button>
                  )}
                </div>
              </div>
              {cancel === row.id && (
                <div className="cancel-confirm">
                  <p>
                    {label(
                      lang,
                      "Xác nhận hủy đơn này? Phòng sẽ được mở lại cho khách khác.",
                      "Cancel this reservation? The room will become available to other guests.",
                    )}
                  </p>
                  <button
                    className="button button-danger"
                    disabled={changing}
                    onClick={() => cancelOrder(row)}
                  >
                    {changing ? (
                      <Spinner />
                    ) : (
                      label(lang, "Xác nhận hủy", "Confirm cancellation")
                    )}
                  </button>
                  <button
                    className="button button-outline"
                    disabled={changing}
                    onClick={() => setCancel(null)}
                  >
                    {label(lang, "Giữ đơn", "Keep reservation")}
                  </button>
                </div>
              )}
            </article>
          ))}
          {result && !result.items.length && (
            <div className="reservation-empty">
              <CalendarDays size={40} />
              <h2>
                {label(
                  lang,
                  "Chưa có đặt phòng",
                  "Your next journey starts here",
                )}
              </h2>
              <p>
                {label(
                  lang,
                  "Chọn nơi lưu trú và gửi đặt phòng đầu tiên của bạn.",
                  "Find a place you love and make your first reservation.",
                )}
              </p>
              <button
                className="button button-blue"
                onClick={() => navigate("/rooms")}
              >
                {label(lang, "Khám phá khách sạn", "Explore stays")}
                <ArrowRight size={17} />
              </button>
            </div>
          )}
          {result?.total > 20 && (
            <p className="booking-help">
              {label(
                lang,
                "Đang hiển thị 20 đơn mới nhất.",
                "Showing your 20 most recent reservations.",
              )}
            </p>
          )}
        </>
      )}
    </main>
  );
}

function AdminLogin() {
  const { adminApi, lang, setSettingsOpen } = useApp();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function login(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(e.currentTarget);
    try {
      await adminApi.login(
        String(form.get("username")),
        String(form.get("password")),
      );
    } catch (e) {
      setError(
        e.status === 401
          ? label(
              lang,
              "Sai tên đăng nhập hoặc mật khẩu admin.",
              "Incorrect administrator credentials.",
            )
          : displayError(e, lang),
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="admin-login-page">
      <div className="admin-login-story">
        <span className="booking-eyebrow">QUICKSTAY · HOST DESK</span>
        <h1>
          {label(
            lang,
            "Mỗi kỳ nghỉ tốt đẹp bắt đầu từ bạn.",
            "Great stays start with you.",
          )}
        </h1>
        <p>
          {label(
            lang,
            "Nhận đặt phòng, chăm sóc khách và quản lý nơi lưu trú từ một nơi.",
            "Welcome your guests and manage every reservation in one thoughtful workspace.",
          )}
        </p>
        <div className="admin-story-note">
          <ShieldCheck size={24} />
          <span>
            {label(
              lang,
              "Khu vực dành riêng cho quản trị viên",
              "A workspace for property administrators",
            )}
          </span>
        </div>
      </div>
      <section className="admin-login-card">
        <span className="admin-icon">
          <Hotel size={25} />
        </span>
        <h2>{label(lang, "Đăng nhập quản trị", "Welcome to the host desk")}</h2>
        <p>
          {label(
            lang,
            "Dùng tài khoản admin của backend SmartStay.",
            "Sign in with your SmartStay administrator account.",
          )}
        </p>
        <form onSubmit={login}>
          <label className="form-label">
            {label(lang, "Tên đăng nhập admin", "Administrator username")}
            <input
              name="username"
              autoComplete="username"
              required
              disabled={busy}
            />
          </label>
          <label className="form-label">
            {label(lang, "Mật khẩu", "Password")}
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
              disabled={busy}
            />
          </label>
          <ErrorBox error={error} />
          <button className="button button-blue full-button" disabled={busy}>
            {busy ? (
              <Spinner />
            ) : (
              label(lang, "Đăng nhập dashboard", "Open dashboard")
            )}
            <ArrowRight size={17} />
          </button>
        </form>
        <p className="booking-help">
          {label(
            lang,
            "Tài khoản khách đăng ký trên website không có quyền truy cập dashboard. Tải lại trang sẽ yêu cầu đăng nhập lại.",
            "Customer accounts cannot access this dashboard. Reloading the page requires signing in again.",
          )}
        </p>
        <button className="text-link" onClick={() => setSettingsOpen(true)}>
          <Settings size={15} />
          {label(lang, "Cấu hình kết nối backend", "Connection settings")}
        </button>
      </section>
    </div>
  );
}

function PropertiesPanel() {
  const { client, adminApi, lang, load: reloadPublic } = useApp();
  const [properties, setProperties] = useState([]),
    [formOpen, setFormOpen] = useState(false),
    [created, setCreated] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const load = useCallback(async () => {
    try {
      setProperties((await client.loadAll("vi", { fresh: true })).items);
    } catch (e) {
      setError(displayError(e, lang));
    }
  }, [client, lang]);
  useEffect(() => {
    load();
  }, [load]);
  async function submit(e) {
    e.preventDefault();
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError("");
    setNotice("");
    try {
      let poi = created;
      if (!poi) {
        poi = await adminApi.createProperty({
          name: f.property_name,
          description: f.description,
          category: f.category,
          address: f.address,
          latitude: Number(f.latitude),
          longitude: Number(f.longitude),
          images: [],
          is_active: true,
        });
        setCreated(poi);
      }
      await adminApi.createRoom({
        poi_id: poi.id,
        name: f.room_name,
        price: f.price,
        currency: "VND",
        capacity: Number(f.capacity),
        inventory: Number(f.inventory),
        kind: "room_type",
        is_available: true,
        amenities: [],
      });
      setFormOpen(false);
      setCreated(null);
      setNotice(
        label(
          lang,
          "Đã lưu khách sạn và loại phòng. Khách có thể đặt ngay từ trang Hotels.",
          "Property and room saved. Guests can now book from the Hotels page.",
        ),
      );
      await load();
      reloadPublic();
    } catch (e) {
      setError(displayError(e, lang));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="properties-panel">
      <div className="admin-panel-heading">
        <div>
          <h2>
            {label(
              lang,
              "Khách sạn & loại phòng",
              "Properties & room inventory",
            )}
          </h2>
          <p>
            {label(
              lang,
              "Mỗi loại phòng có số lượng phòng thực tế và giá mỗi đêm.",
              "Set a nightly price and the actual number of rooms for each room type.",
            )}
          </p>
        </div>
        <button
          className="button button-blue"
          onClick={() => {
            setFormOpen(!formOpen);
            setCreated(null);
            setError("");
          }}
        >
          <Plus size={17} />
          {label(lang, "Thêm khách sạn", "Add property")}
        </button>
      </div>
      {notice && (
        <p className="booking-success" role="status">
          <CheckCircle2 size={18} />
          {notice}
        </p>
      )}
      <ErrorBox error={error} />
      {formOpen && (
        <form className="property-form" onSubmit={submit}>
          <div className="admin-panel-heading">
            <h3>
              {created
                ? label(lang, "Thêm loại phòng cho: ", "Add a room to: ") +
                  created.name
                : label(lang, "Thông tin nơi lưu trú", "Property information")}
            </h3>
            <button
              type="button"
              className="icon-button"
              aria-label="Close property form"
              onClick={() => {
                setFormOpen(false);
                setCreated(null);
              }}
              disabled={busy}
            >
              <X size={18} />
            </button>
          </div>
          {!created && (
            <>
              <div className="booking-form-grid">
                <label className="form-label">
                  {label(lang, "Tên khách sạn", "Property name")}
                  <input name="property_name" required maxLength="200" />
                </label>
                <label className="form-label">
                  {label(lang, "Loại hình", "Category")}
                  <select name="category">
                    <option value="hotel">Hotel</option>
                    <option value="homestay">Homestay</option>
                    <option value="resort">Resort</option>
                    <option value="apartment">Apartment</option>
                    <option value="villa">Villa</option>
                  </select>
                </label>
              </div>
              <label className="form-label">
                {label(lang, "Địa chỉ", "Address")}
                <input name="address" required maxLength="500" />
              </label>
              <label className="form-label">
                {label(
                  lang,
                  "Giới thiệu bằng tiếng Việt",
                  "Vietnamese description",
                )}
                <textarea
                  name="description"
                  required
                  maxLength="20000"
                  rows="3"
                />
              </label>
              <div className="booking-form-grid">
                <label className="form-label">
                  {label(lang, "Vĩ độ", "Latitude")}
                  <input
                    name="latitude"
                    type="number"
                    step="any"
                    min="-90"
                    max="90"
                    required
                    placeholder="10.7769"
                  />
                </label>
                <label className="form-label">
                  {label(lang, "Kinh độ", "Longitude")}
                  <input
                    name="longitude"
                    type="number"
                    step="any"
                    min="-180"
                    max="180"
                    required
                    placeholder="106.7009"
                  />
                </label>
              </div>
            </>
          )}
          <h3>{label(lang, "Loại phòng có thể đặt", "Bookable room type")}</h3>
          <div className="booking-form-grid">
            <label className="form-label">
              {label(lang, "Tên loại phòng", "Room type name")}
              <input
                name="room_name"
                required
                maxLength="160"
                placeholder="Deluxe Double"
              />
            </label>
            <label className="form-label">
              {label(lang, "Giá mỗi đêm (VND)", "Nightly price (VND)")}
              <input
                name="price"
                type="number"
                min="0"
                max="999999999999"
                step="1"
                required
                placeholder="650000"
              />
            </label>
            <label className="form-label">
              {label(lang, "Số khách tối đa / phòng", "Guests per room")}
              <input
                name="capacity"
                type="number"
                min="1"
                max="100"
                defaultValue="2"
                required
              />
            </label>
            <label className="form-label">
              {label(lang, "Số phòng thực tế", "Number of rooms")}
              <input
                name="inventory"
                type="number"
                min="1"
                max="1000"
                defaultValue="1"
                required
              />
            </label>
          </div>
          {created && (
            <p className="booking-help">
              {label(
                lang,
                "Khách sạn đã được lưu. Nếu lưu loại phòng lỗi, hãy sửa rồi gửi lại; không cần tạo lại khách sạn.",
                "The property is already saved. If the room cannot be saved, correct it and retry without creating the property again.",
              )}
            </p>
          )}
          <button className="button button-blue" disabled={busy}>
            {busy ? <Spinner /> : <CheckCircle2 size={17} />}{" "}
            {label(lang, "Lưu khách sạn và phòng", "Save property and room")}
          </button>
        </form>
      )}
      {!properties.length && !formOpen && (
        <div className="reservation-empty">
          <Hotel size={36} />
          <h3>
            {label(
              lang,
              "Chưa có khách sạn công khai",
              "No published properties yet",
            )}
          </h3>
          <p>
            {label(
              lang,
              "Thêm khách sạn và một loại phòng để bắt đầu nhận đặt phòng.",
              "Add a property and one room type to start receiving reservations.",
            )}
          </p>
        </div>
      )}
      {properties.map((p) => (
        <article key={p.id} className="property-row">
          <div>
            <h3>{p.name}</h3>
            <p>{p.address}</p>
            <div className="property-room-tags">
              {p.menu_items
                .filter((r) => r.kind === "room_type")
                .map((r) => (
                  <span key={r.id}>
                    {r.name} · {r.inventory ?? 1}{" "}
                    {label(lang, "phòng", "rooms")} ·{" "}
                    {money(r.price, r.currency, lang)} /{" "}
                    {label(lang, "đêm", "night")}
                  </span>
                ))}
            </div>
          </div>
          <button
            className="button button-outline button-small"
            onClick={() => {
              setCreated(p);
              setFormOpen(true);
              setError("");
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
          >
            <Plus size={15} />
            {label(lang, "Thêm loại phòng", "Add room type")}
          </button>
        </article>
      ))}
    </section>
  );
}

export function AdminDashboard() {
  const { adminApi, adminSession, connection, setSettingsOpen, lang } =
    useApp();
  const [tab, setTab] = useState("bookings"),
    [filters, setFilters] = useState({ page: 1, status: "", search: "" }),
    [searchText, setSearchText] = useState(""),
    [actionError, setActionError] = useState(""),
    [changing, setChanging] = useState(""),
    [expanded, setExpanded] = useState(""),
    [confirmCancel, setConfirmCancel] = useState("");
  const canRead = adminSession?.user.permissions?.includes("booking.read");
  const canEdit = adminSession?.user.permissions?.includes("booking.update");
  const canCreate =
    adminSession?.user.permissions?.includes("poi.create") &&
    adminSession?.user.permissions?.includes("content.publish") &&
    adminSession?.user.permissions?.includes("menu.create");
  const { result, busy, error, updated, load } = useOrders(
    adminApi,
    !!adminSession && canRead && tab === "bookings",
    filters,
    lang,
  );
  async function change(row, status) {
    setChanging(row.id);
    setActionError("");
    try {
      await adminApi.change(row.id, row.revision, status);
      setConfirmCancel("");
    } catch (e) {
      setActionError(displayError(e, lang));
    } finally {
      setChanging("");
      await load();
    }
  }
  if (connection.mode !== "api")
    return (
      <main className="container inner-page">
        <div className="reservation-empty">
          <ShieldCheck size={40} />
          <h1>
            {label(
              lang,
              "Kết nối backend để quản trị",
              "Connect your backend to manage stays",
            )}
          </h1>
          <p>
            {label(
              lang,
              "Dashboard sử dụng dữ liệu thật từ SmartStay.",
              "This dashboard uses your live SmartStay data.",
            )}
          </p>
          <button
            className="button button-blue"
            onClick={() => setSettingsOpen(true)}
          >
            {label(lang, "Kết nối SmartStay", "Connect SmartStay")}
            <ArrowRight size={17} />
          </button>
        </div>
      </main>
    );
  if (!adminSession)
    return (
      <main className="container inner-page">
        <AdminLogin />
      </main>
    );
  return (
    <main className="admin-workspace container inner-page">
      <aside className="admin-sidebar">
        <div className="host-desk-brand">
          <Hotel size={22} />
          <div>
            Host desk<small>QUICKSTAY</small>
          </div>
        </div>
        <nav aria-label="Dashboard navigation">
          <button
            className={tab === "bookings" ? "selected" : ""}
            onClick={() => setTab("bookings")}
          >
            <ClipboardList size={18} />
            {label(lang, "Đơn đặt phòng", "Reservations")}
          </button>
          {canCreate && (
            <button
              className={tab === "properties" ? "selected" : ""}
              onClick={() => setTab("properties")}
            >
              <Hotel size={18} />
              {label(lang, "Khách sạn & phòng", "Properties & rooms")}
            </button>
          )}
          <button onClick={() => setSettingsOpen(true)}>
            <Settings size={18} />
            {label(lang, "Kết nối", "Connection")}
          </button>
        </nav>
        <div className="admin-sidebar-bottom">
          <ShieldCheck size={18} />
          <span>
            {adminSession.user.full_name}
            <small>{adminSession.user.role}</small>
          </span>
          <button
            className="icon-button"
            aria-label="Sign out of dashboard"
            onClick={() =>
              adminApi
                .logout()
                .catch((e) => setActionError(displayError(e, lang)))
            }
          >
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="admin-main">
        <div className="reservation-heading">
          <div>
            <span className="booking-eyebrow">
              HOST DESK / {tab === "bookings" ? "RESERVATIONS" : "PROPERTIES"}
            </span>
            <h1>
              {tab === "bookings"
                ? label(lang, "Quản lý đặt phòng", "Your reservations")
                : label(lang, "Nơi lưu trú của bạn", "Your properties")}
            </h1>
            <p>
              {label(
                lang,
                "Theo dõi và chăm sóc từng kỳ nghỉ.",
                "A thoughtful welcome for every guest.",
              )}
            </p>
          </div>
          <a className="button button-outline" href="#/rooms">
            {label(lang, "Xem website khách", "Guest website")}
            <ArrowRight size={16} />
          </a>
        </div>
        {tab === "properties" ? (
          <PropertiesPanel />
        ) : (
          <>
            <div className="dashboard-stat-grid">
              {[
                [
                  "total",
                  label(lang, "Tổng đơn", "All reservations"),
                  ClipboardList,
                ],
                [
                  "pending",
                  label(lang, "Chờ xác nhận", "Awaiting confirmation"),
                  CalendarDays,
                ],
                [
                  "confirmed",
                  label(lang, "Đã xác nhận", "Confirmed stays"),
                  CheckCircle2,
                ],
                ["cancelled", label(lang, "Đã hủy", "Cancelled"), X],
              ].map(([key, title, Icon]) => (
                <button
                  key={key}
                  className={"dashboard-stat stat-" + key}
                  onClick={() =>
                    setFilters((f) => ({
                      ...f,
                      page: 1,
                      status: key === "total" ? "" : key,
                    }))
                  }
                >
                  <div>
                    <span>{title}</span>
                    <Icon size={19} />
                  </div>
                  <strong>{result?.summary?.[key] ?? "—"}</strong>
                  <small>
                    {key === "pending"
                      ? label(
                          lang,
                          "Cần bạn phản hồi",
                          "Waiting for your response",
                        )
                      : label(
                          lang,
                          "Cập nhật từ hệ thống",
                          "From your booking records",
                        )}
                  </small>
                </button>
              ))}
            </div>
            <section className="admin-orders">
              <div className="admin-orders-toolbar">
                <form
                  className="admin-search"
                  onSubmit={(e) => {
                    e.preventDefault();
                    setFilters((f) => ({ ...f, page: 1, search: searchText }));
                  }}
                >
                  <Search size={17} />
                  <input
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    placeholder={label(
                      lang,
                      "Mã đơn, tên khách, email…",
                      "Booking code, guest, email…",
                    )}
                    maxLength="100"
                    aria-label="Search reservations"
                  />
                  <button className="button button-small button-dark">
                    {label(lang, "Tìm", "Search")}
                  </button>
                </form>
                <label className="admin-status-filter">
                  <span className="sr-only">Status</span>
                  <select
                    value={filters.status}
                    onChange={(e) =>
                      setFilters((f) => ({
                        ...f,
                        page: 1,
                        status: e.target.value,
                      }))
                    }
                  >
                    <option value="">
                      {label(lang, "Tất cả trạng thái", "All statuses")}
                    </option>
                    {Object.entries(statuses).map(([v, n]) => (
                      <option key={v} value={v}>
                        {n[lang === "vi" ? 0 : 1]}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="icon-button"
                  onClick={load}
                  disabled={busy}
                  aria-label="Refresh reservations"
                >
                  {busy ? <Spinner /> : <RefreshCw size={18} />}
                </button>
              </div>
              <div className="admin-sync-row">
                <p className="sync-caption">
                  <i />
                  {label(
                    lang,
                    "Tự cập nhật mỗi 5 giây",
                    "Auto refresh every 5 seconds",
                  )}
                </p>
                <span>
                  {updated
                    ? updated.toLocaleTimeString(
                        lang === "vi" ? "vi-VN" : "en-GB",
                      )
                    : "—"}
                </span>
              </div>
              <ErrorBox
                error={
                  error ||
                  actionError ||
                  (!canRead
                    ? label(
                        lang,
                        "Tài khoản chưa được cấp booking.read. Đăng nhập lại sau khi cập nhật backend.",
                        "This account needs booking.read. Sign in again after updating the backend.",
                      )
                    : "")
                }
              />
              <div className="admin-table-scroll">
                <table className="admin-booking-table">
                  <thead>
                    <tr>
                      <th>
                        {label(lang, "Mã đơn / khách", "Booking / guest")}
                      </th>
                      <th>
                        {label(lang, "Khách sạn / phòng", "Property / room")}
                      </th>
                      <th>{label(lang, "Ngày lưu trú", "Stay dates")}</th>
                      <th>{label(lang, "Tổng tiền", "Total")}</th>
                      <th>{label(lang, "Trạng thái", "Status")}</th>
                      <th>{label(lang, "Thao tác", "Actions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result?.items.map((row) => (
                      <React.Fragment key={row.id}>
                        <tr>
                          <td>
                            <button
                              className="booking-code text-link"
                              onClick={() =>
                                setExpanded(expanded === row.id ? "" : row.id)
                              }
                            >
                              {row.code}
                            </button>
                            <strong>{row.contact_name}</strong>
                            <span>{row.phone}</span>
                          </td>
                          <td>
                            <strong>{row.property_name}</strong>
                            <span>
                              {row.room_name} · {row.guests}{" "}
                              {label(lang, "khách", "guests")}
                            </span>
                          </td>
                          <td>
                            <strong>{formatDate(row.check_in, lang)}</strong>
                            <span>
                              {formatDate(row.check_out, lang)} · {row.nights}{" "}
                              {label(lang, "đêm", "nights")}
                            </span>
                          </td>
                          <td>
                            <strong>
                              {money(row.total_price, row.currency, lang)}
                            </strong>
                            <span>
                              {label(
                                lang,
                                "Thanh toán với khách sạn",
                                "Pay at property",
                              )}
                            </span>
                          </td>
                          <td>
                            <StatusBadge status={row.status} />
                          </td>
                          <td>
                            <div className="admin-row-actions">
                              <button
                                onClick={() =>
                                  setExpanded(expanded === row.id ? "" : row.id)
                                }
                                className="button button-outline button-small"
                              >
                                {label(lang, "Chi tiết", "Details")}
                              </button>
                              {canEdit && row.status === "pending" && (
                                <button
                                  className="button button-blue button-small"
                                  disabled={changing === row.id}
                                  onClick={() => change(row, "confirmed")}
                                >
                                  {changing === row.id ? (
                                    <Spinner />
                                  ) : (
                                    label(lang, "Xác nhận", "Confirm")
                                  )}
                                </button>
                              )}
                              {canEdit &&
                                ["pending", "confirmed"].includes(
                                  row.status,
                                ) && (
                                  <button
                                    className="text-danger"
                                    disabled={!!changing}
                                    onClick={() => {
                                      setExpanded(row.id);
                                      setConfirmCancel(row.id);
                                    }}
                                  >
                                    {label(lang, "Hủy đơn", "Cancel")}
                                  </button>
                                )}
                              {canEdit &&
                                row.status === "confirmed" &&
                                row.check_out <=
                                  new Date().toLocaleDateString("en-CA", {
                                    timeZone: "Asia/Ho_Chi_Minh",
                                  }) && (
                                  <button
                                    className="button button-outline button-small"
                                    onClick={() => change(row, "completed")}
                                  >
                                    {label(lang, "Hoàn thành", "Complete")}
                                  </button>
                                )}
                            </div>
                          </td>
                        </tr>
                        {expanded === row.id && (
                          <tr className="admin-expanded">
                            <td colSpan="6">
                              <ReservationDetails booking={row} lang={lang} />
                              <div className="admin-contact-details">
                                <p>
                                  <b>Email:</b> {row.email}
                                </p>
                                <p>
                                  <b>{label(lang, "Điện thoại:", "Phone:")}</b>{" "}
                                  {row.phone}
                                </p>
                                <p>
                                  <b>{label(lang, "Ghi chú:", "Notes:")}</b>{" "}
                                  {row.notes || "—"}
                                </p>
                              </div>
                              {confirmCancel === row.id && (
                                <div className="cancel-confirm">
                                  <p>
                                    {label(
                                      lang,
                                      "Hủy đơn và mở lại số phòng đã giữ?",
                                      "Cancel this booking and release the reserved room?",
                                    )}
                                  </p>
                                  <button
                                    className="button button-danger"
                                    disabled={!!changing}
                                    onClick={() => change(row, "cancelled")}
                                  >
                                    {changing === row.id ? (
                                      <Spinner />
                                    ) : (
                                      label(
                                        lang,
                                        "Xác nhận hủy",
                                        "Confirm cancellation",
                                      )
                                    )}
                                  </button>
                                  <button
                                    className="button button-outline"
                                    onClick={() => setConfirmCancel("")}
                                  >
                                    {label(lang, "Quay lại", "Go back")}
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
              {!result && busy && (
                <div className="reservation-empty">
                  <Spinner />
                  <p>
                    {label(
                      lang,
                      "Đang tải đơn từ backend…",
                      "Loading reservations…",
                    )}
                  </p>
                </div>
              )}
              {result && !result.items.length && (
                <div className="reservation-empty">
                  <CalendarDays size={36} />
                  <h3>
                    {label(
                      lang,
                      "Chưa có đơn phù hợp",
                      "No matching reservations",
                    )}
                  </h3>
                  <p>
                    {label(
                      lang,
                      "Đơn mới của khách sẽ tự xuất hiện tại đây.",
                      "New guest reservations will appear here automatically.",
                    )}
                  </p>
                  {canCreate && !filters.search && !filters.status && (
                    <button
                      className="button button-outline"
                      onClick={() => setTab("properties")}
                    >
                      {label(
                        lang,
                        "Thêm khách sạn và phòng để test",
                        "Add a property and room to test",
                      )}
                      <ArrowRight size={16} />
                    </button>
                  )}
                </div>
              )}
              <div className="admin-pagination">
                <span>
                  {result?.total ?? 0} {label(lang, "đơn", "reservations")}
                </span>
                <div>
                  <button
                    className="icon-button"
                    aria-label="Previous page"
                    disabled={filters.page <= 1 || busy}
                    onClick={() =>
                      setFilters((f) => ({ ...f, page: f.page - 1 }))
                    }
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <span>
                    {label(lang, "Trang", "Page")} {filters.page}
                  </span>
                  <button
                    className="icon-button"
                    aria-label="Next page"
                    disabled={
                      !result || filters.page * 20 >= result.total || busy
                    }
                    onClick={() =>
                      setFilters((f) => ({ ...f, page: f.page + 1 }))
                    }
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
