# Bắt đầu — SmartStay đặt phòng thật

Gói gồm toàn bộ backend cập nhật, React cho khách và dashboard quản trị. ZIP chưa tự thay mã trên máy bạn; thực hiện các bước sau.

## 1. Cập nhật backend cũ

Giải nén bằng **Extract All / Giải nén tất cả**. Mở thư mục SmartStay-Booking trong VS Code, mở Terminal:

```powershell
python .\AP_DUNG_DAT_PHONG.py
```

Nếu máy dùng Python Launcher, thay `python` bằng `py`. Khi được hỏi, dán đường dẫn backend **cũ** đang có `docker-compose.yml`, `.env` và thư mục `backend`.

Script kiểm tra file, sao lưu mã cũ ở `booking-backups`, giữ dữ liệu MongoDB/Redis/S3 và các khóa/mật khẩu/cấu hình khác. Trong môi trường phát triển, `.env` chỉ được thêm origin localhost cổng 4173.

Terminal tại backend cũ:

```powershell
docker compose up -d --build backend
docker compose ps
```

Nếu dùng file Compose S3/HTTPS riêng, giữ cách thêm `-f`/`COMPOSE_FILE` hiện tại. Chờ backend healthy. Kiểm tra http://localhost:8001/health/ready và http://localhost:8001/docs: phải có nhóm bookings. Không cần xóa database.

## 2. Chạy frontend mới

Dừng frontend cũ bằng **Ctrl+C** để nhường cổng 4173. Mở thêm thư mục `quickstay-frontend` trong VS Code, Terminal tại đó:

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Cần Node.js 22.12 trở lên. Nếu trình duyệt vẫn lưu Design preview: mở nút đó hoặc nút kết nối cuối trang, chọn Live SmartStay API, nhập `/api`, lưu.

## 3. Test bằng hai tab

**Tab admin:** http://localhost:4173/#/admin. Dùng admin đã tạo ở giai đoạn 2, tương ứng `SUPERADMIN_USERNAME` của backend. Tài khoản đăng ký ở trang khách không dùng cho dashboard. Chọn Properties & rooms / Khách sạn & phòng, thêm khách sạn và một loại phòng, ví dụ:

- Tên: Khách sạn thử nghiệm SmartStay; loại hình Hotel.
- Địa chỉ: Quận 1, TP. Hồ Chí Minh; giới thiệu tiếng Việt.
- Vĩ độ `10.7769`, kinh độ `106.7009`.
- Loại phòng Deluxe Double; giá `650000` VND/đêm.
- Số khách/phòng `2`, số phòng thực tế `1`.

**Tab khách:** http://localhost:4173/#/rooms. Bấm Login, đăng ký và đăng nhập tài khoản khách riêng. Chọn khách sạn, ngày tương lai, kiểm tra phòng trống, điền thông tin liên hệ rồi gửi đơn.

Kết quả cần thấy:

1. My Bookings có mã `SS-...`, giá và trạng thái chờ xác nhận.
2. Dashboard tự hiện đơn sau khoảng 5 giây khi tab mở. Chi tiết có tên, điện thoại/email/ghi chú, loại phòng, ngày ở và tổng tiền.
3. Admin xác nhận; My Bookings tự đổi trạng thái.
4. Loại phòng số lượng 1 sẽ báo hết nếu đơn khác chọn trùng đêm.
5. Hủy đơn sẽ mở lại phòng và cập nhật trạng thái ở dashboard.
6. Tải lại trang, đăng nhập lại cùng tài khoản: đơn vẫn còn trong MongoDB.

Token chỉ giữ trong bộ nhớ, nên tải lại trang cần đăng nhập lại; dữ liệu đơn không mất.

## 4. Khách ở máy khác

Để truy cập Internet, phải triển khai backend cùng MongoDB replica set/Redis trên máy chủ HTTPS và cấu hình URL đó cho frontend. `localhost` chỉ dùng trên máy đang chạy dự án. Gói cập nhật không tự đưa Docker trên máy bạn lên Internet.

Chưa có thanh toán online, email xác nhận hay đếm lượt QR/nghe. Khách thanh toán với khách sạn; dashboard hiện số đơn/trạng thái.

## Nội dung

- `quickstay-frontend`: toàn bộ React, CSS, ảnh/font, tests, README.
- `smartstay-backend`: backend, Docker Compose, tests, CI, hướng dẫn đặt phòng.
- `AP_DUNG_DAT_PHONG.py`: cập nhật các file backend thay đổi, có sao lưu.
- `UPDATE_MANIFEST.json`: danh sách và SHA-256 file cập nhật.

Đã qua 166 kiểm tra backend, 20 kiểm tra frontend và build. Kiểm tra MongoDB thật xác nhận không đặt vượt phòng, lặp UUID không trùng đơn, lỗi audit rollback. Trình duyệt đã thử tạo khách sạn, gửi đơn, dashboard nhận/xác nhận và tự cập nhật trạng thái bằng dữ liệu kiểm thử độc lập.
