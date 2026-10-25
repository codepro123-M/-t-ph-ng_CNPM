# QuickStay — khách hàng và dashboard SmartStay

Bản sửa 25/10/2026: đọc `../HUONG_DAN_SUA_5_LOI.md` để cập nhật cả hai phía có sao lưu. Kết quả mới nhất ở `../KET_QUA_SUA_5_LOI.md`.

React kết nối FastAPI/MongoDB để đặt phòng thật. Dùng kèm backend trong gói SmartStay-Booking; backend giai đoạn 1–3 cũ chưa có API đặt phòng.

## Chạy trong VS Code

Cần Node.js 22.12 trở lên. Terminal trong `quickstay-frontend`:

```powershell
npm install
Copy-Item .env.example .env.local
npm run dev
```

Dừng frontend cũ bằng Ctrl+C nếu đang chiếm cổng 4173.

- Trang khách: http://localhost:4173/#/rooms
- Đơn của khách: http://localhost:4173/#/bookings
- Dashboard: http://localhost:4173/#/admin

Backend chạy ở http://localhost:8001. `.env.local`:

```dotenv
SMARTSTAY_API_TARGET=http://127.0.0.1:8001
VITE_SMARTSTAY_API_BASE=/api
```

Khởi động lại frontend sau khi sửa cấu hình. Nếu trình duyệt đã lưu chế độ demo từ bản cũ: nhấn Design preview hoặc nút kết nối cuối trang, chọn Live SmartStay API, nhập `/api` và lưu. Vite bỏ tiền tố `/api` rồi chuyển tiếp request sang backend. Demo chỉ lưu đơn mẫu ở trình duyệt; Live gửi và đọc đơn thật từ MongoDB.

## Thử bằng hai tab

1. Dashboard: đăng nhập tài khoản admin đã tạo ở backend giai đoạn 2. Tài khoản khách không có quyền quản trị.
2. Chọn Properties & rooms / Khách sạn & phòng, thêm khách sạn, loại phòng, giá, số khách/phòng và số lượng phòng thực tế. Khách sạn đã có nhưng thiếu phòng: chọn Add room type.
3. Tab khách: đăng ký/đăng nhập tài khoản khách riêng, chọn khách sạn và ngày, kiểm tra phòng trống rồi gửi đặt phòng với thông tin liên hệ.
4. My Bookings hiện mã `SS-...`, tổng tiền và trạng thái Pending / Chờ xác nhận. Đơn đã được lưu vào MongoDB.
5. Dashboard tự lấy đơn mới mỗi 5 giây khi tab đang mở. Xem chi tiết, lọc/tìm đơn và xác nhận/hủy.
6. My Bookings tự cập nhật trạng thái. Hủy đơn sẽ mở lại số phòng.
7. Tải lại trang rồi đăng nhập lại cùng tài khoản: đơn vẫn còn.

Access/refresh token chỉ nằm trong bộ nhớ. Client tự làm mới access token trong phiên đang mở; tải lại trang cần đăng nhập lại. Phiên khách và admin tách biệt.

## API

| Chức năng | API |
|---|---|
| Nội dung/đa ngôn ngữ | `GET /poi/load-all`, `GET /poi/{id}` |
| Đăng ký/đăng nhập khách | `POST /api/v1/auth/register`, `POST /api/v1/auth/session` |
| Tạo bản dịch/giọng nói | `POST /localizations/on-demand`, `GET /localizations/poi/{id}/status` |
| Kiểm tra theo ngày | `GET /bookings/availability` |
| Gửi đơn, xem đơn cá nhân | `POST /bookings`, `GET /bookings`, `GET /bookings/{id}` |
| Khách hủy đơn | `PATCH /bookings/{id}/cancel` |
| Đăng nhập admin | `POST /admin/auth/login` |
| Danh sách/lọc/tìm đơn | `GET /admin/bookings` |
| Xác nhận/hủy/hoàn thành | `PATCH /admin/bookings/{id}` |
| Thêm khách sạn/loại phòng | `POST /poi`, `POST /admin/menu-items` |

Một yêu cầu đặt một phòng, 1–30 đêm, nhận phòng trong vòng 365 ngày. `inventory` là số lượng phòng của một loại phòng; dữ liệu cũ thiếu trường này mặc định 1. `capacity` là số khách tối đa mỗi phòng. Đơn chờ/đã xác nhận đều giữ phòng; chưa tự hết hạn đơn chờ. Giá tính ở backend bằng Decimal. Giao dịch MongoDB và số lượng theo từng đêm ngăn đặt vượt phòng; UUID `request_id` tránh đơn trùng khi thử lại; `expected_revision` chống ghi đè trạng thái cũ.

## Cho khách truy cập Internet

Cần triển khai cả frontend và backend. Backend cần URL HTTPS công khai, MongoDB replica set và Redis. Website HTTPS không gọi được backend `http://localhost:8001` trên máy bạn.

Dùng `VITE_SMARTSTAY_API_BASE=https://api.ten-mien-cua-ban.com` và build lại, hoặc đặt URL trong phần kết nối trên web. Thêm origin HTTPS của frontend vào `TRUSTED_ORIGINS`, giữ các origin cũ và tạo lại container backend để đọc môi trường mới. Giữ nguyên quyền truy cập website đã triển khai cho tới khi bạn chọn mở công khai.

## Phạm vi

- Đơn được lưu thật. Chưa có thanh toán trực tuyến, email xác nhận hoặc hoàn tiền; khách thanh toán trực tiếp với khách sạn. Thống kê là số đơn, không phải tiền đã thu.
- Dashboard dành cho admin có `booking.read` / `booking.update`; chưa có màn hình đơn riêng theo từng chủ khách sạn.
- Lượt QR/truy cập/nghe chưa có API ghi nhận.
- Thuyết minh gửi tác vụ tạo bản dịch/MP3 đúng ngôn ngữ, theo dõi tiến độ và phát media backend. Có nút chọn giọng trình duyệt khi dịch vụ ngoài lỗi.
- Ưu đãi/đánh giá/newsletter trang giới thiệu vẫn là nội dung mẫu.

## Kiểm tra

```powershell
npm test
npm run build
```

22 kiểm tra API/client và 4 kịch bản giao diện React bao gồm hợp đồng API, đồng bộ nội dung, bearer token, làm mới phiên đồng thời, truy vấn phòng/ngày và lỗi tồn phòng. Trình duyệt thử bằng dữ liệu kiểm thử độc lập. Kiểm tra đồng thời/rollback MongoDB thật nằm trong backend.

## Nguồn thiết kế

QuickStay Figma người dùng cung cấp: https://www.figma.com/design/vWAjka7MDKh3QWfvERF6Mx/QuickStay?node-id=0-1. Figma plugin báo thiếu quyền chỉnh sửa nên chưa xác minh từng lớp/pixel. Bố cục tham chiếu từ ảnh người dùng và QuickStay của GreatStack. Ảnh hero/logo/ưu đãi từ `https://hb-gs.vercel.app/`, ảnh phòng từ tài nguyên công khai `shantanulanjewar12/Quickstay-hotel-booking-system`, chân dung mẫu từ Unsplash, font Outfit và Playfair Display từ Google Fonts. Tài nguyên lưu cục bộ.
