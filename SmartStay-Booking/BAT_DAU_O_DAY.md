# Bắt đầu — SmartStay đã sửa 5 lỗi

Đọc **HUONG_DAN_SUA_5_LOI.md** trước khi cập nhật bản đang chạy. Báo cáo kiểm tra: **KET_QUA_SUA_5_LOI.md**.

## Cập nhật bản cũ

Giải nén bản sửa vào thư mục riêng. Trong `SmartStay-Booking` vừa giải nén:

```powershell
python KIEM_TRA_GOI.py
python AP_DUNG_SUA_5_LOI.py --project "C:\duong-dan\SmartStay-Booking-cu"
```

Công cụ cập nhật cả backend/frontend, sao lưu code cũ và giữ cấu hình cá nhân/dữ liệu. Nếu hai thư mục nằm riêng hoặc khác tên, dùng `--backend` và `--frontend` như hướng dẫn chi tiết.

Sau đó, tại backend **cũ** chạy `docker compose up -d --build backend`; tại frontend **cũ** chạy `npm ci` và `npm run dev`. Đăng nhập lại.

## Chạy mới

Trong thư mục `SmartStay-Booking`:

```powershell
python CHAY_DU_AN.py
```

Cần Python 3.10+, Node.js 22.12+ và Docker Desktop/Compose v2. Tài khoản admin xem trong `.env` riêng trên máy đã cấu hình, không có mật khẩu cố định trong code.

Trang khách: http://localhost:4173/#/rooms

Dashboard: http://localhost:4173/#/admin

Swagger: http://localhost:8001/docs

Nếu thấy Design preview, chọn Live SmartStay API và `/api` trong phần kết nối. Hướng dẫn chi tiết có bước thử đặt phòng bằng hai tab và thử dịch/giọng nói thật.
