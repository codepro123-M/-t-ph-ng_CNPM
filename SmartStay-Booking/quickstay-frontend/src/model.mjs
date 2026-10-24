export function fold(value = '') { return String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase(); }
export function minimumPrice(poi) {
  const rooms = (poi.menu_items || []).filter(row => row.kind === 'room_type' && row.is_available !== false && row.currency === 'VND' && /^\d+(\.\d{1,2})?$/.test(String(row.price)));
  return rooms.length ? Math.min(...rooms.map(row => Number(row.price))) : null;
}
export function money(value, currency = 'VND', language = 'vi') {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  try { return new Intl.NumberFormat(language === 'vi' ? 'vi-VN' : 'en-US', { style: 'currency', currency, maximumFractionDigits: currency === 'VND' ? 0 : 2 }).format(Number(value)); }
  catch { return String(value) + ' ' + currency; }
}
export function filterStays(rows, { search = '', category = 'all', budget = 'all', savedOnly = false, favorites = [], sort = 'recommended' } = {}) {
  const term = fold(search.trim());
  let result = rows.filter(row => (!term || fold(row.name + ' ' + row.address).includes(term)) && (category === 'all' || row.category === category) && (!savedOnly || favorites.includes(row.id)));
  if (budget !== 'all') result = result.filter(row => {
    const price = minimumPrice(row);
    return price !== null && (budget === 'low' ? price < 500000 : budget === 'mid' ? price >= 500000 && price <= 1500000 : price > 1500000);
  });
  return [...result].sort((a, b) => {
    if (sort === 'price-up' || sort === 'price-down') {
      const ap = minimumPrice(a), bp = minimumPrice(b);
      if (ap == null) return bp == null ? 0 : 1;
      if (bp == null) return -1;
      return sort === 'price-up' ? ap - bp : bp - ap;
    }
    if (sort === 'distance') return (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity);
    return (b.audio_priority || 0) - (a.audio_priority || 0) || a.name.localeCompare(b.name, 'vi');
  });
}
export function readStorage(key, fallback) {
  try { const value = localStorage.getItem(key); return value == null ? fallback : JSON.parse(value); } catch { return fallback; }
}
export function writeStorage(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Browsing remains usable when storage is disabled. */ } }
export function mapUrl(poi, directions = false) {
  const lat = Number(poi.latitude), lng = Number(poi.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return directions ? `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}` : `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
}
