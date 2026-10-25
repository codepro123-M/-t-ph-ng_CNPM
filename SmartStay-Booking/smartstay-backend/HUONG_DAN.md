# SmartStay Concierge API

Bản 25/10/2026 dùng một bộ nghiệp vụ trong `app/auth`, `app/admin`, `app/owner`, `app/content`, `app/bookings`, `app/audio`, `app/localization` và `app/ui_i18n`. `app/routers/*` chỉ là đường import chuyển tiếp, không có backend RAM song song.

Hướng dẫn cập nhật và chạy full-stack: `../HUONG_DAN_SUA_5_LOI.md`. Kết quả kiểm tra bản này: `../KET_QUA_SUA_5_LOI.md`. Các hướng dẫn giai đoạn 2/3/S3 trong thư mục này mô tả các API nền và lịch sử triển khai.

Backend kết nối MongoDB Replica Set và Redis trong lifespan, tạo index, bootstrap theo `.env`, kiểm tra media và khởi động worker. Readiness kiểm tra dịch vụ thật. React dùng username/password và Bearer; cookie Secure vẫn có CSRF và HTTPS cho luồng kiểm tra riêng.

Chạy mới bằng launcher ở thư mục cha: `python CHAY_DU_AN.py`. Giữ `.env` và volume khi cập nhật. Với bản đã cấu hình: `docker compose up -d --build backend`.

- Swagger: http://localhost:8001/docs
- Readiness: http://localhost:8001/health/ready
- Trang khách: http://localhost:4173/#/rooms
- Dashboard: http://localhost:4173/#/admin

Đăng nhập lại sau khi cập nhật. Tài khoản admin thuộc `admin_users`; khách đăng ký thuộc `auth_users`. Danh mục dùng 34 quyền dấu chấm trong 10 miền, gồm `booking.read` và `booking.update`. Bootstrap không đặt lại mật khẩu đã lưu.

Dịch và TTS sử dụng dịch vụ bên ngoài thực. Chạy `docker compose exec -T backend python integration/check_providers.py` để kiểm tra kết nối từ mạng của mình. Khi dịch vụ lỗi, trạng thái là lỗi; không báo bản ghi giả là sẵn sàng.
