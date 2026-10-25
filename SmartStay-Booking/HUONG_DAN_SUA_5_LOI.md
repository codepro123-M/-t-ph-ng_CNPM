# SmartStay — bản sửa 5 lỗi, ngày 25/10/2026

Bản này thống nhất backend FastAPI, frontend React và công cụ cập nhật. Đọc `KET_QUA_SUA_5_LOI.md` để biết các kiểm tra đã chạy và giới hạn kiểm chứng dịch vụ bên ngoài.

## 1. Cập nhật dự án cũ đang có dữ liệu

Giải nén ZIP này vào **một thư mục riêng**. Dừng frontend bằng Ctrl+C và lưu các file đang sửa trong VS Code. Mở Terminal trong thư mục `SmartStay-Booking` của **bản vừa giải nén**.

Kiểm tra toàn bộ gói trước:

```powershell
python .\KIEM_TRA_GOI.py
```

Nếu dự án cũ có đúng hai thư mục `smartstay-backend` và `quickstay-frontend`, chạy (thay đường dẫn ví dụ bằng đường dẫn thực):

```powershell
python .\AP_DUNG_SUA_5_LOI.py --project "C:\duong-dan\SmartStay-Booking-cu"
```

Nếu backend và frontend nằm riêng, hoặc frontend cũ tên `quickstay-react`, chỉ rõ từng thư mục:

```powershell
python .\AP_DUNG_SUA_5_LOI.py --backend "C:\duong-dan\backend-cu" --frontend "C:\duong-dan\quickstay-react"
```

Có thể thêm `--dry-run` để chỉ kiểm tra, chưa chép file. Công cụ kiểm tra hash của **cả frontend và backend trước lần ghi đầu tiên**, sao lưu file sắp thay trong `repair-backups`, chép file nguyên tử và khôi phục file đã thay nếu gặp lỗi chép. Bản sao lưu chứa `.env`, hãy giữ riêng trên máy mình.

Công cụ giữ khóa/mật khẩu, cấu hình S3 và các giá trị khác trong `.env`, giữ `.env.local`, Git và dữ liệu Docker. Trong môi trường phát triển, nó chỉ bổ sung origin localhost cổng 4173 nếu thiếu. Không cần xóa database/volume để cập nhật.

Bản cũ có bộ lưu RAM: dữ liệu chỉ tồn tại trong tiến trình đó không nằm trong ZIP hoặc volume MongoDB. Nếu còn nội dung cần giữ ở bản RAM đang chạy, lưu/xuất nội dung đó trước khi rebuild. Bản sửa giữ dữ liệu đã lưu MongoDB; không thể khôi phục RAM của tiến trình đã tắt.

Sau khi cập nhật, quay về Terminal của **backend cũ**:

```powershell
docker compose up -d --build backend
docker compose ps -a
```

Ở Terminal của **frontend cũ**:

```powershell
npm ci
npm run dev
```

Giữ cách bật overlay S3/HTTPS hiện tại. Khi VS Code báo file thay đổi từ bên ngoài, tải lại file từ ổ đĩa. Đăng nhập lại trên website sau cập nhật để nhận phiên và quyền mới.

## 2. Chạy một bản mới tải từ Git

Cần Docker Desktop/Engine có Compose v2, Python 3.10+ và Node.js 22.12+. Mở Terminal trong thư mục `SmartStay-Booking` rồi chạy:

```powershell
python .\CHAY_DU_AN.py
```

Launcher tạo cấu hình riêng, sinh khóa và tài khoản admin khi cần, chạy Docker và frontend. Đọc `SUPERADMIN_USERNAME`/`SUPERADMIN_PASSWORD` trong `.env` trên chính máy đó. Backend lấy tài khoản từ MongoDB và cấu hình bootstrap; không có tài khoản admin mẫu cố định.

Nếu database đã có admin, dùng tài khoản đang tồn tại. Đổi `SUPERADMIN_PASSWORD` trong `.env` không tự đặt lại mật khẩu tài khoản đã lưu.

## 3. Kiểm tra bằng hai tab

- Trang khách: `http://localhost:4173/#/rooms`.
- Dashboard: `http://localhost:4173/#/admin`.
- Swagger: `http://localhost:8001/docs`.
- Readiness: `http://localhost:8001/health/ready`.

Readiness trả `ready` khi kiểm tra MongoDB Replica Set, Redis và media đạt; có `media_ready`, `media_backend` và `mounted_routers: 12`.

Trong dashboard, dùng tài khoản admin, thêm khách sạn và loại phòng: giá 650000 VND, sức chứa 2, số phòng thực tế 1. Ở tab khách, đăng ký tài khoản khách riêng, chọn hai đêm trong tương lai rồi đặt phòng. Đơn hiện ở cả hai phía. Admin xác nhận; trang đơn của khách tự cập nhật sau khoảng 5 giây khi đang hiển thị. Thử đặt trùng đêm sẽ báo hết phòng. Hủy đơn sẽ trả lại số lượng phòng.

Nếu trình duyệt còn lưu Design preview, mở phần kết nối ở cuối trang, chọn Live SmartStay API, nhập `/api` và lưu. Trên localhost, Vite chuyển `/api` sang backend cổng 8001.

## 4. Dịch và thuyết minh thật

Ở chi tiết khách sạn, chọn Việt/Anh/Trung/Nhật/Hàn rồi nhấn Nghe. Nếu chưa có bản ghi đúng ngôn ngữ, frontend gửi yêu cầu tạo, theo dõi trạng thái và lấy lại nội dung sau khi xong. Backend gọi Google Translate thông qua adapter của `deep-translator`, gọi `edge-tts` 7.3.1, kiểm định MP3 bằng ffprobe rồi lưu qua cùng hệ thống media local/S3. Lần sau dùng lại bản ghi đã lưu.

Tác vụ được lưu trong MongoDB, có trạng thái, tiến độ, heartbeat và lease. Khi API dừng giữa chừng, tác vụ có thể được tiếp tục sau khi khởi động lại. Khi dịch vụ dịch/giọng nói lỗi, API ghi trạng thái lỗi; không tạo văn bản gắn nhãn giả hoặc MP3 giả. Người dùng có thể chủ động chọn giọng đọc trình duyệt cho nội dung đang hiển thị.

Dịch vụ bên ngoài cần Internet và chuỗi chứng chỉ được hệ điều hành tin cậy. Code giữ kiểm tra chứng chỉ/hostname, không tắt TLS. Nếu trình duyệt chặn tự phát sau khi đợi lâu, nhấn Nghe thêm một lần khi bản ghi báo sẵn sàng.

Kiểm tra trực tiếp từ container backend:

```powershell
docker compose exec -T backend python integration/check_providers.py
```

Lệnh dùng một câu thử không có thông tin cá nhân; báo riêng kết quả dịch và sinh MP3. Nếu Google/Microsoft bị chặn hoặc không phản hồi, kiểm tra mạng của Docker/máy chủ rồi thử lại. Không cần đổi khóa JWT hay xóa database để xử lý lỗi mạng nhà cung cấp.

Một số API thuyết minh:

| API | Công dụng |
|---|---|
| `POST /localizations/on-demand` | Công khai cho POI đã công bố; body `{poi_id, lang}`; 202 nếu đang tạo, 200 nếu đã có |
| `GET /localizations/poi/{id}/status?lang=en` | Trạng thái đã tạo/đang tạo/lỗi |
| `POST /admin/audio-tasks` | Admin có quyền xuất bản tạo tác vụ theo danh sách ngôn ngữ |
| `GET /admin/audio-tasks` | Danh sách tác vụ |
| `POST /admin/audio-tasks/{id}/pause`, `/resume`, `/cancel` | Điều khiển tác vụ |
| `GET /admin/audio-tasks/stream` | SSE snapshot, cập nhật và heartbeat |
| `GET /audio/pack-manifest?lang=en` | Manifest SHA-256 của bản ghi đã công bố |

Có thể tạo POI bằng `POST /poi?auto_run_tts=true&activation_requested=true` để giữ ở trạng thái chưa công bố đến khi bản tiếng Anh sẵn sàng. Phản hồi vẫn là POI chuẩn có `id`, thêm `audio_task_id`. Tạo POI thông thường không bị buộc chờ dịch vụ bên ngoài.

## 5. Kiểm tra mã nguồn

Tại `smartstay-backend`:

```powershell
python -m pip install -r backend/requirements-test.txt
python -m pytest -q
python -m ruff check backend scripts AP_DUNG_BAN_SUA.py
docker compose exec -T backend python integration/check_booking_replica.py
```

Kiểm thử MP3 cần ffmpeg/ffprobe. Dockerfile đã cài sẵn. Nếu chạy pytest trên Windows trực tiếp, cài ffmpeg và thêm thư mục `bin` vào PATH trước.

Tại `quickstay-frontend`: `npm test`, `npm run build`.

Tại `SmartStay-Booking`: `python -m unittest discover -s tests -v` và `python KIEM_TRA_GOI.py`.

`.gitattributes` giữ source ở LF trên Windows/Linux để hash không thay đổi do Git tự đổi xuống dòng. Không chỉnh mã nguồn trong gói trước khi chạy updater; nếu đã sửa riêng, hợp nhất thay đổi rồi chạy `python TAO_MANIFEST.py` để tạo manifest cho chính bản đã duyệt đó.

Bản này chưa bổ sung thanh toán online, email xác nhận, thống kê QR/lượt nghe hoặc ứng dụng React Native. Các phần đó nằm ngoài 5 lỗi đang sửa.
