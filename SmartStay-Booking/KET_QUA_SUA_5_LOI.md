# Kết quả sửa SmartStay — 25/10/2026

Đối chiếu với `smartstay.zip` người dùng gửi. Bản sửa gồm backend, frontend, công cụ cập nhật và tài liệu. Các kết quả dưới đây được thực hiện trong môi trường kiểm tra độc lập, không truy cập database hay Docker trên máy người dùng.

## Bản vá tiếp nối: Google 429

Sau khi người dùng xác nhận Google trả 429 và MP3 hợp lệ trên Docker của mình, bổ sung chế độ dịch `auto`: Google → MyMemory khi lỗi, cache bản dịch lưu runtime, thời gian chờ nhà cung cấp tồn tại qua khởi động lại, chia đoạn tối đa 500 byte UTF-8 cho MyMemory và báo lỗi hạn mức rõ ràng. Không thay luồng đặt phòng hay giao diện. Xem `HUONG_DAN_SUA_DICH_429.md` để cập nhật và kiểm tra.

Kiểm tra tập trung dịch thuật và phase 4: **22 passed**. Toàn bộ backend sau bản vá: **187 passed**, 3.295 warning deprecation, Python 3.12.14; Ruff đạt. Nguồn nhà cung cấp trong unit test được giả lập. Chưa xác nhận kết nối MyMemory thực từ mạng người dùng; lệnh `integration/check_providers.py` in rõ nhà cung cấp và HIT/MISS để kiểm tra sau khi áp dụng.

## Năm lỗi và thay đổi

| Lỗi | Thay đổi |
|---|---|
| Hai bộ router, lifecycle không kết nối dịch vụ | Dùng một bộ module canonical; khôi phục application factory, kết nối MongoDB/Redis, transaction probe, index, bootstrap theo môi trường, worker và shutdown. Readiness kiểm tra thật thay vì gán True. |
| Frontend/API lệch nhau | Dùng username/password và phiên Bearer thống nhất; gắn auth/bookings; giữ ObjectId, media ID, phân trang/cursor, ngôn ngữ và các URL alias cùng handler. |
| Import thiếu và quyền không đồng bộ | Khôi phục các hàm bảo mật bất đồng bộ, token có issuer/audience/session; một danh mục 34 quyền dấu chấm trong 10 miền; không tạo admin mặc định bằng mật khẩu viết sẵn. |
| Dịch/TTS giả | Gọi nhà cung cấp thật, giới hạn thời gian chờ; cache MP3 có kiểm định ffprobe; gắn bản ghi qua media local/S3 và source revision. Tác vụ lưu MongoDB, có lease/heartbeat, tiến độ, pause/resume/cancel. React tạo/theo dõi/phát bản ghi, xử lý lỗi và lựa chọn giọng trình duyệt riêng. |
| Manifest không khớp | Tạo lại SHA-256 cho toàn bộ backend/frontend/root; thêm kiểm tra gói, cập nhật cả hai phía có sao lưu và rollback; giữ cấu hình riêng. Có `.gitattributes` và công cụ tạo lại manifest sau thay đổi có chủ ý. |

Đồng thời sửa định nghĩa `resolve_safe_path` bị ghi đè bằng kiểm tra tiền tố chuỗi, vô hiệu bản ghi tiếng Việt khi sửa nguồn, giữ đúng tham chiếu media khi dọn file và đặt workflow CI ở gốc dự án full-stack.

## Kiểm tra đã đạt

| Kiểm tra | Kết quả |
|---|---|
| Toàn bộ pytest backend | **187 passed**, Python 3.12.14 (sau bản vá Google 429) |
| Ruff backend/scripts | Đạt |
| Ruff launcher/updater/root tests | Đạt |
| Node tests API/client frontend | **22 passed** |
| React/jsdom | **4 kịch bản đạt**: tạo và tự phát bản ghi, pause/resume/cache; xử lý chặn autoplay; lỗi provider và giọng trình duyệt; hủy yêu cầu và chặn kết quả muộn |
| Build frontend | Vite build thành công |
| Import và cú pháp | 68 module app import thành công; 101 file Python hợp lệ theo cú pháp Python 3.11 |
| Áp dụng bản sửa thực tế | Đã áp dụng lên bản sao ZIP gốc: 173 hash khớp, giữ env/Git/runtime; dry-run của updater cũ cũng hợp lệ |
| Unit tests công cụ cập nhật | **11 passed**: backup hai phía, giữ env, từ chối hash sai trước khi ghi, rollback khi lỗi chép, dry-run, symlink, production env |
| MongoDB thật | MongoDB 7.0.45, Replica Set một node |
| Redis thật | Redis 7.2.6 |
| Đặt phòng đồng thời thật | 12 yêu cầu tranh một phòng: đúng một đơn; 8 lần cùng UUID: cùng một đơn; lỗi audit rollback cả đơn và tồn phòng |
| Client React với API thật | Đăng ký/đăng nhập, sync/chi tiết, báo giá, gửi đơn, chống trùng/vượt phòng, dashboard và xác nhận đơn |
| Lưu dữ liệu | Khởi động lại tiến trình API, đăng nhập lại vẫn có đơn; khách hủy và số phòng được trả lại |
| Readiness thật | Dừng Redis trả 503; khởi động lại Redis phục hồi 200 |
| Dịch vụ giọng nói thật | Edge TTS trả MP3 **13.248 byte**, ffprobe xác nhận hợp lệ; TLS vẫn kiểm tra chứng chỉ và hostname |

Bộ unit dùng MongoDB/Redis giả lập để kiểm tra các nhánh lỗi. Kiểm tra tích hợp ở các dòng MongoDB/Redis/client thật được chạy thêm bằng binary và Uvicorn thực. Kiểm tra React/jsdom giả lập phản hồi API và thao tác media native; không phải kiểm tra trực quan bằng trình duyệt thật. MP3 fixture trong unit được tạo bằng ffmpeg; đây là dữ liệu kiểm thử, không được dùng thay lời thuyết minh trong sản phẩm.

## Phạm vi chưa được xác nhận tại đây

- Google Translate không trả lời trước timeout trong lần thử từ mạng kiểm tra này. Đường gọi HTTP, parser, giới hạn thời gian chờ, TLS, nhánh dịch thành công/lỗi, lưu kết quả và tích hợp frontend đã được kiểm thử bằng provider giả lập. Không khẳng định đã dịch thành công qua mạng thực tại đây. Có `integration/check_providers.py` để kiểm tra lại từ Docker/mạng của người dùng.
- Không có Docker Engine trong môi trường kiểm tra; chưa trực tiếp build/chạy container hoặc chạy GitHub Actions của bản này. Đã chạy API, Replica Set và Redis thật ngoài Docker. Dockerfile dùng Python 3.11; source được kiểm tra cú pháp tương thích Python 3.11, pytest tại đây chạy Python 3.12.
- Probe S3 và luồng media S3 có kiểm thử SDK; đợt kiểm tra tích hợp mới này dùng media local. Khi dùng S3 hiện có, chạy smoke của dự án trên Docker của mình.
- Các warning deprecation từ thư viện kiểm thử không làm kiểm thử thất bại.

Các báo cáo giai đoạn 2/3 trong backend là lịch sử của các bản trước. Với bản này, ưu tiên báo cáo hiện tại và `HUONG_DAN_SUA_5_LOI.md`.
