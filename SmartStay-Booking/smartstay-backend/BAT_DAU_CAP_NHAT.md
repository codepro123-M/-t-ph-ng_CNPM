# Áp dụng bản sửa cho code hiện tại

Bản này được đối chiếu với `smart-stay-current.zip` bạn gửi ngày 22/10/2026.
Đã sửa lifecycle, kết nối thật MongoDB/Redis/S3, nội dung lưu trú, kiểm duyệt,
delta sync và cleanup media. Có sẵn `scripts/smoke_phase3.py`.

## 1. Giải nén và cập nhật có sao lưu

Lưu các file đang sửa trong VS Code trước. Giải nén ZIP mới vào **một thư mục
riêng**, ví dụ trong Downloads. Không cần thay đổi vị trí dự án cũ đang chạy.
Thư mục vừa giải nén phải có `AP_DUNG_BAN_SUA.py`, `backend`, `scripts` và
`docker-compose.yml`.

Tại File Explorer của thư mục vừa giải nén, gõ `powershell` vào thanh địa chỉ,
nhấn Enter, rồi chạy:

```powershell
python .\AP_DUNG_BAN_SUA.py --project "C:\Users\ACER NITRO 5\Downloads\CNPM\smart-stay-concierge"
```

Công cụ sao lưu các file code sắp bị thay thế vào một thư mục
`smart-stay-code-backup-...` bên cạnh dự án, rồi chép bản sửa vào **dự án cũ**.
Nó giữ `.env`, thông tin Git, môi trường Python, dữ liệu runtime và Docker volume.
Nếu gặp lỗi lúc chép, công cụ khôi phục các file đã thay trong lần chạy đó.
Chế độ xem trước, không ghi file:

```powershell
python .\AP_DUNG_BAN_SUA.py --project "C:\Users\ACER NITRO 5\Downloads\CNPM\smart-stay-concierge" --dry-run
```

Có thể chạy `python .\AP_DUNG_BAN_SUA.py` không truyền tham số rồi chọn thư mục
dự án cũ trong cửa sổ chọn thư mục. Nếu máy không có Tkinter, dùng lệnh có
`--project` ở trên.

## 2. Khởi động bản sửa

Quay về Terminal VS Code của **dự án cũ**. Nếu VS Code báo file đã được thay đổi
từ bên ngoài, tải lại nội dung từ ổ đĩa để xem bản mới. Chạy:

```powershell
docker compose up -d --build
docker compose ps -a
```

Chờ backend healthy. `s3-init` là tác vụ một lần, `Exited (0)` là thành công.
Giữ nguyên tên và vị trí thư mục dự án cũ để Compose tiếp tục dùng các volume
đang có. Không cần tạo lại MongoDB hoặc xóa volume.

Mở http://127.0.0.1:8001/health/ready. Phản hồi phải có:

```json
{
  "status": "ready",
  "mongodb_tx_ready": true,
  "redis_ready": true,
  "media_ready": true,
  "media_backend": "s3"
}
```

Nếu đang dùng backend local, `media_backend` sẽ là `local`. Trong bản sửa, các
cờ readiness lấy từ kiểm tra dịch vụ thật. Có thể xem dấu phiên bản triển khai
tại http://127.0.0.1:8001/compatibility/version; endpoint này chỉ mô tả phiên bản
giao thức, không thay thế `/health/ready`.

## 3. Chạy kiểm tra Giai đoạn 3

```powershell
python scripts/smoke_phase3.py
```

Nếu Python trên Windows báo thiếu httpx:

```powershell
python -m pip install httpx==0.27.2
python scripts/smoke_phase3.py
```

Script kiểm tra readiness và phiên bản backend trước khi đăng nhập, nên phát
hiện được trường hợp chép script mới nhưng vẫn chạy code cũ. Nó đọc
`SUPERADMIN_USERNAME` và `SUPERADMIN_PASSWORD` từ `.env`, không in mật khẩu.
Các dòng PASS bao gồm:

- Ảnh hợp lệ, giới hạn kích thước, bài pending, duyệt bài và thông báo.
- ETag/304, delta sync, hạng phòng, sửa bài qua duyệt và ba tầng fallback.
- Nearby bằng geoNear; có thể báo Haversine nếu truy vấn địa lý lỗi.
- Cách ly chủ nhà, quyền xóa POI, tombstone và cleanup intent.

Script chỉ sửa dữ liệu thử có tên/ID ngẫu nhiên mà nó vừa tạo. Sau kiểm tra, POI
thử bị xóa và tài khoản thử bị vô hiệu hóa; hồ sơ, thông báo và audit vẫn được
giữ. File thử được worker dọn sau thời gian chờ mặc định 24 giờ.

Nếu lỗi, gửi nguyên nội dung terminal và log:

```powershell
docker compose logs --no-color --tail=100 backend
```

## 4. Vì sao phải đồng bộ lại các file?

Bản ZIP cũ có hai bộ router. `main.py` đang dùng `app/routers/*`, đặt sẵn
`mongodb_tx_ready=True`, `redis_ready=True` và không gọi `connect_db()`.
Các helper trong `core/bootstrap.py` ghi vào dictionary `_COLLECTIONS`, bỏ qua
lỗi MongoDB. Các kiểm thử bổ sung chạy được ngay với RAM, không kiểm chứng
transaction hoặc lưu dữ liệu qua lần khởi động lại. Vì thế healthy và 6 test
PASS trước đó chưa phản ánh đúng hạ tầng hoặc nghiệp vụ thực.

Bản sửa dùng một bộ nghiệp vụ trong `app/admin`, `app/owner`, `app/content`.
Các đường import `app/routers/*` được chuyển tiếp về bộ này, không còn một bản
triển khai RAM song song. `core/bootstrap.py` chuyển tiếp tới bootstrap MongoDB;
`core/content_engine.py` chỉ ghi chú vị trí module thay thế, không còn fallback
RAM. Các test cũ được viết lại để chạy qua dịch vụ có kiểm soát database và quyền;
bổ sung bộ test nội dung, test công cụ cập nhật và smoke trên server thật.

Tài khoản super-admin dùng thông tin `.env` hoặc tài khoản đã có trong MongoDB.
Bản sửa không tự tạo tài khoản mẫu cố định. JWT của bản RAM cũ không còn hợp lệ;
đăng nhập lại để tạo phiên mới. Nếu `.env` chưa có tài khoản bootstrap thì chạy
helper phát triển `python scripts/configure_phase2.py` và khởi động lại; helper
giữ các khóa mạnh cùng cấu hình S3 đang có. Xem hướng dẫn Giai đoạn 2 nếu MongoDB
đã có super-admin dưới tên khác, để dùng đúng tài khoản thay vì tạo thêm.

Các bản ghi đã lưu thật trong MongoDB/volume được giữ. Các dữ liệu **chỉ có trong
RAM** của backend cũ không nằm trong ZIP hoặc volume và không được tự chuyển sang
MongoDB. Nếu đã nhập dữ liệu cần giữ trên bản RAM, lưu nội dung đó trước khi khởi
động lại; bản sửa không thể phục hồi dữ liệu RAM sau khi tiến trình đã tắt.

## 5. URL và payload

Các URL chính không có prefix: `/admin/...`, `/owner/...`, `/poi/...`, `/media/...`.
Các alias `/api/v1/admin/...`, `/api/v1/owner/...`, `/api/v1/poi/...` vẫn dùng được.
Swagger hiển thị giao thức chuẩn; các alias được ẩn để tránh danh sách lặp.

| Cách gọi trong bản cũ | Cách dùng trong bản sửa |
|---|---|
| `GET /poi/nearby?lat=...&lng=...&lang=ja` | Vẫn nhận; tên chuẩn là `latitude`, `longitude`, `language` |
| `GET /poi/load-all?lang=ja` | Vẫn nhận; ETag phụ thuộc ngôn ngữ và truy vấn |
| `submission_type`, `target_poi_id`, `poi_data` | Nhận làm alias của `kind`, `poi_id`, `payload` |
| Cập nhật POI hoặc bài sửa | Bổ sung `expected_revision` để chặn ghi đè dữ liệu mới hơn |
| Payload POI `lat/lng` | Nhận alias; `geofence_radius` và `trigger_radius` nếu cùng có phải bằng nhau |
| Ảnh `{url, size_bytes}` | Upload file thật và dùng ID asset; kích thước do server đo |
| `POST /api/v1/owner/poi/{id}/menu-items` | Vẫn dùng được, chuyển đến cùng dịch vụ quản lý hạng phòng |
| `services` của hạng phòng | Nhận alias của `amenities`; giá trả chuỗi Decimal chính xác |
| `GET /poi/{id}/menu` | Vẫn trả `{poi_id, total, items}` |
| `PUT /poi/{id}/localizations` | Chỉ Admin có quyền xuất bản; thêm `source_revision`, dùng `audio_asset_id` |
| `GET /api/v1/admin/rbac/permissions` | Vẫn dùng được; danh mục chuẩn dùng tên quyền dấu chấm như `poi.read` |
| `GET /api/v1/admin/me` | Alias của thông tin phiên hiện tại |
| Đăng nhập `email/password` của bản RAM | Dùng `username/password`, thêm `mode: bearer` nếu gọi qua HTTP |
| Đăng ký chủ `cccd_number` | Giao thức chuẩn yêu cầu `username`, `national_id` và các trường trong Swagger |
| Review hồ sơ `review_note` | Tên chuẩn là `reason` |
| `sync_cursor` dạng timestamp | Cursor mới có chữ ký; dùng trong tham số `cursor`, hoặc dùng `as_of` cho `updated_after` |
| `DELETE /poi/{id}` trả JSON | Thành công trả HTTP 204 không body; theo dõi xóa qua delta và cleanup jobs |

ID mới là MongoDB ObjectId. Các ID dạng `poi_...`, `usr_owner_...` chỉ nằm trong
RAM của bản cũ không tự biến thành ObjectId. Định dạng phản hồi chuẩn được ghi
trong Swagger và `HUONG_DAN_GIAI_DOAN_3.md`; giữ URL alias không có nghĩa giữ mọi
field hoặc cách phân quyền cũ.

Quyền nhập bản dịch yêu cầu quyền Admin để chủ khác không sửa POI ngoài quyền sở
hữu. File MP3 phải upload trước, không dùng URL tùy ý. Khi sửa văn bản nguồn,
bản dịch cũ bị vô hiệu và audio cũ được xếp dọn. Nội dung dịch/TTS hiện được nhập
qua API, chưa tự sinh ở Giai đoạn 3.

## 6. Kiểm thử mã nguồn

Trong dự án đã cập nhật:

```powershell
python -m pip install -r backend/requirements-test.txt
python -m pytest -q
python -m ruff check backend scripts AP_DUNG_BAN_SUA.py
```

Kết quả kiểm tra và phạm vi dịch vụ thật xem `KET_QUA_KIEM_TRA_GIAI_DOAN_3.md`.
Môi trường kiểm tra của bản ZIP không có Docker Engine; việc kiểm tra cuối trên
Docker Windows của bạn thực hiện bằng các bước ở trên.
