# SmartStay — đặt phòng thật

Module mới: `backend/app/bookings`. `main.py` tự tạo index và nâng cấp hai quyền `booking.read`, `booking.update` cho vai trò admin dựng sẵn một lần. Không cần xóa database.

## Cập nhật dự án cũ

Dùng `AP_DUNG_DAT_PHONG.py` ở gói SmartStay-Booking, chọn backend cũ có `docker-compose.yml` và `.env`. Script sao lưu mã cũ, giữ dữ liệu MongoDB/Redis/S3, giữ các cấu hình khác và chỉ thêm hai origin localhost cổng 4173 trong môi trường phát triển.

Terminal tại backend cũ:

```powershell
docker compose up -d --build backend
docker compose ps
```

Giữ cách thêm file Compose S3/HTTPS của bạn nếu đang dùng. Không cần chạy lại trình khởi tạo giai đoạn 2 khi đã có tài khoản admin và cấu hình hoạt động. Đăng nhập lại sau nâng cấp để token nhận quyền booking mới.

## Dự án mới

```powershell
Copy-Item .env.example .env
python scripts/configure_phase2.py
docker compose up -d --build
```

Làm theo script để tạo khóa/tài khoản super-admin. Nếu cần S3, dùng các script cấu hình hiện có. Frontend có README riêng.

## API mới

| API | Quyền và dữ liệu |
|---|---|
| `GET /bookings/availability` | Công khai, query `poi_id`, `room_type_id`, `check_in`, `check_out`, `guests`; trả phòng trống và giá |
| `POST /bookings` | Tài khoản khách Bearer; body: các trường trên, UUID `request_id`, `contact_name`, `email`, `phone`, `notes` tùy chọn |
| `GET /bookings` | Chỉ đơn của khách hiện tại; `page`, `limit` |
| `GET /bookings/{id}` | Chỉ chủ đơn |
| `PATCH /bookings/{id}/cancel` | Chủ đơn; body `{"expected_revision":1}` |
| `GET /admin/bookings` | `booking.read`; `page`, `limit`, `status`, `search`, tổng số từng trạng thái |
| `PATCH /admin/bookings/{id}` | `booking.update`; `expected_revision`, `status` |

Admin đăng nhập `POST /admin/auth/login`, khách đăng nhập `/api/v1/auth/session`, JSON `mode: bearer`.

## Quy tắc

- `pending` sang `confirmed` hoặc `cancelled`; `confirmed` sang `cancelled` hoặc `completed`. Chỉ hoàn thành khi đến ngày trả phòng. Đơn hủy/hoàn thành không mở lại bằng API này.
- Ngày tính theo UTC+7. Mỗi đơn một phòng, 1–30 đêm, nhận từ hôm nay tới 365 ngày tới. Ngày trả phòng không chiếm chỗ qua đêm.
- `menu_items.inventory` từ 1–1000, mặc định 1; `capacity` là số khách/phòng. Chỉ phòng đang khả dụng của khách sạn đang công khai được đặt.
- Đơn chờ/đã xác nhận đều giữ phòng; chưa có tự hết hạn giữ phòng. Hủy/hoàn thành trả số lượng trong cùng giao dịch.
- `bookings` lưu đơn/thông tin liên hệ, `booking_inventory` lưu số lượng theo loại phòng/đêm. Không có TTL xóa đơn.
- Snapshot/majority transaction tự thử lại xung đột. Lưu đơn, số lượng và audit cùng giao dịch; lỗi thì rollback.
- Unique theo khách + UUID tránh trùng. Cùng UUID với nội dung khác trả 409. Giá/tổng tiền không được nhận từ frontend, tính bằng Decimal từ giá server.
- Snapshot tên nơi lưu trú/phòng/giá giúp đơn cũ giữ đúng thông tin khi nội dung thay đổi. Revision ngăn ghi đè từ tab khác.
- Khách chỉ xem/hủy đơn của mình trước/sát ngày nhận phòng. Admin có quyền xem toàn hệ thống. Chưa có dashboard đơn riêng từng chủ khách sạn.
- Chưa có thanh toán online, email xác nhận hay đếm lượt QR/nghe. Tổng tiền không có nghĩa khách đã trả tiền.

## Kiểm thử

```powershell
python -m pip install -r backend/requirements-test.txt
python -m pytest -q
docker compose exec -T backend python integration/check_booking_replica.py
```

166 kiểm tra backend đã qua. Lệnh integration chỉ tạo database tạm tiền tố `smartstay_booking_test_`, kiểm tra 12 yêu cầu tranh một phòng, 8 yêu cầu cùng UUID, rollback lỗi audit rồi xóa chính database tạm đó. Đã chạy qua trên MongoDB 7 replica set. CI đã có bước này.

## Sửa lỗi nhanh

- `404 /bookings`: cập nhật nhầm thư mục hoặc Docker còn mã cũ; cập nhật đúng rồi build lại backend.
- `401`: dùng đúng tài khoản khách hoặc admin ở cổng đăng nhập tương ứng.
- `403 Untrusted request origin`: thêm origin frontend vào `TRUSTED_ORIGINS`, tạo lại container; `restart` không đọc lại `.env`.
- `409 Room is fully booked...`: hết phòng ít nhất một đêm; chọn ngày/loại khác.
- Danh sách khách sạn trống: thêm khách sạn và loại phòng từ dashboard; không tự nạp mẫu vào database thật.
- Web deploy không nối được localhost: cần URL HTTPS công khai cho backend.
