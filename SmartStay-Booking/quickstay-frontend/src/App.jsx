import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  Search,
  CalendarDays,
  Users,
  MapPin,
  ArrowRight,
  ArrowLeft,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Star,
  Heart,
  Menu,
  X,
  Wifi,
  Coffee,
  ConciergeBell,
  Mountain,
  Waves,
  Home as HomeIcon,
  ShieldCheck,
  Globe2,
  Check,
  SlidersHorizontal,
  Server,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Headphones,
  BedDouble,
  LogOut,
  Mail,
  Instagram,
  Facebook,
  Twitter,
  Linkedin,
  ExternalLink,
} from "lucide-react";
import { createClient, mediaUrl, normalizeBase } from "./api.mjs";
import AudioGuide from "./AudioGuide.jsx";
import { fold, money, readStorage, writeStorage, mapUrl } from "./model.mjs";
import { demoStays, offers, reviews, sampleBookings } from "./demo.mjs";
import { copy } from "./i18n.mjs";
import { Context, useApp } from "./context.jsx";
import { createBookingClient } from "./booking-api.mjs";
import {
  AdminDashboard,
  Checkout,
  CustomerBookings,
} from "./BookingFeatures.jsx";
import SmartStayControlCenter from "./SmartStayControlCenter.jsx";

const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
const currency = (poi) =>
  poi?.menu_items?.find(
    (r) => r.kind === "room_type" && r.is_available !== false,
  );
const price = (poi) => {
  const r = currency(poi);
  return r && Number.isFinite(Number(r.price)) ? Number(r.price) : null;
};
const displayPrice = (poi, language = "en") =>
  price(poi) == null
    ? language === "vi"
      ? "Liên hệ"
      : "On request"
    : money(price(poi), currency(poi).currency, language).replace(".00", "");
const roomTypes = ["Single Bed", "Double Bed", "Luxury Room", "Family Suite"];
const amenityIcons = {
  "Free WiFi": Wifi,
  "Free Wifi": Wifi,
  "Free Breakfast": Coffee,
  "Room Service": ConciergeBell,
  "Mountain View": Mountain,
  "Pool Access": Waves,
};
const localizedDemo = (poi, lang) => ({
  ...poi,
  language: lang,
  resolved_lang: lang,
  description:
    lang === "vi"
      ? "Khám phá không gian nghỉ ngơi nơi thiết kế tinh tế hòa cùng sự thoải mái. Thức dậy với khung cảnh tuyệt đẹp, thư giãn trong căn phòng được chăm chút và tận hưởng cảm giác thân thuộc như ở nhà. Từ ly cà phê buổi sáng đến buổi chiều bên hồ bơi, từng chi tiết đều dành cho kỳ nghỉ của bạn."
      : lang === "ja"
        ? "美しい景色と快適なお部屋で、ゆったりとした時間をお過ごしください。朝のコーヒーからプールサイドでのひとときまで、思い出に残る滞在をお楽しみいただけます。"
        : lang === "ko"
          ? "아름다운 전망과 편안한 객실에서 여유로운 시간을 즐겨 보세요. 아침 커피부터 수영장에서의 휴식까지, 특별한 숙박 경험을 선사합니다."
          : lang === "zh"
            ? "在精心设计的舒适客房中放松身心，欣赏美丽的景色。从清晨的咖啡到泳池边的悠闲时光，每个细节都让您享受难忘的住宿体验。"
            : poi.description,
  check_in_instructions:
    lang === "vi"
      ? "Nhận phòng từ 14:00. Vui lòng mang giấy tờ tùy thân và xác nhận đặt phòng. Quầy lễ tân phục vụ 24/7."
      : poi.check_in_instructions,
});

function useRoute() {
  const [route, setRoute] = useState(
    () => window.location.hash.slice(1) || "/",
  );
  useEffect(() => {
    const change = () => {
      setRoute(window.location.hash.slice(1) || "/");
      window.scrollTo({ top: 0, behavior: "instant" });
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  return route;
}
function Modal({ title, children, onClose, wide = false }) {
  const root = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement,
      overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    root.current?.focus();
    const handler = (e) => {
      if (
        [...document.querySelectorAll('[role="dialog"]')].at(-1) !==
        root.current
      )
        return;
      if (e.key === "Escape") closeRef.current();
      if (e.key === "Tab") {
        const nodes = [
          ...root.current.querySelectorAll(
            'button:not(:disabled),input:not(:disabled),select:not(:disabled),a[href],textarea,[tabindex="0"]',
          ),
        ].filter((x) => x.getClientRects().length);
        if (!nodes.length) {
          e.preventDefault();
          return;
        }
        if (
          e.shiftKey &&
          (document.activeElement === nodes[0] ||
            document.activeElement === root.current)
        ) {
          e.preventDefault();
          nodes.at(-1).focus();
        } else if (
          !e.shiftKey &&
          (document.activeElement === nodes.at(-1) ||
            document.activeElement === root.current)
        ) {
          e.preventDefault();
          nodes[0].focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", handler);
      previous?.focus?.();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        ref={root}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={"modal " + (wide ? "modal-wide" : "")}
      >
        <div className="modal-heading">
          <h2>{title}</h2>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={21} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}
function Photo({ src, alt, className = "", ...rest }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  return !src || failed ? (
    <div
      className={"photo-placeholder " + className}
      role="img"
      aria-label={alt + " · photo unavailable"}
    >
      <BedDouble size={28} />
      <span>Photo unavailable</span>
    </div>
  ) : (
    <img
      className={className}
      src={src}
      alt={alt}
      onError={() => setFailed(true)}
      {...rest}
    />
  );
}
function Stars({ count = 5 }) {
  return (
    <span className="stars" aria-label={count + " out of 5 stars"}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          size={14}
          strokeWidth={1.5}
          fill={i < count ? "currentColor" : "none"}
        />
      ))}
    </span>
  );
}
function Amenities({ poi, detailed = false }) {
  const values = currency(poi)?.amenities || [];
  return (
    <div className={"amenities " + (detailed ? "amenities-detailed" : "")}>
      {values.slice(0, detailed ? 12 : 4).map((item) => {
        const Icon = amenityIcons[item] || Check;
        return (
          <span key={item}>
            <Icon size={detailed ? 20 : 14} />
            {item}
          </span>
        );
      })}
    </div>
  );
}
function Header() {
  const {
    t,
    lang,
    setLang,
    route,
    navigate,
    scrollSection,
    favorites,
    setSavedOnly,
    setSettingsOpen,
    session,
    setAuthOpen,
    signOut,
  } = useApp();
  const [scrolled, setScrolled] = useState(window.scrollY > 50),
    [mobile, setMobile] = useState(false);
  useEffect(() => {
    const change = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", change, { passive: true });
    return () => window.removeEventListener("scroll", change);
  }, []);
  useEffect(() => {
    setMobile(false);
  }, [route]);
  const isHome = route === "/",
    light = !isHome || scrolled;
  return (
    <header className={"header " + (light ? "header-light" : "header-hero")}>
      <div className="nav-wrap">
        <a href="#/" className="brand" aria-label="QuickStay home">
          <img src="/assets/logo.svg" alt="QuickStay" />
        </a>
        <nav
          className={"nav-links " + (mobile ? "nav-open" : "")}
          aria-label="Main navigation"
        >
          <a href="#/" className={isHome ? "active" : ""}>
            {t.home}
          </a>
          <a
            href="#/rooms"
            className={route.startsWith("/rooms") ? "active" : ""}
            onClick={() => setSavedOnly(false)}
          >
            {t.hotels}
          </a>
          <button
            onClick={() => {
              scrollSection("experience");
              setMobile(false);
            }}
          >
            {t.experience}
          </button>
          <button
            onClick={() => {
              scrollSection("about");
              setMobile(false);
            }}
          >
            {t.about}
          </button>
          <a
            href="#/bookings"
            className={
              "bookings-link " + (route === "/bookings" ? "active" : "")
            }
          >
            {t.bookings}
          </a>
        </nav>
        <div className="nav-actions">
          <a
            href={route === "/control" ? "#/rooms" : "#/control"}
            className={"header-control-toggle " + (route === "/control" ? "to-classic" : "to-control")}
            title={lang === "en" ? "Toggle interface" : "Chuyển đổi giao diện"}
          >
            {route === "/control" ? (lang === "en" ? "Hotels" : "Đặt phòng") : (lang === "en" ? "SmartStay Control" : "Điều khiển")}
          </a>
          <button
            className="icon-button search-shortcut"
            aria-label="Search hotels"
            onClick={() => {
              setSavedOnly(false);
              navigate("/rooms");
            }}
          >
            <Search size={20} />
          </button>
          <button
            className="icon-button favorite-shortcut"
            aria-label={t.saved}
            onClick={() => {
              setSavedOnly(true);
              navigate("/rooms");
            }}
          >
            <Heart
              size={19}
              fill={favorites.length ? "currentColor" : "none"}
            />
          </button>
          <button
            className="language-switch"
            onClick={() => setLang(lang === "en" ? "vi" : "en")}
            aria-label="Switch language"
          >
            <Globe2 size={16} />
            <span>{lang.toUpperCase()}</span>
          </button>
          {session ? (
            <button className="login-button" onClick={signOut} title={t.logout}>
              <LogOut size={15} />
              {session.user.full_name.split(" ")[0]}
            </button>
          ) : (
            <button className="login-button" onClick={() => setAuthOpen(true)}>
              {t.login}
            </button>
          )}
          <button
            className="icon-button mobile-toggle"
            aria-label={mobile ? "Close menu" : "Open menu"}
            aria-expanded={mobile}
            onClick={() => setMobile(!mobile)}
          >
            {mobile ? <X /> : <Menu />}
          </button>
        </div>
      </div>
    </header>
  );
}
function SearchForm({ compact = false, onSubmit }) {
  const { t, search, setSearch, toast } = useApp();
  const change = (e) =>
    setSearch((s) => ({ ...s, [e.target.name]: e.target.value }));
  function submit(e) {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    if (fields.checkIn && fields.checkOut && fields.checkOut <= fields.checkIn)
      return toast("Check-out must be after check-in.");
    setSearch(fields);
    onSubmit();
  }
  return (
    <form
      onSubmit={submit}
      className={"search-form " + (compact ? "search-compact" : "")}
    >
      <label className="destination-field">
        <span>
          <MapPin size={16} />
          {t.destination}
        </span>
        <input
          name="destination"
          placeholder={t.where}
          value={search.destination}
          onChange={change}
          autoComplete="off"
          list="destinations"
        />
        <datalist id="destinations">
          {[
            "New York",
            "London",
            "Dubai",
            "Singapore",
            "Đà Lạt",
            "Đà Nẵng",
            "Hồ Chí Minh",
          ].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </datalist>
      </label>
      <label>
        <span>
          <CalendarDays size={16} />
          {t.checkIn}
        </span>
        <input
          type="date"
          name="checkIn"
          min={today()}
          value={search.checkIn}
          onChange={change}
        />
      </label>
      <label>
        <span>
          <CalendarDays size={16} />
          {t.checkOut}
        </span>
        <input
          type="date"
          name="checkOut"
          min={search.checkIn || today()}
          value={search.checkOut}
          onChange={change}
        />
      </label>
      <label className="guest-field">
        <span>
          <Users size={16} />
          {t.guests}
        </span>
        <input
          type="number"
          name="guests"
          min="1"
          max="20"
          value={search.guests}
          onChange={change}
          required
        />
      </label>
      <button type="submit" className="button button-dark">
        <Search size={18} />
        {t.search}
      </button>
    </form>
  );
}
function RoomCard({ poi, index }) {
  const { t, lang, navigate, favorites, toggleFavorite, imageFor } = useApp();
  return (
    <article className="room-card">
      <div className="room-card-photo">
        <button
          className="image-link"
          onClick={() => navigate("/rooms/" + poi.id)}
          aria-label={"View " + poi.name}
        >
          <Photo
            src={imageFor(poi, 0)}
            alt={poi.name + " room"}
            loading="lazy"
          />
        </button>
        {index < 2 && poi.sample && (
          <span className="best-badge">Best Seller</span>
        )}
        <button
          className={
            "save-button " + (favorites.includes(poi.id) ? "is-saved" : "")
          }
          aria-label={
            favorites.includes(poi.id) ? "Remove from saved stays" : "Save stay"
          }
          onClick={() => toggleFavorite(poi.id)}
        >
          <Heart
            size={17}
            fill={favorites.includes(poi.id) ? "currentColor" : "none"}
          />
        </button>
      </div>
      <div className="room-card-body">
        <div className="card-title-line">
          <button
            className="text-link"
            onClick={() => navigate("/rooms/" + poi.id)}
          >
            <h3>{poi.name}</h3>
          </button>
          {poi.sample ? (
            <span className="rating">
              <Star size={14} fill="currentColor" />
              {poi.rating}
            </span>
          ) : (
            <span className="category-label">{poi.category}</span>
          )}
        </div>
        <p className="address">
          <MapPin size={14} />
          {poi.address}
        </p>
        <div className="card-bottom">
          <p className="card-price">
            {displayPrice(poi, lang)} <span>{t.perNight}</span>
          </p>
          <button
            className="button button-outline"
            onClick={() => navigate("/rooms/" + poi.id)}
          >
            {t.bookNow}
          </button>
        </div>
      </div>
    </article>
  );
}
function ContentState({ children }) {
  const { status, error, t, load, setSettingsOpen } = useApp();
  if (status === "loading")
    return (
      <div className="content-state">
        <Loader2 className="spin" />
        <p>{t.loading}</p>
      </div>
    );
  if (error)
    return (
      <div className="content-state error-state">
        <AlertCircle />
        <h3>We couldn't load your stays</h3>
        <p>{error}</p>
        <div className="button-row">
          <button className="button button-dark" onClick={() => load()}>
            {t.retry}
          </button>
          <button
            className="button button-outline"
            onClick={() => setSettingsOpen(true)}
          >
            {t.connect}
          </button>
        </div>
      </div>
    );
  return children;
}
function HomeLocationMap() {
  const { data, navigate, lang } = useApp();
  // Vị trí mặc định Sài Gòn (TP. Hồ Chí Minh)
  const [userLat, setUserLat] = useState(10.7769);
  const [userLng, setUserLng] = useState(106.7009);
  const [gpsActive, setGpsActive] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [mapKey, setMapKey] = useState(0);
  const [locMsg, setLocMsg] = useState(
    lang === "en"
      ? "Location: Ho Chi Minh City (Saigon) - 10.7769, 106.7009"
      : "Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - 10.7769, 106.7009"
  );
  const [selectedStay, setSelectedStay] = useState(null);

  useEffect(() => {
    setLocMsg(
      lang === "en"
        ? `Location: Ho Chi Minh City (Saigon) - ${userLat.toFixed(4)}, ${userLng.toFixed(4)}`
        : `Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - ${userLat.toFixed(4)}, ${userLng.toFixed(4)}`
    );
  }, [lang, userLat, userLng]);

  const calcDist = (lat1, lon1, lat2, lon2) => {
    if (!lat1 || !lon1 || !lat2 || !lon2) return 999999;
    const R = 6371e3;
    const phi1 = (lat1 * Math.PI) / 180;
    const phi2 = (lat2 * Math.PI) / 180;
    const deltaPhi = ((lat2 - lat1) * Math.PI) / 180;
    const deltaLambda = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
      Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return Math.round(R * c);
  };

  const getLiveLocation = () => {
    setShowMap(true);
    const saigonLat = 10.7769;
    const saigonLng = 106.7009;

    if (!navigator.geolocation) {
      setUserLat(saigonLat);
      setUserLng(saigonLng);
      setGpsActive(true);
      setMapKey((k) => k + 1);
      setLocMsg(
        lang === "en"
          ? "Location: Ho Chi Minh City (Saigon) - 10.7769, 106.7009"
          : "Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - 10.7769, 106.7009"
      );
      return;
    }

    setLocMsg(lang === "en" ? "Scanning GPS satellite location in Saigon..." : "Đang quét vị trí vệ tinh GPS tại Sài Gòn...");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        setUserLat(lat);
        setUserLng(lng);
        setGpsActive(true);
        setMapKey((k) => k + 1);
        setLocMsg(
          lang === "en"
            ? `Your exact location: ${lat.toFixed(4)}, ${lng.toFixed(4)} (Saigon)`
            : `Đã xác định đúng vị trí bạn đang đứng: ${lat.toFixed(4)}, ${lng.toFixed(4)} (Sài Gòn)`
        );
      },
      (err) => {
        setUserLat(saigonLat);
        setUserLng(saigonLng);
        setGpsActive(true);
        setMapKey((k) => k + 1);
        setLocMsg(
          lang === "en"
            ? "Your location: Ho Chi Minh City (Saigon) - 10.7769, 106.7009"
            : "Vị trí của bạn: TP. Hồ Chí Minh (Sài Gòn) - 10.7769, 106.7009"
        );
      },
      { enableHighAccuracy: true, timeout: 3000, maximumAge: 0 }
    );
  };

  const staysWithDistance = useMemo(() => {
    return (data || [])
      .map((s) => ({
        ...s,
        dist: calcDist(userLat, userLng, Number(s.latitude), Number(s.longitude)),
      }))
      .sort((a, b) => a.dist - b.dist);
  }, [data, userLat, userLng]);

  const activeTarget = selectedStay || staysWithDistance[0];

  return (
    <section className="container" style={{ margin: "36px auto 16px", padding: "0 20px" }}>
      <div style={{ background: "#ffffff", border: "1px solid #e5e7eb", borderRadius: "14px", padding: "24px", boxShadow: "0 2px 10px rgba(0,0,0,0.04)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: showMap ? "16px" : 0, borderBottom: showMap ? "1px solid #f3f4f6" : "none", paddingBottom: showMap ? "14px" : 0 }}>
          <div>
            <h2 style={{ fontSize: "20px", fontWeight: "700", margin: "0 0 4px", color: "#111827", fontFamily: "inherit" }}>
              {lang === "en"
                ? "Live Location Map & Nearest Properties"
                : "Bản Đồ Định Vị Vị Trí Của Bạn & Các Nơi Lưu Trú Gần Nhất"}
            </h2>
            <p style={{ margin: 0, fontSize: "14px", color: "#6b7280" }}>
              {lang === "en"
                ? "Locate exactly where you are in Saigon and get direct directions to hotels & homestays."
                : "Xác định bạn đang đứng ở đâu tại Sài Gòn và chỉ đường trực tiếp đến khách sạn / homestay."}
            </p>
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button
              onClick={getLiveLocation}
              style={{
                background: "#2563eb",
                color: "#ffffff",
                padding: "9px 18px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: "600",
                cursor: "pointer",
                border: "none",
              }}
            >
              {showMap
                ? (lang === "en" ? "Update GPS Location" : "Cập nhật vị trí GPS")
                : (lang === "en" ? "Get My Current GPS Location" : "Lấy vị trí GPS hiện tại của tôi")}
            </button>
            {showMap && (
              <button
                onClick={() => setShowMap(false)}
                style={{
                  background: "#f3f4f6",
                  color: "#374151",
                  padding: "9px 14px",
                  borderRadius: "8px",
                  fontSize: "13px",
                  fontWeight: "600",
                  cursor: "pointer",
                  border: "1px solid #d1d5db",
                }}
              >
                {lang === "en" ? "Hide Map" : "Đóng bản đồ"}
              </button>
            )}
          </div>
        </div>

        {showMap && (
          <>
            <div style={{ background: "#eff6ff", borderLeft: "4px solid #2563eb", padding: "10px 16px", borderRadius: "0 6px 6px 0", fontSize: "13px", color: "#1e40af", marginBottom: "18px", marginTop: "14px" }}>
              <b>{lang === "en" ? "Status:" : "Trạng thái:"}</b> {locMsg}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "20px" }}>
              {/* Iframe Bản đồ Google Maps ghim đúng vị trí tọa độ */}
              <div style={{ borderRadius: "10px", overflow: "hidden", border: "1px solid #d1d5db", minHeight: "380px", background: "#f3f4f6" }}>
                <iframe
                  key={mapKey}
                  title={lang === "en" ? "Map of your current location" : "Bản đồ vị trí của bạn"}
                  src={`https://maps.google.com/maps?q=${userLat},${userLng}&hl=${lang}&z=16&output=embed`}
                  style={{ width: "100%", height: "100%", minHeight: "380px", border: 0 }}
                  loading="lazy"
                />
              </div>

              {/* Danh sách khách sạn lân cận */}
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div style={{ fontSize: "14px", fontWeight: "700", color: "#111827" }}>
                  {lang === "en"
                    ? `Nearest properties by distance (${staysWithDistance.length} places):`
                    : `Khách sạn lân cận theo khoảng cách (${staysWithDistance.length} cơ sở):`}
                </div>

                <div style={{ maxHeight: "300px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "10px", paddingRight: "4px" }}>
                  {staysWithDistance.slice(0, 5).map((stay) => {
                    const isSelected = activeTarget?.id === stay.id;
                    const inGeofence = stay.dist <= 30;
                    return (
                      <div
                        key={stay.id}
                        onClick={() => setSelectedStay(stay)}
                        style={{
                          padding: "12px 14px",
                          border: isSelected ? "2px solid #2563eb" : "1px solid #e5e7eb",
                          borderRadius: "8px",
                          background: isSelected ? "#f8fafc" : "#ffffff",
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "8px" }}>
                          <div>
                            <h4 style={{ margin: "0 0 3px", fontSize: "15px", fontWeight: "700", color: "#111827" }}>
                              {stay.name}
                            </h4>
                            <p style={{ margin: 0, fontSize: "12px", color: "#6b7280" }}>{stay.address}</p>
                          </div>
                          <span style={{ fontSize: "13px", fontWeight: "700", color: "#2563eb", whiteSpace: "nowrap" }}>
                            {stay.dist < 1000 ? `${stay.dist} m` : `${(stay.dist / 1000).toFixed(1)} km`}
                          </span>
                        </div>

                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "8px" }}>
                          {inGeofence ? (
                            <span style={{ fontSize: "11px", fontWeight: "600", color: "#059669", background: "#ecfdf5", padding: "2px 8px", borderRadius: "4px" }}>
                              {lang === "en" ? "Inside perimeter (30m)" : "Đã trong khuôn viên (30m)"}
                            </span>
                          ) : (
                            <span style={{ fontSize: "11px", color: "#6b7280" }}>
                              {lang === "en" ? `${stay.dist - 30}m from Geofence` : `Cách Geofence ${stay.dist - 30}m`}
                            </span>
                          )}

                          <a
                            href={`https://www.google.com/maps/dir/?api=1&origin=${userLat},${userLng}&destination=${stay.latitude},${stay.longitude}`}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            style={{
                              fontSize: "12px",
                              fontWeight: "600",
                              color: "#2563eb",
                              textDecoration: "underline",
                            }}
                          >
                            {lang === "en" ? "Google Maps Directions" : "Chỉ đường Google Maps"}
                          </a>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {activeTarget && (
                  <div style={{ background: "#f8fafc", padding: "14px", borderRadius: "8px", border: "1px solid #e5e7eb", marginTop: "auto", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                    <div>
                      <span style={{ fontSize: "13px", color: "#374151" }}>
                        {lang === "en" ? "Selected property: " : "Khách sạn đang chọn: "}<b>{activeTarget.name}</b>
                      </span>
                      <div style={{ fontSize: "12px", color: "#6b7280" }}>
                        {lang === "en" ? "Distance: " : "Khoảng cách: "}<b>{activeTarget.dist < 1000 ? `${activeTarget.dist} m` : `${(activeTarget.dist / 1000).toFixed(1)} km`}</b>
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "6px" }}>
                      <button
                        onClick={() => navigate("/rooms/" + activeTarget.id)}
                        style={{ background: "#ffffff", border: "1px solid #d1d5db", padding: "7px 12px", borderRadius: "6px", fontSize: "12px", fontWeight: "600", cursor: "pointer" }}
                      >
                        {lang === "en" ? "View Room Details" : "Xem Chi Tiết Phòng"}
                      </button>
                      <button
                        onClick={() => navigate("/control")}
                        style={{ background: "#2563eb", color: "#ffffff", border: "none", padding: "7px 14px", borderRadius: "6px", fontSize: "12px", fontWeight: "600", cursor: "pointer" }}
                      >
                        {lang === "en" ? "Listen to Audio Directions" : "Nghe Thuyết Minh Dẫn Đường"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function HomePage() {
  const {
    t,
    lang,
    data,
    navigate,
    setSavedOnly,
    setOffer,
    showInfo,
    connection,
    toast,
    setSettingsOpen,
  } = useApp();
  const [email, setEmail] = useState("");
  return (
    <>
      <section className="hero">
        <div className="hero-shade" />
        <div className="container hero-content">
          <span className="hero-eyebrow">{t.ultimate}</span>
          <h1>{t.hero}</h1>
          <p>{t.heroSub}</p>
          <SearchForm
            onSubmit={() => {
              setSavedOnly(false);
              navigate("/rooms");
            }}
          />
        </div>
        <span className="hero-location">
          <MapPin size={13} /> A little closer to your perfect escape
        </span>
      </section>

      {/* Bản Đồ Vị Trí Của Bạn & Khách Sạn Lân Cận */}
      <HomeLocationMap />
      <section className="featured-section" id="hotels">
        <div className="container">
          <div className="section-heading centered">
            <span className="eyebrow">STAY SOMEWHERE SPECIAL</span>
            <h2>{t.featured}</h2>
            <p>{t.featuredSub}</p>
          </div>
          <ContentState>
            <div className="room-grid">
              {data.slice(0, 4).map((poi, i) => (
                <RoomCard key={poi.id} poi={poi} index={i} />
              ))}
            </div>
            {!data.length && <p className="empty-copy">{t.empty}</p>}
          </ContentState>
          <div className="center">
            <button
              className="button button-outline view-all"
              onClick={() => {
                setSavedOnly(false);
                navigate("/rooms");
              }}
            >
              {t.viewAll}
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </section>
      <section className="offers-section container" id="experience">
        <div className="section-heading heading-row">
          <div>
            <h2>{t.offers}</h2>
            <p>{t.offersSub}</p>
          </div>
          <button
            className="text-arrow"
            onClick={() => setOffer({ all: true })}
          >
            {t.allOffers}
            <ArrowRight size={18} />
          </button>
        </div>
        <div className="offer-grid">
          {offers.map((offer) => (
            <article
              className="offer-card"
              key={offer.id}
              style={{ backgroundImage: `url(${offer.image})` }}
            >
              <div className="offer-shade" />
              <span className="discount">{offer.discount}% OFF</span>
              <div className="offer-content">
                <h3>{offer.title}</h3>
                <p>{offer.description}</p>
                <small>Expires {offer.expiry} · Sample offer</small>
                <button onClick={() => setOffer(offer)}>
                  {t.viewOffer}
                  <ArrowRight size={16} />
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="testimonials-section">
        <div className="container">
          <div className="section-heading centered">
            <h2>{t.testimonials}</h2>
            <p>{t.testimonialsSub}</p>
          </div>
          <div className="review-grid">
            {reviews.map((r, i) => (
              <article className="review-card" key={r.name}>
                <div className="review-person">
                  <img src={r.image} alt="" loading="lazy" />
                  <div>
                    <h3>{r.name}</h3>
                    <p>{r.location}</p>
                  </div>
                </div>
                <Stars count={i === 1 ? 4 : 5} />
                <blockquote>“{r.text}”</blockquote>
              </article>
            ))}
          </div>
          <p className="sample-caption">
            {lang === "vi"
              ? "Các đánh giá minh họa từ bản thiết kế QuickStay."
              : "Sample reviews from the QuickStay design."}
          </p>
        </div>
      </section>
      <section className="newsletter-section container">
        <div className="newsletter">
          <span className="eyebrow">YOUR NEXT CHAPTER AWAITS</span>
          <h2>{t.inspired}</h2>
          <p>{t.inspiredSub}</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              toast(
                lang === "vi"
                  ? "Bản xem thử chưa kết nối dịch vụ gửi bản tin. Email của bạn chưa được gửi đi."
                  : "Newsletter signup isn't connected in this preview. Your email has not been submitted.",
              );
            }}
          >
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t.email}
              aria-label={t.email}
              required
            />
            <button type="submit">
              {t.subscribe}
              <ArrowRight size={17} />
            </button>
          </form>
          <small>Preview only. Newsletter delivery is not connected.</small>
        </div>
      </section>
    </>
  );
}
function RoomsPage() {
  const {
    t,
    lang,
    data,
    search,
    setSearch,
    favorites,
    savedOnly,
    setSavedOnly,
    navigate,
    toggleFavorite,
    imageFor,
    connection,
  } = useApp();
  const [types, setTypes] = useState([]),
    [budget, setBudget] = useState("all"),
    [sort, setSort] = useState("recommended"),
    [filterOpen, setFilterOpen] = useState(false);
  const isDemo = connection.mode === "demo";
  const filtered = useMemo(() => {
    let list = data.filter(
      (p) =>
        (!search.destination ||
          fold(p.name + " " + p.address + " " + (p.city || "")).includes(
            fold(search.destination),
          )) &&
        (!savedOnly || favorites.includes(p.id)) &&
        (!types.length ||
          types.some((x) =>
            p.sample ? p.roomType === x : p.category === x,
          )) &&
        (!Number(search.guests) ||
          (p.menu_items || []).some(
            (r) =>
              r.kind === "room_type" &&
              r.is_available !== false &&
              Number(r.capacity) >= Number(search.guests),
          ) ||
          !p.menu_items?.length),
    );
    if (budget !== "all")
      list = list.filter((p) => {
        const n = price(p);
        return (
          n != null &&
          (budget === "low"
            ? n < 200
            : budget === "mid"
              ? n >= 200 && n <= 350
              : n > 350)
        );
      });
    if (sort !== "recommended")
      list = [...list].sort((a, b) => {
        const ca = currency(a)?.currency || "",
          cb = currency(b)?.currency || "";
        if (ca !== cb) return ca.localeCompare(cb);
        const ap = price(a),
          bp = price(b);
        return ap == null
          ? 1
          : bp == null
            ? -1
            : sort === "low"
              ? ap - bp
              : bp - ap;
      });
    return list;
  }, [data, search, types, budget, sort, savedOnly, favorites]);
  const reset = () => {
    setTypes([]);
    setBudget("all");
    setSort("recommended");
    setSavedOnly(false);
    setSearch((s) => ({ ...s, destination: "", guests: "2" }));
  };
  const categories = isDemo
    ? roomTypes
    : [...new Set(data.map((p) => p.category))];
  return (
    <main className="container inner-page rooms-page">
      <div className="page-heading">
        <h1>{savedOnly ? t.saved : t.hotelsTitle}</h1>
        <p>{t.hotelSub}</p>
      </div>
      <div className="listing-search">
        <label>
          <Search size={17} />
          <input
            aria-label="Search destination"
            placeholder={t.where + "…"}
            value={search.destination}
            onChange={(e) =>
              setSearch((s) => ({ ...s, destination: e.target.value }))
            }
          />
        </label>
        <span>
          {filtered.length} {lang === "vi" ? "kết quả" : "stays found"}
        </span>
        <button
          className="filter-toggle button button-outline"
          onClick={() => setFilterOpen(!filterOpen)}
        >
          <SlidersHorizontal size={16} />
          {t.filters}
        </button>
      </div>
      <div className="listing-layout">
        <div className="room-list">
          <ContentState>
            {filtered.map((poi) => (
              <article className="room-list-row" key={poi.id}>
                <button
                  className="list-photo"
                  onClick={() => navigate("/rooms/" + poi.id)}
                  aria-label={"View " + poi.name}
                >
                  <Photo src={imageFor(poi, 0)} alt={poi.name} loading="lazy" />
                </button>
                <div className="list-room-content">
                  <span className="city-label">{poi.city || poi.category}</span>
                  <button
                    className="text-link"
                    onClick={() => navigate("/rooms/" + poi.id)}
                  >
                    <h2>{poi.name}</h2>
                  </button>
                  {poi.sample ? (
                    <div className="list-reviews">
                      <Stars />
                      <span>200+ reviews</span>
                    </div>
                  ) : (
                    <small>{currency(poi)?.name || t.rooms}</small>
                  )}
                  <p className="address">
                    <MapPin size={15} />
                    {poi.address}
                  </p>
                  <Amenities poi={poi} />
                  <div className="list-price-row">
                    <p className="list-price">
                      {displayPrice(poi, lang)} <span>{t.perNight}</span>
                    </p>
                    <button
                      className="text-arrow"
                      onClick={() => navigate("/rooms/" + poi.id)}
                    >
                      {t.details}
                      <ArrowRight size={15} />
                    </button>
                  </div>
                </div>
                <button
                  className={
                    "list-save icon-button " +
                    (favorites.includes(poi.id) ? "is-saved" : "")
                  }
                  onClick={() => toggleFavorite(poi.id)}
                  aria-label={
                    favorites.includes(poi.id)
                      ? "Remove from saved stays"
                      : "Save stay"
                  }
                >
                  <Heart
                    size={19}
                    fill={favorites.includes(poi.id) ? "currentColor" : "none"}
                  />
                </button>
              </article>
            ))}
            {!filtered.length && (
              <div className="content-state">
                <BedDouble size={34} />
                <h3>{t.empty}</h3>
                <p>{t.emptySub}</p>
                <button className="button button-outline" onClick={reset}>
                  {t.clear}
                </button>
              </div>
            )}
          </ContentState>
          {filtered.length > 0 && (
            <div className="pagination">
              <span>1</span>
              <small>
                {filtered.length} {lang === "vi" ? "nơi lưu trú" : "stays"}
              </small>
            </div>
          )}
        </div>
        <aside
          className={"filter-panel " + (filterOpen ? "filter-panel-open" : "")}
        >
          <div className="filter-heading">
            <span>{t.filters}</span>
            <button onClick={reset}>{t.clear}</button>
          </div>
          <div className="filter-body">
            <h3>{t.popular}</h3>
            {categories.map((type) => (
              <label className="checkbox-row" key={type}>
                <input
                  type="checkbox"
                  checked={types.includes(type)}
                  onChange={() =>
                    setTypes((current) =>
                      current.includes(type)
                        ? current.filter((x) => x !== type)
                        : [...current, type],
                    )
                  }
                />
                <span>{type}</span>
              </label>
            ))}
            {isDemo && (
              <>
                <h3>{t.priceRange}</h3>
                {[
                  ["all", "All prices"],
                  ["low", "Under $200"],
                  ["mid", "$200 to $350"],
                  ["high", "Over $350"],
                ].map(([value, label]) => (
                  <label className="checkbox-row" key={value}>
                    <input
                      type="radio"
                      name="budget"
                      checked={budget === value}
                      onChange={() => setBudget(value)}
                    />
                    <span>{label}</span>
                  </label>
                ))}
              </>
            )}
            <h3>{t.sort}</h3>
            {[
              ["recommended", t.recommended],
              ["low", t.priceLow],
              ["high", t.priceHigh],
            ].map(([value, label]) => (
              <label className="checkbox-row" key={value}>
                <input
                  type="radio"
                  name="sort"
                  checked={sort === value}
                  onChange={() => setSort(value)}
                />
                <span>{label}</span>
              </label>
            ))}
            {!isDemo && (
              <p className="filter-note">
                Prices are sorted within each currency. Check your dates on the
                property page to see available rooms.
              </p>
            )}
            <button
              className="button button-dark mobile-filter-done"
              onClick={() => setFilterOpen(false)}
            >
              Show {filtered.length} stays
            </button>
          </div>
        </aside>
      </div>
    </main>
  );
}
function DetailPage({ id }) {
  const {
    t,
    lang,
    data,
    client,
    connection,
    imageFor,
    navigate,
    search,
    setSearch,
    toast,
    setBookingModal,
    favorites,
    toggleFavorite,
    bookingApi,
  } = useApp();
  const [poi, setPoi] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [narration, setNarration] = useState(lang),
    [selectedImage, setSelectedImage] = useState(null),
    [selectedRoom, setSelectedRoom] = useState(""),
    [checked, setChecked] = useState(false),
    [checking, setChecking] = useState(false);
  useEffect(() => {
    setNarration(lang);
  }, [lang, id]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setChecked(false);
    setPoi(null);
    if (connection.mode === "demo") {
      const p = demoStays.find((x) => x.id === id);
      if (p) {
        setPoi(localizedDemo(p, narration));
        setSelectedRoom(p.menu_items[0]?.id || "");
      } else setError("Stay not found.");
      setLoading(false);
    } else
      client
        .detail(id, narration, { signal: controller.signal })
        .then((p) => {
          setPoi(p);
          setSelectedRoom(p.menu_items[0]?.id || "");
        })
        .catch((e) => {
          if (!controller.signal.aborted)
            setError(
              e.status === 404
                ? "This stay is no longer available."
                : "Unable to load this stay. Check the SmartStay connection.",
            );
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    return () => controller.abort();
  }, [id, narration, client, connection.mode]);
  if (loading)
    return (
      <main className="container inner-page">
        <div className="content-state">
          <Loader2 className="spin" />
          <p>{t.loading}</p>
        </div>
      </main>
    );
  if (error || !poi)
    return (
      <main className="container inner-page">
        <div className="content-state">
          <AlertCircle />
          <h2>{error || t.empty}</h2>
          <button
            className="button button-dark"
            onClick={() => navigate("/rooms")}
          >
            {t.back}
          </button>
        </div>
      </main>
    );
  const room =
      poi.menu_items.find((r) => r.id === selectedRoom) || currency(poi),
    images = poi.images?.length ? poi.images : [null];
  const check = async (e) => {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    const next = { ...search, ...fields };
    if (!next.checkIn || !next.checkOut)
      return toast(
        lang === "vi"
          ? "Vui lòng chọn ngày nhận và trả phòng."
          : "Please select your check-in and check-out dates.",
      );
    if (next.checkOut <= next.checkIn)
      return toast("Check-out must be after check-in.");
    if (Number(next.guests) > Number(room?.capacity || 100))
      return toast("Please choose a room with enough capacity.");
    if (!room)
      return toast(
        lang === "vi"
          ? "Khách sạn chưa có loại phòng để đặt."
          : "This property has no bookable room type.",
      );
    setSearch(next);
    if (connection.mode === "demo") {
      setChecked(true);
      return;
    }
    setChecking(true);
    setChecked(false);
    try {
      const result = await bookingApi.availability({
        poi_id: poi.id,
        room_type_id: room.id,
        check_in: next.checkIn,
        check_out: next.checkOut,
        guests: next.guests,
      });
      setChecked(result);
    } catch (e) {
      toast(e.message || "Cannot check availability.");
    } finally {
      setChecking(false);
    }
  };
  const galleryIndex = selectedImage ?? 0;
  return (
    <main className="container inner-page detail-page">
      <button className="back-link" onClick={() => navigate("/rooms")}>
        <ArrowLeft size={16} />
        {t.back}
      </button>
      <div className="detail-title-row">
        <h1>
          {poi.name} <span>({room?.name || poi.category})</span>
        </h1>
        {poi.sample && <span className="deal-badge">20% OFF</span>}
        <button
          className={
            "icon-button detail-save " +
            (favorites.includes(poi.id) ? "is-saved" : "")
          }
          aria-label="Save stay"
          onClick={() => toggleFavorite(poi.id)}
        >
          <Heart
            size={21}
            fill={favorites.includes(poi.id) ? "currentColor" : "none"}
          />
        </button>
      </div>
      {poi.sample && (
        <div className="list-reviews detail-reviews">
          <Stars />
          <span>200+ reviews</span>
        </div>
      )}
      <p className="address detail-address">
        <MapPin size={16} />
        {poi.address}
      </p>
      <div
        className={
          "detail-gallery " + (images.length === 1 ? "single-gallery" : "")
        }
      >
        <button
          className="gallery-main"
          aria-label="Open main room photo"
          onClick={() => setSelectedImage(0)}
        >
          <Photo src={imageFor(poi, 0)} alt={poi.name + " main room"} />
        </button>
        {images.length > 1 && (
          <div className="gallery-thumbnails">
            {Array.from({ length: Math.min(images.length, 4) }, (_, i) => (
              <button
                key={i}
                onClick={() => setSelectedImage(i)}
                aria-label={"Open room photo " + (i + 1)}
              >
                <Photo
                  src={imageFor(poi, i)}
                  alt={poi.name + " photo " + (i + 1)}
                />
                {i === Math.min(images.length, 4) - 1 && (
                  <span className="gallery-count">
                    View photos <span>{images.length}</span>
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="detail-summary">
        <div>
          <h2>
            {lang === "vi"
              ? "Trải nghiệm sự thoải mái tuyệt vời"
              : "Experience Luxury Like Never Before"}
          </h2>
          <Amenities poi={poi} detailed />
        </div>
        <div className="detail-price">
          {room
            ? money(Number(room.price), room.currency, lang).replace(".00", "")
            : displayPrice(poi, lang)}
          <span>{t.perNight}</span>
        </div>
      </div>
      <form className="availability-form" onSubmit={check}>
        <label>
          {t.checkIn}
          <input
            type="date"
            min={today()}
            name="checkIn"
            value={search.checkIn}
            disabled={checking}
            onChange={(e) => {
              setSearch((s) => ({ ...s, checkIn: e.target.value }));
              setChecked(false);
            }}
            required
          />
        </label>
        <label>
          {t.checkOut}
          <input
            type="date"
            name="checkOut"
            min={search.checkIn || today()}
            value={search.checkOut}
            disabled={checking}
            onChange={(e) => {
              setSearch((s) => ({ ...s, checkOut: e.target.value }));
              setChecked(false);
            }}
            required
          />
        </label>
        <label>
          {t.guests}
          <input
            type="number"
            name="guests"
            min="1"
            max={room?.capacity || 20}
            value={search.guests}
            disabled={checking}
            onChange={(e) => {
              setSearch((s) => ({ ...s, guests: e.target.value }));
              setChecked(false);
            }}
            required
          />
        </label>
        <button
          className="button button-blue"
          type="submit"
          disabled={checking || !room}
        >
          {checking && <Loader2 className="spin" size={16} />}
          {t.availability}
          <ArrowRight size={16} />
        </button>
      </form>
      {checked && (
        <div className="availability-result">
          {connection.mode === "demo" || checked.available ? (
            <CheckCircle2 size={20} />
          ) : (
            <AlertCircle size={20} />
          )}
          <div>
            <strong>
              {connection.mode === "demo"
                ? "Available in this preview"
                : checked.available
                  ? lang === "vi"
                    ? "Còn phòng cho ngày bạn chọn"
                    : "Available for your dates"
                  : lang === "vi"
                    ? "Hết phòng trong khoảng ngày này"
                    : "Sold out for these dates"}
            </strong>
            <p>
              {connection.mode === "demo"
                ? "This is a demo reservation. No actual room is reserved and no payment is taken."
                : `${checked.remaining} ${lang === "vi" ? "phòng còn trống · Tổng tiền" : "rooms remaining · Total"}: ${money(checked.total_price, checked.currency, lang)}`}
            </p>
          </div>
          {(connection.mode === "demo" || checked.available) && (
            <button
              className="button button-blue"
              onClick={() =>
                setBookingModal({ poi, room, search: { ...search } })
              }
            >
              {connection.mode === "demo"
                ? t.saveDemo
                : lang === "vi"
                  ? "Đặt phòng ngay"
                  : "Reserve this room"}
            </button>
          )}
        </div>
      )}
      <div className="detail-body">
        <div className="detail-main">
          <div className="feature-list">
            {[
              [HomeIcon, "clean", "cleanSub"],
              [ShieldCheck, "cleaning", "cleaningSub"],
              [MapPin, "location", "locationSub"],
              [Heart, "smooth", "smoothSub"],
            ].map(([Icon, title, sub]) => (
              <div key={title}>
                <Icon size={23} />
                <div>
                  <h3>{t[title]}</h3>
                  <p>{t[sub]}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="description">{poi.description}</p>
          <AudioGuide
            poi={poi}
            language={narration}
            setLanguage={setNarration}
            onPrepared={setPoi}
          />
          <section className="room-options">
            <h3>{t.rooms}</h3>
            {poi.menu_items
              .filter((r) => r.kind === "room_type")
              .map((r) => (
                <label
                  key={r.id}
                  className={
                    "room-option " +
                    (r.id === selectedRoom ? "room-option-selected" : "")
                  }
                >
                  <input
                    type="radio"
                    name="roomOption"
                    checked={r.id === selectedRoom}
                    disabled={checking}
                    onChange={() => {
                      setSelectedRoom(r.id);
                      setChecked(false);
                    }}
                  />
                  <div>
                    <strong>{r.name}</strong>
                    <small>
                      <Users size={13} />
                      {r.capacity} {t.guests.toLowerCase()}
                    </small>
                    <p>{r.description}</p>
                  </div>
                  <b>
                    {money(Number(r.price), r.currency, lang)}
                    <small>{t.perNight}</small>
                  </b>
                </label>
              ))}
          </section>
          <div className="checkin-info">
            <h3>{t.instructions}</h3>
            <p>
              {poi.check_in_instructions ||
                (lang === "vi"
                  ? "Vui lòng liên hệ nơi lưu trú để biết hướng dẫn."
                  : "Please contact the property for arrival instructions.")}
            </p>
          </div>
          <section className="location-section">
            <h3>
              {lang === "vi" ? "Vị trí nơi lưu trú" : "Location on the map"}
            </h3>
            <div className="map-panel">
              <iframe
                title={poi.name + " map"}
                src={
                  "https://maps.google.com/maps?q=" +
                  Number(poi.latitude) +
                  "," +
                  Number(poi.longitude) +
                  "&z=14&output=embed"
                }
                loading="lazy"
                referrerPolicy="no-referrer"
              />
              <a
                href={mapUrl(poi)}
                target="_blank"
                rel="noreferrer"
                className="map-link"
              >
                <MapPin size={16} />
                {t.viewMap}
                <ExternalLink size={13} />
              </a>
            </div>
            <p className="address">
              <MapPin size={15} />
              {poi.address}
            </p>
          </section>
          <div className="host-card">
            <div className="host-avatar">
              <HomeIcon size={25} />
            </div>
            <div>
              <h3>
                {lang === "vi"
                  ? "Đội ngũ đón tiếp"
                  : "Your stay, thoughtfully hosted"}
              </h3>
              <p>{poi.name}</p>
            </div>
            <button
              className="button button-outline"
              onClick={() => toast(poi.check_in_instructions || poi.address)}
            >
              {t.instructions}
            </button>
          </div>
        </div>
        <aside className="stay-note">
          <span>THE QUICKSTAY PROMISE</span>
          <h3>
            A stay worth
            <br />
            remembering.
          </h3>
          <p>Take a breath, settle in, and make room for a little discovery.</p>
          <Headphones size={27} />
          <small>Explore your stay with the multilingual audio guide.</small>
        </aside>
      </div>
      {selectedImage !== null && (
        <Modal
          title={poi.name + " · Photos"}
          wide
          onClose={() => setSelectedImage(null)}
        >
          <div className="lightbox">
            <Photo
              src={imageFor(poi, galleryIndex)}
              alt={"Room photo " + (galleryIndex + 1)}
            />
            <div>
              <button
                className="icon-button"
                aria-label="Previous photo"
                onClick={() =>
                  setSelectedImage(
                    (galleryIndex - 1 + images.length) % images.length,
                  )
                }
              >
                <ChevronLeft />
              </button>
              <span>
                {galleryIndex + 1} / {images.length}
              </span>
              <button
                className="icon-button"
                aria-label="Next photo"
                onClick={() =>
                  setSelectedImage((galleryIndex + 1) % images.length)
                }
              >
                <ChevronRight />
              </button>
            </div>
          </div>
        </Modal>
      )}
    </main>
  );
}
function BookingsPage() {
  const { t, connection, bookings, setBookings, navigate, setInfo, lang } =
    useApp();
  const [selected, setSelected] = useState(null);
  const rows = connection.mode === "demo" ? bookings : [];
  const fmt = (v) =>
    new Date(v + "T12:00:00").toLocaleDateString(
      lang === "vi" ? "vi-VN" : "en-GB",
      { day: "numeric", month: "short", year: "numeric" },
    );
  return (
    <main className="container inner-page bookings-page">
      <div className="page-heading">
        <h1>{t.bookings}</h1>
        <p>{t.bookingsSub}</p>
      </div>
      <div className="preview-inline">
        <AlertCircle size={16} />
        {connection.mode === "demo"
          ? "Sample reservations — no real booking or payment has been made."
          : "Reservations are not yet available in the current SmartStay backend."}
      </div>
      <div className="booking-table-head">
        <span>{t.hotel}</span>
        <span>{t.dateTime}</span>
        <span>{t.payment}</span>
      </div>
      {rows.map((b) => (
        <article className="booking-row" key={b.id}>
          <div className="booking-hotel">
            <button
              onClick={() => navigate("/rooms/" + b.stayId)}
              aria-label={"View " + b.name}
            >
              <Photo src={b.image} alt={b.name} />
            </button>
            <div>
              <h2>
                {b.name}
                <span>({b.room})</span>
              </h2>
              <p className="address">
                <MapPin size={14} />
                {b.address}
              </p>
              <p>
                <Users size={14} />
                {t.guests}: {b.guests}
              </p>
              <b>
                {t.total}: {money(b.price, "USD", lang).replace(".00", "")}
              </b>
            </div>
          </div>
          <div className="booking-dates">
            <p>
              <span>{t.checkIn}:</span>
              {fmt(b.checkIn)}
            </p>
            <p>
              <span>{t.checkOut}:</span>
              {fmt(b.checkOut)}
            </p>
          </div>
          <div className="booking-payment">
            <span className={"payment-status " + (b.paid ? "paid" : "unpaid")}>
              <i />
              {b.paid ? "Completed · sample" : "Pending · sample"}
            </span>
            <button
              className="button button-outline"
              onClick={() => setSelected(b)}
            >
              {t.details}
            </button>
          </div>
        </article>
      ))}
      {!rows.length && (
        <div className="content-state">
          <CalendarDays size={36} />
          <h3>
            {lang === "vi" ? "Chưa có đặt phòng" : "Your next stay is waiting"}
          </h3>
          <p>
            {connection.mode === "api"
              ? "You can browse real stays and room options while booking support is being added."
              : "Explore a stay and save a demo reservation."}
          </p>
          <button
            className="button button-dark"
            onClick={() => navigate("/rooms")}
          >
            {t.hotels}
            <ArrowRight size={17} />
          </button>
        </div>
      )}
      {selected && (
        <Modal title="Reservation preview" onClose={() => setSelected(null)}>
          <Photo
            src={selected.image}
            alt={selected.name}
            className="modal-photo"
          />
          <h3>
            {selected.name} · {selected.room}
          </h3>
          <p>
            {fmt(selected.checkIn)} — {fmt(selected.checkOut)}
          </p>
          <p>
            {selected.guests} guests · {money(selected.price, "USD", lang)}
          </p>
          <div className="preview-inline">
            Sample booking stored on this device. It does not reserve a room or
            collect payment.
          </div>
          {!selected.id.startsWith("sample-") && (
            <button
              className="button button-outline"
              onClick={() => {
                const next = bookings.filter((b) => b.id !== selected.id);
                setBookings(next);
                writeStorage("quickstay.demo-bookings", next);
                setSelected(null);
              }}
            >
              Remove demo booking
            </button>
          )}
        </Modal>
      )}
    </main>
  );
}
function Footer() {
  const { t, lang, setSettingsOpen, showInfo, connection, navigate } = useApp();
  const link = (title) => () =>
    showInfo(
      title,
      title === "Contact us"
        ? "For questions about a property, please see its address and check-in information on the stay detail page. This design preview does not provide a support inbox."
        : title === "Privacy policy"
          ? "This preview stores saved stays, language and demo reservations in your browser. When you connect SmartStay, public content is requested from the API URL you choose. Login credentials are sent only to that API; session tokens are kept in memory. Maps are provided by Google Maps."
          : "This is an interactive QuickStay design preview. Sample rooms, offers and reservations are for demonstration. SmartStay connection is available below.",
    );
  return (
    <footer id="about">
      <div className="container footer-main">
        <div className="footer-brand">
          <a href="#/">
            <img src="/assets/logo.svg" alt="QuickStay" />
          </a>
          <p>
            Discover the world's most extraordinary places to stay. Luxury,
            comfort, and unforgettable experiences, all in one place.
          </p>
          <div className="social-links">
            {[
              [Instagram, "Instagram"],
              [Facebook, "Facebook"],
              [Twitter, "Twitter"],
              [Linkedin, "LinkedIn"],
            ].map(([Icon, name]) => (
              <button key={name} aria-label={name} onClick={link(name)}>
                <Icon size={17} />
              </button>
            ))}
          </div>
        </div>
        <div className="footer-column">
          <h3>COMPANY</h3>
          {["About us", "Careers", "Press", "Blog", "Partners"].map((x) => (
            <button key={x} onClick={link(x)}>
              {x}
            </button>
          ))}
        </div>
        <div className="footer-column">
          <h3>SUPPORT</h3>
          {[
            "Help center",
            "Safety information",
            "Cancellation options",
            "Contact us",
            "Accessibility",
          ].map((x) => (
            <button key={x} onClick={link(x)}>
              {x}
            </button>
          ))}
        </div>
        <div className="footer-column footer-updates">
          <h3>STAY UPDATED</h3>
          <p>Travel inspiration, tailored to your next escape.</p>
          <button
            className="footer-connect"
            onClick={() => setSettingsOpen(true)}
          >
            <Server size={16} />
            {connection.mode === "demo" ? t.connect : "SmartStay connected"}
            <ArrowRight size={15} />
          </button>
          <small>
            {connection.mode === "demo"
              ? "Interactive design preview · sample data"
              : "Live content from your SmartStay API"}
          </small>
          <a className="text-link footer-admin-link" href="#/admin">
            <ShieldCheck size={15} />
            Dashboard
          </a>
        </div>
      </div>
      <div className="container footer-bottom">
        <p>© {new Date().getFullYear()} QuickStay. All rights reserved.</p>
        <div>
          {["Privacy policy", "Terms of service", "Sitemap"].map((x) => (
            <button key={x} onClick={link(x)}>
              {x}
            </button>
          ))}
        </div>
      </div>
    </footer>
  );
}
function SettingsModal() {
  const {
    connection,
    setConnection,
    setSettingsOpen,
    setSession,
    t,
    toast,
    lang,
  } = useApp();
  const [base, setBase] = useState(connection.base || ""),
    [mode, setMode] = useState(connection.mode),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function save(e) {
    e.preventDefault();
    setError("");
    if (mode === "demo") {
      setConnection({ mode: "demo", base: "/api" });
      writeStorage("quickstay.connection", { mode: "demo", base: "/api" });
      setSession(null);
      setSettingsOpen(false);
      return;
    }
    setBusy(true);
    try {
      const normalized = normalizeBase(base);
      if (location.protocol === "https:" && normalized.startsWith("http:"))
        throw new Error(
          "This HTTPS website needs an HTTPS API URL. For a local HTTP backend, run the React project locally with its Vite proxy.",
        );
      if (
        /https?:\/\/(?:localhost|127\.0\.0\.1)(?::|\/|$)/.test(normalized) &&
        location.hostname !== "localhost" &&
        location.hostname !== "127.0.0.1"
      )
        throw new Error(
          "A hosted website cannot reach the backend on your computer. Use a public HTTPS API URL, or run the frontend locally.",
        );
      const c = createClient(normalized);
      await c.loadAll(lang);
      const value = { mode: "api", base: normalized };
      setConnection(value);
      setSession(null);
      writeStorage("quickstay.connection", value);
      toast("SmartStay connected. Loading real content.");
      setSettingsOpen(false);
    } catch (e) {
      setError(
        e.message.includes("fetch")
          ? "Cannot reach the API. Check its URL, HTTPS and TRUSTED_ORIGINS settings."
          : e.message,
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="SmartStay connection" onClose={() => setSettingsOpen(false)}>
      <p className="modal-intro">
        Choose sample data for the design preview, or connect your own SmartStay
        backend.
      </p>
      <form onSubmit={save}>
        <div className="connection-options">
          <label className={mode === "demo" ? "selected" : ""}>
            <input
              type="radio"
              name="connection"
              checked={mode === "demo"}
              onChange={() => setMode("demo")}
            />
            <div>
              <strong>Design preview</strong>
              <small>Sample rooms, offers and demo bookings.</small>
            </div>
          </label>
          <label className={mode === "api" ? "selected" : ""}>
            <input
              type="radio"
              name="connection"
              checked={mode === "api"}
              onChange={() => setMode("api")}
            />
            <div>
              <strong>Live SmartStay API</strong>
              <small>
                Your real properties, rooms, translations and recordings.
              </small>
            </div>
          </label>
        </div>
        {mode === "api" && (
          <>
            <label className="form-label">
              API origin or proxy base
              <input
                value={base}
                onChange={(e) => setBase(e.target.value)}
                placeholder="https://api.your-domain.com"
                required
              />
            </label>
            <p className="form-help">
              Enter the server root, without /docs or /poi. Local React
              development can use /api through the included proxy. Add this
              website's origin to TRUSTED_ORIGINS.
            </p>
          </>
        )}
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <button
          className="button button-dark full-button"
          type="submit"
          disabled={busy}
        >
          {busy ? (
            <>
              <Loader2 size={16} className="spin" />
              Checking API…
            </>
          ) : (
            "Save connection"
          )}
          <ArrowRight size={16} />
        </button>
      </form>
    </Modal>
  );
}
function AuthModal() {
  const { setAuthOpen, connection, bookingApi, toast, t } = useApp();
  const [register, setRegister] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(e.currentTarget),
      username = String(form.get("username")),
      password = String(form.get("password"));
    try {
      const result = register
        ? await bookingApi.register({
            username,
            password,
            full_name: String(form.get("full_name")),
          })
        : await bookingApi.login(username, password);
      if (register) {
        setRegister(false);
        toast("Account created. You can now sign in.");
      } else {
        setAuthOpen(false);
        toast("Welcome, " + result.user.full_name + ".");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={register ? t.register : "Welcome to QuickStay"}
      onClose={() => setAuthOpen(false)}
    >
      {connection.mode === "demo" ? (
        <>
          <div className="auth-welcome">
            <HomeIcon size={36} />
            <h3>A little closer to your next escape.</h3>
            <p>
              Sign in becomes available when you connect your SmartStay API. You
              can explore all sample stays without an account.
            </p>
          </div>
          <button
            className="button button-dark full-button"
            onClick={() => setAuthOpen(false)}
          >
            Continue exploring
            <ArrowRight size={17} />
          </button>
        </>
      ) : (
        <form onSubmit={submit}>
          {register && (
            <label className="form-label">
              {t.firstName}
              <input
                name="full_name"
                required
                maxLength="100"
                autoComplete="name"
              />
            </label>
          )}
          <label className="form-label">
            {t.username}
            <input
              name="username"
              required
              minLength={register ? 3 : 1}
              maxLength="50"
              pattern="[a-zA-Z0-9_.-]+"
              autoComplete="username"
            />
          </label>
          <label className="form-label">
            {t.password}
            <input
              name="password"
              type="password"
              required
              minLength={register ? 8 : 1}
              maxLength="72"
              autoComplete={register ? "new-password" : "current-password"}
            />
          </label>
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <button className="button button-dark full-button" disabled={busy}>
            {busy ? (
              <Loader2 className="spin" size={16} />
            ) : register ? (
              t.register
            ) : (
              t.signIn
            )}
            <ArrowRight size={17} />
          </button>
          <button
            className="auth-switch"
            type="button"
            onClick={() => {
              setRegister(!register);
              setError("");
            }}
          >
            {register
              ? "Already have an account? Sign in"
              : "New here? Create an account"}
          </button>
          <p className="form-help">
            Your session is kept in memory and ends when you reload this page.
          </p>
        </form>
      )}
    </Modal>
  );
}
export default function App() {
  const route = useRoute(),
    path = route.split("?")[0];
  const [lang, setLangState] = useState(() =>
    readStorage("quickstay.language", "en"),
  );
  const [connection, setConnection] = useState(() =>
    readStorage(
      "quickstay.connection",
      import.meta.env.VITE_SMARTSTAY_API_BASE
        ? { mode: "api", base: import.meta.env.VITE_SMARTSTAY_API_BASE }
        : { mode: "demo", base: "/api" },
    ),
  );
  const [data, setData] = useState([]),
    [status, setStatus] = useState("loading"),
    [error, setError] = useState(""),
    [settingsOpen, setSettingsOpen] = useState(false),
    [authOpen, setAuthOpen] = useState(false),
    [session, setSession] = useState(null),
    [adminSession, setAdminSession] = useState(null),
    [favorites, setFavorites] = useState(() =>
      readStorage("quickstay.favorites", []),
    ),
    [savedOnly, setSavedOnly] = useState(false),
    [offer, setOffer] = useState(null),
    [info, setInfo] = useState(null),
    [notification, setNotification] = useState(""),
    [bookingModal, setBookingModal] = useState(null),
    [bookings, setBookings] = useState(() =>
      readStorage("quickstay.demo-bookings", sampleBookings),
    );
  const [search, setSearch] = useState({
    destination: "",
    checkIn: "",
    checkOut: "",
    guests: "2",
  });
  const t = copy[lang] || copy.en;
  const client = useMemo(() => {
    try {
      return createClient(connection.base);
    } catch {
      return createClient("/api");
    }
  }, [connection.base]);
  const requestId = useRef(0);
  const bookingApi = useMemo(
    () => createBookingClient(connection.base, setSession),
    [connection.base],
  );
  const adminApi = useMemo(
    () =>
      createBookingClient(connection.base, setAdminSession, { admin: true }),
    [connection.base],
  );
  useEffect(() => {
    bookingApi.clear();
    adminApi.clear();
    setBookingModal(null);
  }, [connection, bookingApi, adminApi]);
  async function load() {
    const current = ++requestId.current;
    setStatus("loading");
    setError("");
    if (connection.mode === "demo") {
      setData(demoStays);
      setStatus("ready");
      return;
    }
    try {
      const result = await client.loadAll(lang);
      if (current === requestId.current) {
        setData(result.items);
        setStatus("ready");
      }
    } catch (e) {
      if (current === requestId.current) {
        setData([]);
        setError(
          "Check that your backend is running and permits this website in TRUSTED_ORIGINS. No sample data is substituted.",
        );
        setStatus("error");
      }
    }
  }
  useEffect(() => {
    load();
    return () => {
      requestId.current++;
    };
  }, [client, connection.mode, lang]);
  useEffect(() => {
    if (!notification) return;
    const timeout = setTimeout(() => setNotification(""), 5500);
    return () => clearTimeout(timeout);
  }, [notification]);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  const navigate = (path) => {
    if ((window.location.hash.slice(1) || "/") === path)
      window.scrollTo({ top: 0, behavior: "smooth" });
    else window.location.hash = path;
  };
  const setLang = (value) => {
    setLangState(value);
    writeStorage("quickstay.language", value);
  };
  const toast = (value) => setNotification(value);
  const toggleFavorite = (id) =>
    setFavorites((previous) => {
      const next = previous.includes(id)
        ? previous.filter((x) => x !== id)
        : [...previous, id];
      writeStorage("quickstay.favorites", next);
      return next;
    });
  const imageFor = (poi, index) =>
    connection.mode === "demo"
      ? poi.images?.[index] || poi.images?.[0]
      : mediaUrl(poi.images?.[index] || poi.images?.[0], connection.base);
  const scrollSection = (id) => {
    if (path !== "/") {
      navigate("/");
      setTimeout(
        () =>
          document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }),
        100,
      );
    } else document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };
  const showInfo = (title, text) => setInfo({ title, text });
  async function signOut() {
    try {
      await bookingApi.logout();
    } catch {
      toast(
        "Signed out on this device. The server could not be reached to revoke the session.",
      );
    } finally {
      setSession(null);
    }
  }
  function saveDemoBooking() {
    const { poi, room, search: s } = bookingModal;
    const nights = Math.round(
      (Date.parse(s.checkOut) - Date.parse(s.checkIn)) / 86400000,
    );
    const booking = {
      id:
        "demo-" +
        (typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : Date.now().toString(36) +
            "-" +
            Math.random().toString(36).slice(2)),
      stayId: poi.id,
      name: poi.name,
      room: room?.name || poi.roomType,
      image: imageFor(poi, 0),
      address: poi.address,
      price: Number(room.price) * nights,
      guests: Number(s.guests),
      checkIn: s.checkIn,
      checkOut: s.checkOut,
      paid: false,
      sample: true,
    };
    const next = [booking, ...bookings];
    setBookings(next);
    writeStorage("quickstay.demo-bookings", next);
    setBookingModal(null);
    toast("Demo reservation saved on this device. No room has been reserved.");
    navigate("/bookings");
  }
  const ctx = {
    route: path,
    t,
    lang,
    setLang,
    connection,
    setConnection,
    data,
    status,
    error,
    load,
    client,
    bookingApi,
    adminApi,
    adminSession,
    navigate,
    scrollSection,
    search,
    setSearch,
    favorites,
    toggleFavorite,
    savedOnly,
    setSavedOnly,
    imageFor,
    settingsOpen,
    setSettingsOpen,
    session,
    setSession,
    setAuthOpen,
    signOut,
    toast,
    showInfo,
    setInfo,
    setOffer,
    setBookingModal,
    bookings,
    setBookings,
  };
  const page =
    path === "/" ? (
      <HomePage />
    ) : path === "/rooms" ? (
      <RoomsPage />
    ) : path === "/bookings" ? (
      connection.mode === "api" ? (
        <CustomerBookings />
      ) : (
        <BookingsPage />
      )
    ) : path === "/admin" ? (
      <AdminDashboard />
    ) : path === "/control" ? (
      <SmartStayControlCenter onSwitchToClassic={() => navigate("/rooms")} />
    ) : path.startsWith("/rooms/") ? (
      <DetailPage key={path} id={decodeURIComponent(path.split("/")[2])} />
    ) : (
      <main className="container inner-page content-state">
        <h1>Page not found</h1>
        <a href="#/" className="button button-dark">
          Back to home
        </a>
      </main>
    );
  return (
    <Context.Provider value={ctx}>
      <a
        className="skip-link"
        href="#page-content"
        onClick={(e) => {
          e.preventDefault();
          const node = document.getElementById("page-content");
          node.focus();
          node.scrollIntoView();
        }}
      >
        Skip to content
      </a>
      <Header />
      <div id="page-content" tabIndex={-1}>
        {page}
      </div>
      <Footer />
      {connection.mode === "demo" && (
        <button className="preview-chip" onClick={() => setSettingsOpen(true)}>
          <span />
          <span>{t.demo}</span>
          <ChevronRight size={13} />
        </button>
      )}
      {notification && (
        <div className="toast" role="status">
          <CheckCircle2 size={19} />
          {notification}
          <button
            aria-label="Dismiss notification"
            onClick={() => setNotification("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {settingsOpen && <SettingsModal />}
      {authOpen && <AuthModal />}
      {offer && (
        <Modal
          title={offer.all ? t.offers : offer.title}
          wide={!!offer.all}
          onClose={() => setOffer(null)}
        >
          {offer.all ? (
            <div className="offer-modal-grid">
              {offers.map((o) => (
                <button key={o.id} onClick={() => setOffer(o)}>
                  <img src={o.image} alt={o.title} />
                  <h3>{o.title}</h3>
                  <p>
                    {o.discount}% OFF · View details
                    <ArrowRight size={14} />
                  </p>
                </button>
              ))}
            </div>
          ) : (
            <>
              <img
                src={offer.image}
                alt={offer.title}
                className="modal-photo"
              />
              <span className="modal-discount">{offer.discount}% OFF</span>
              <h3>{offer.title}</h3>
              <p>{offer.description}</p>
              <div className="preview-inline">
                <AlertCircle size={17} />
                This is a sample offer from the design, not an active promotion.
              </div>
              <button
                className="button button-dark full-button"
                onClick={() => {
                  setOffer(null);
                  navigate("/rooms");
                }}
              >
                Explore hotels
                <ArrowRight size={17} />
              </button>
            </>
          )}
        </Modal>
      )}
      {info && (
        <Modal title={info.title} onClose={() => setInfo(null)}>
          <p className="modal-intro">{info.text}</p>
          <button
            className="button button-dark full-button"
            onClick={() => setInfo(null)}
          >
            Got it
          </button>
        </Modal>
      )}
      {bookingModal && connection.mode === "api" && (
        <Checkout reservation={bookingModal} Modal={Modal} />
      )}
      {bookingModal && connection.mode === "demo" && (
        <Modal
          title="Save a demo reservation"
          onClose={() => setBookingModal(null)}
        >
          <Photo
            src={imageFor(bookingModal.poi, 0)}
            alt={bookingModal.poi.name}
            className="modal-photo"
          />
          <h3>
            {bookingModal.poi.name} · {bookingModal.room.name}
          </h3>
          <p>
            {bookingModal.search.checkIn} — {bookingModal.search.checkOut}
          </p>
          <p>
            {bookingModal.search.guests} guests ·{" "}
            {money(
              Number(bookingModal.room.price) *
                Math.round(
                  (Date.parse(bookingModal.search.checkOut) -
                    Date.parse(bookingModal.search.checkIn)) /
                    86400000,
                ),
              bookingModal.room.currency,
              lang,
            )}
          </p>
          <div className="preview-inline">
            <AlertCircle size={17} />
            This only saves a sample reservation on your device. It does not
            reserve a room or collect payment.
          </div>
          <button
            className="button button-blue full-button"
            onClick={saveDemoBooking}
          >
            {t.saveDemo}
            <ArrowRight size={17} />
          </button>
        </Modal>
      )}
    </Context.Provider>
  );
}
