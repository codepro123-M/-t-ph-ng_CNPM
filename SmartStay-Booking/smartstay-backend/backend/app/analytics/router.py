from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from app.core.database import db_manager

router = APIRouter(tags=["analytics"])

# Bộ nhớ tạm in-memory đảm bảo luôn phản hồi ngay cả khi DB đang bận
_MEMORY_QR_LOGS: List[Dict[str, Any]] = [
    {
        "id": "qr-demo-1",
        "stay_id": "saigon-riverside",
        "stay_name": "SmartStay Saigon Riverside Hotel",
        "device": "iPhone 15 Pro (Safari Mobile)",
        "ip": "172.20.10.3",
        "action": "Quét mã QR tại Quầy lễ tân & Xem bản đồ Sài Gòn",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    },
    {
        "id": "qr-demo-2",
        "stay_id": "saigon-central",
        "stay_name": "SmartStay Central Ben Thanh Villa",
        "device": "Samsung Galaxy S24 (Chrome Mobile)",
        "ip": "172.20.10.4",
        "action": "Quét mã QR trên Cửa phòng & Nghe thuyết minh",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "status": "connected",
    },
]


class QRScanEvent(BaseModel):
    stay_id: Optional[str] = "saigon-riverside"
    stay_name: Optional[str] = "SmartStay Saigon Riverside Hotel"
    device: Optional[str] = "Mobile Device"
    url: Optional[str] = "/"
    action: Optional[str] = "Quét mã QR truy cập trang web"


def parse_device_info(user_agent: str) -> str:
    ua = user_agent.lower()
    if "iphone" in ua:
        return "Apple iPhone (iOS Safari)"
    elif "ipad" in ua:
        return "Apple iPad"
    elif "android" in ua:
        return "Android Smartphone (Chrome)"
    elif "macintosh" in ua or "mac os" in ua:
        return "Mac OS Desktop"
    elif "windows" in ua:
        return "Windows PC"
    return "Mobile / Web Device"


@router.get("/analytics/ping")
@router.get("/api/v1/analytics/ping")
async def ping_analytics():
    return {"lane": "analytics", "status": "ok"}


@router.post("/analytics/qr-scan")
@router.post("/api/v1/analytics/qr-scan")
async def record_qr_scan(payload: QRScanEvent, request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    ua = request.headers.get("user-agent", "")
    detected_device = parse_device_info(ua) if payload.device == "Mobile Device" else payload.device

    record = {
        "id": f"qr-{int(datetime.now().timestamp() * 1000)}",
        "stay_id": payload.stay_id,
        "stay_name": payload.stay_name,
        "device": detected_device,
        "url": payload.url,
        "ip": client_ip,
        "action": payload.action,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }

    # Lưu vào in-memory
    _MEMORY_QR_LOGS.insert(0, record)
    if len(_MEMORY_QR_LOGS) > 100:
        _MEMORY_QR_LOGS.pop()

    # Thử lưu vào MongoDB nếu database sẵn sàng
    if db_manager.db is not None:
        try:
            await db_manager.db["qr_scans"].insert_one({
                "stay_id": record["stay_id"],
                "stay_name": record["stay_name"],
                "device": record["device"],
                "url": record["url"],
                "ip": record["ip"],
                "action": record["action"],
                "scanned_at": record["scanned_at"],
            })
        except Exception:
            pass

    return {
        "status": "recorded",
        "event_id": record["id"],
        "total_scans": len(_MEMORY_QR_LOGS),
    }


@router.get("/analytics/qr-stats")
@router.get("/api/v1/analytics/qr-stats")
async def get_qr_stats():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_count = sum(1 for x in _MEMORY_QR_LOGS if x.get("scanned_at", "").startswith(now_str))
    
    # Đếm số thiết bị
    devices = {}
    for x in _MEMORY_QR_LOGS:
        d = x.get("device", "Khác")
        devices[d] = devices.get(d, 0) + 1
    
    top_device = max(devices, key=devices.get) if devices else "Mobile"

    return {
        "total_scans": len(_MEMORY_QR_LOGS),
        "today_scans": max(today_count, 1),
        "active_visitors": min(len(_MEMORY_QR_LOGS), 3),
        "top_device": top_device,
        "recent_scans": _MEMORY_QR_LOGS[:25],
    }


@router.post("/analytics/qr-clear")
@router.post("/api/v1/analytics/qr-clear")
async def clear_qr_stats():
    _MEMORY_QR_LOGS.clear()
    if db_manager.db is not None:
        try:
            await db_manager.db["qr_scans"].delete_many({})
        except Exception:
            pass
    return {"status": "cleared", "total_scans": 0}
