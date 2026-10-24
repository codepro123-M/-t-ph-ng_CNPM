# Kết quả kiểm tra Giai đoạn 3

Ngày kiểm tra: **22/10/2026**. Bản sửa được đối chiếu với `smart-stay-current.zip`
người dùng gửi. Kiểm tra trên môi trường Linux độc lập. Chưa build/chạy bản sửa
trên Docker Windows của người dùng.

| Hạng mục | Kết quả |
|---|---|
| Pytest unit và regression | **152 passed**: 105 kiểm thử nền, 37 kiểm thử nội dung, 7 kiểm thử tương thích thay bộ test RAM và 3 kiểm thử công cụ cập nhật; Python 3.12.14 |
| Ruff backend và scripts | Đạt |
| Docker Compose config | Đạt với local + HTTPS và S3 + HTTPS bằng CLI 5.6.1; hai helper cấu hình chạy lặp vẫn hợp lệ |
| MongoDB thật | 7.0.45, Replica Set một node, startup transaction và chỉ mục 2dsphere thành công |
| Redis thật | 6.2.14 từ binary kiểm thử; Compose dự án dùng Redis 7 |
| S3 thật | RustFS 1.0.3, có kiểm tra bucket bật versioning |
| HTTPS thật | Caddy 2.11.7, HTTP client xác minh CA nội bộ |
| Schema POI | Tiếng Việt, tọa độ hợp lệ, GeoJSON lon/lat, bán kính mặc định 30 m, audio priority, giới hạn ảnh |
| Ảnh | PNG thật, tên file không thành đường dẫn, riêng tư trước duyệt, công khai sau duyệt, 9 ảnh và ảnh quá 5 MiB bị chặn |
| Owner submissions | Chủ chưa duyệt bị chặn; bài pending không công khai; Admin duyệt tạo POI và thông báo; chủ khác không đọc/sửa được |
| Kiểm soát chỉnh sửa | Revision cũ bị từ chối; chủ không bỏ qua duyệt bằng PATCH POI; thao tác duyệt lặp bị chặn |
| Hạng phòng/dịch vụ | CRUD theo POI, quyền sở hữu, giá chuỗi Decimal chính xác, cập nhật dataset |
| Ba tầng fallback | Đúng ngôn ngữ → tiếng Anh → nguồn Việt và audio null; dùng cùng logic cho load-all/nearby |
| Bản dịch và audio | Nhập bản dịch theo source_revision; sửa văn bản nguồn vô hiệu bản cũ; MP3 thật được ffprobe kiểm tra và phát qua S3/HTTPS |
| Geo | MongoDB `$geoNear` thật; bỏ chỉ mục trên database thử để ép Haversine, tập POI khớp |
| ETag | Cùng representation trả 304 không body; tách ngôn ngữ; CORS expose header |
| Delta | Checkpoint, timestamp có múi giờ, POI thay đổi, tombstone xóa/ẩn, cursor sai/hết hạn/reset |
| Phân trang khi dữ liệu đổi | Đang tải thì sửa/xóa/thêm POI: các trang giữ snapshot cũ, delta tiếp theo nhận đủ thay đổi |
| Ghi đồng thời | Bốn request tạo POI cùng lúc đều thành công; dataset tăng đúng bốn version nhờ retry transaction |
| Xóa toàn vẹn | POI + menu_items + poi_localizations, hủy bài pending, thông báo, audit, tombstone và cleanup intent |
| Rollback thật | MongoDB từ chối audit khi xóa: POI, hạng phòng, bản dịch, version và cleanup intent đều giữ nguyên |
| Worker media thật | Đặt tác vụ thử đến hạn, worker xóa ảnh/MP3 cùng version S3; không còn object version hoặc delete marker của media thử |
| Worker media unit | File local có tham chiếu được giữ; file không còn tham chiếu được xóa; lỗi được giữ để retry |
| Lưu qua khởi động lại | Dừng hẳn tiến trình Uvicorn, khởi động lại, POI trả đúng dữ liệu trước đó; phiên và URL alias vẫn dùng được |
| Readiness thực | Dừng S3 trả 503, khôi phục S3 trở lại 200; dừng Redis trả 503; MongoDB không sẵn sàng thì startup thất bại |
| Tương thích API | URL `/api/v1`, query lat/lng/lang, payload bài gửi cũ, menu và catalog; chặn chủ khác sửa và chặn nhập URL media chưa quản lý |
| Áp dụng cập nhật | Sao lưu code, giữ `.env`/Git/runtime, chặn symlink ra ngoài, dry-run không ghi; áp dụng thử thành công lên bản sao ZIP gốc |
| Hồi quy Giai đoạn 2 thật | Roles/32 quyền, nâng cấp tài khoản cũ, cookie Secure/HttpOnly, CSRF, refresh rotation/reuse, audit rollback, PII hết hạn được purge |

Các unit test dùng MongoDB/Redis giả lập, đọc/ghi file local thật, bcrypt/JWT/Fernet
thật. Luồng tích hợp chạy thêm bằng MongoDB, Redis, RustFS, Caddy và Uvicorn thật
trong database/bucket/thư mục tạm. Chúng không truy cập môi trường Windows của
người dùng. Kiểm thử audio unit có trường hợp thay bước nhận dạng audio bằng giả
lập; tích hợp bổ sung dùng MP3 do ffmpeg tạo và ffprobe thực.

Toàn bộ Python source đã được parse theo cú pháp Python 3.11. Môi trường kiểm tra không có Docker Engine, nên chưa thực hiện build image hoặc
chạy container của ZIP này ở đây. Dockerfile dùng Python 3.11; kiểm thử unit cục
bộ dùng Python 3.12.14. Cấu hình Compose được kiểm tra riêng bằng CLI; workflow
GitHub Actions đã bổ sung smoke Giai đoạn 3 cho local và S3, nhưng chưa có kết quả
chạy Actions của phiên bản mới. Chạy `python scripts/smoke_phase3.py` sau khi
rebuild để xác nhận trên Docker của bạn.

Pytest có cảnh báo deprecation từ Starlette/AnyIO và mongomock trên Python 3.12;
không có kiểm thử thất bại.

## Phạm vi và giới hạn

- Bản gốc có hai bộ router và `main.py` dùng bộ RAM, đặt readiness sẵn thành
  true. Bản sửa kết nối dịch vụ thật, loại bỏ fallback RAM và đưa các đường
  import cũ về một bộ nghiệp vụ. Chi tiết thay đổi payload/tài khoản và cách áp
  dụng có sao lưu nằm trong `BAT_DAU_CAP_NHAT.md`.
- Dữ liệu đã ghi MongoDB/volume được giữ. Bản ghi chỉ nằm trong RAM của tiến
  trình cũ không có trong ZIP và không được tự di chuyển hoặc phục hồi.

- Hoàn thiện backend/API của các hạng mục Giai đoạn 3; chưa có giao diện chủ nhà,
  Admin hoặc ứng dụng du khách.
- Bản dịch và MP3 được nhập qua API để kiểm tra hydration. Chưa có dịch tự động,
  sinh TTS hoặc tự phát theo GPS trên thiết bị.
- Hạng phòng có nguồn tiếng Việt; chưa dịch các tên/mô tả hạng phòng.
- `content_changes` giữ lịch sử snapshot, chưa có tác vụ nén/xóa lịch sử. Media
  được dọn bất đồng bộ sau thời gian chờ mặc định 24 giờ, không xóa file ngay khi
  DELETE POI trả về.
- Dữ liệu phòng/bài đăng thử từ Giai đoạn 2 được giữ riêng; không tự đoán POI để
  chuyển chúng sang collection Giai đoạn 3.
- Fallback địa lý vẫn cần đọc được MongoDB. Đổi endpoint/backend lưu trữ cần kế
  hoạch di chuyển media; cập nhật cấu hình không tự di chuyển file.

Hướng dẫn áp dụng và thử từng API: `HUONG_DAN_GIAI_DOAN_3.md`.
