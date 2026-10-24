# SmartStay: tải từ GitHub và chạy đầy đủ trên máy cá nhân

Đây là bộ bổ sung cho `SmartStay-Booking-Fullstack.zip` của bạn, gồm `CHAY_DU_AN.py` và tài liệu này. Script sử dụng chính `smartstay-backend/scripts/configure_phase2.py` của dự án để tạo cấu hình riêng trên từng máy.

## 1. Đặt file đúng chỗ

Chép **hai file trong gói bổ sung** vào thư mục `SmartStay-Booking`, cùng cấp với hai thư mục `smartstay-backend` và `quickstay-frontend`. Giữ nguyên các thư mục mã nguồn đang có. Đây là bộ bổ sung, chưa chứa toàn bộ backend/frontend.

Các đường dẫn cần có:

- `SmartStay-Booking/CHAY_DU_AN.py`
- `SmartStay-Booking/HUONG_DAN_GITHUB.md`
- `SmartStay-Booking/smartstay-backend/scripts/configure_phase2.py`
- `SmartStay-Booking/smartstay-backend/.env.example`
- `SmartStay-Booking/quickstay-frontend/.env.example`

## 2. Người tải về cần cài gì?

- Docker Desktop có Docker Compose v2; mở Docker Desktop và chờ Engine chạy. Linux có thể dùng Docker Engine cùng Compose v2.
- Python 3.10 trở lên, lệnh `python` hoặc `py` hoạt động trên Windows.
- Node.js **22.12.0 trở lên**, có `npm`, theo `engines` của dự án.
- Internet để tải image Docker và các gói npm ở lần cài đầu.

Đóng Terminal frontend cũ bằng **Ctrl+C** nếu nó đang chiếm cổng 4173.

## 3. Một lệnh để thiết lập và chạy

Mở Terminal **tại thư mục `SmartStay-Booking`**, chạy:

```powershell
python .\CHAY_DU_AN.py
```

Nếu máy dùng Python Launcher:

```powershell
py .\CHAY_DU_AN.py
```

Trên macOS/Linux: `python3 CHAY_DU_AN.py`.

Script thực hiện lần lượt:

1. Kiểm tra Docker, Node.js và cổng frontend.
2. Tạo `smartstay-backend/.env` từ file mẫu nếu chưa có; sinh ba khóa riêng ngẫu nhiên và mật khẩu admin. Khóa/mật khẩu hợp lệ đã tồn tại được giữ nguyên.
3. Bật cơ chế bootstrap admin `env_only` bằng helper có sẵn. Trên cơ sở dữ liệu mới, backend sẽ tạo tài khoản super-admin đầu tiên.
4. Tạo `quickstay-frontend/.env.local` từ file mẫu nếu chưa có. Mặc định `/api` được Vite chuyển tới `http://127.0.0.1:8001`.
5. Bổ sung quy tắc vào `.gitignore` ở gốc, giữ cấu hình cá nhân và các thư mục phát sinh khỏi Git.
6. Chạy `npm ci`, khởi động Docker Compose và chờ healthcheck tối đa 180 giây sau giai đoạn build.
7. Kiểm tra `/health/ready`, rồi chạy frontend bằng `npm run dev`.

Khi Vite báo sẵn sàng, mở:

| Mục | Địa chỉ |
|---|---|
| Trang khách | http://localhost:4173/#/rooms |
| Dashboard admin | http://localhost:4173/#/admin |
| Tài liệu API | http://localhost:8001/docs |

Đọc `SUPERADMIN_USERNAME` và `SUPERADMIN_PASSWORD` trong **file `.env` trên chính máy đang chạy** để đăng nhập dashboard. Mật khẩu không được ghi cố định trong mã nguồn hoặc in ra Terminal.

Nếu trình duyệt đã lưu lựa chọn `Design preview`, mở phần kết nối, chọn **Live SmartStay API**, nhập **`/api`** và lưu.

## 4. Chỉ tạo cấu hình trước khi đưa mã lên Git

```powershell
python .\CHAY_DU_AN.py --setup-only
```

Chế độ này chỉ cần Python, không chạy Docker/npm. Nó tạo `.env`, `.env.local` và quy tắc `.gitignore`; các bước kiểm tra runtime được thực hiện khi chạy bình thường.

Đưa lên GitHub **mã nguồn, Docker Compose, `.env.example` của cả backend/frontend, script cấu hình, `CHAY_DU_AN.py`, `.gitignore` và tài liệu**. Người clone chạy lại cùng lệnh để có cấu hình riêng.

| File | Đưa lên Git? | Vai trò |
|---|---|---|
| `smartstay-backend/.env.example` | Có | Mẫu chung, chưa chứa mật khẩu/khóa riêng |
| `quickstay-frontend/.env.example` | Có | Mẫu địa chỉ API local |
| `CHAY_DU_AN.py`, các script backend | Có | Tự thiết lập và khởi động |
| `.gitignore` | Có | Quy tắc dùng chung cho người clone |
| `smartstay-backend/.env` | Không | Khóa, tài khoản và cấu hình riêng trên mỗi máy |
| `quickstay-frontend/.env.local` | Không | Thiết lập frontend riêng trên mỗi máy |
| `node_modules`, dữ liệu MongoDB, file upload | Không | Dữ liệu/gói phát sinh ngoài mã nguồn |

Kiểm tra file đã được Git theo dõi hay chưa từ thư mục `SmartStay-Booking`:

```powershell
git ls-files -- smartstay-backend/.env quickstay-frontend/.env.local
```

Không có kết quả nghĩa là hai file đó chưa được theo dõi. Nếu có tên file, bỏ theo dõi đúng các file đó (lệnh này giữ file trên máy):

```powershell
git rm --cached --ignore-unmatch -- smartstay-backend/.env quickstay-frontend/.env.local
```

Kiểm tra quy tắc bỏ qua:

```powershell
git check-ignore -v smartstay-backend/.env quickstay-frontend/.env.local
```

Thêm `.gitignore` không xóa một bí mật đã có trong lịch sử commit. Nếu từng đẩy khóa riêng lên remote, cần thay khóa bị lộ; với `SECRET_KEY` đã dùng mã hóa dữ liệu, cần kế hoạch chuyển đổi dữ liệu trước khi thay. Bộ bổ sung không tự sửa lịch sử Git hoặc tự xoay khóa đang dùng.

Tham khảo: [GitHub — Ignoring files](https://docs.github.com/en/get-started/git-basics/ignoring-files), [Docker Compose — environment variables](https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/).

## 5. “Chạy thật” trong gói này nghĩa là gì?

Frontend gọi FastAPI thật; backend dùng MongoDB replica set, Redis và lưu trữ local có Docker volume. Chức năng đặt phòng hiện có ghi dữ liệu vào MongoDB; dữ liệu không mất chỉ vì đóng tab hoặc tắt rồi mở lại container.

`APP_ENV=development` mô tả môi trường chạy localhost và cho phép origin HTTP. Nó không biến MongoDB thành dữ liệu giả. Script sinh khóa thật cho từng lần cài đặt. Các nội dung mẫu của giao diện/seed đã có trong dự án không bị script này thay đổi.

**Mỗi máy có cơ sở dữ liệu và tài khoản riêng.** Clone Git không chuyển các đơn, ảnh upload hoặc dữ liệu khách hàng trên máy bạn sang máy khác. Người mới có thể thêm khách sạn và loại phòng trong dashboard, rồi đăng ký tài khoản khách riêng để thử luồng đặt phòng.

Đây chưa phải cấu hình triển khai website công khai. Triển khai Internet cần máy chủ, tên miền/HTTPS, cấu hình origin công khai và bảo vệ các dịch vụ dữ liệu. Không chỉ đổi `APP_ENV` sang `production`: backend hiện yêu cầu origin HTTPS ở chế độ đó. Helper của dự án cũng từ chối sửa `.env` production.

React hiện dùng bearer token trong bộ nhớ. Launcher chạy HTTP local và không tự thêm gateway HTTPS; những overlay HTTPS/S3 đã có trong `.env` vẫn được giữ lại. Nếu bạn kiểm tra riêng luồng cookie Secure, dùng hướng dẫn HTTPS giai đoạn 2 của dự án.

## 6. Dùng tiếp và xử lý lỗi

- **Chạy lần sau:** chạy lại `python CHAY_DU_AN.py`. Nó giữ khóa/mật khẩu hợp lệ và các Docker volume đã có. `npm ci` cài lại đúng dependency theo lockfile.
- **Dừng frontend:** Ctrl+C trong Terminal launcher.
- **Dừng backend:** mở Terminal ở `smartstay-backend`, chạy `docker compose stop`.
- **Xem trạng thái:** ở `smartstay-backend`, chạy `docker compose ps -a`.
- **Backend chưa sẵn sàng:** ở `smartstay-backend`, chạy `docker compose logs --tail=80 backend` và xem lỗi cụ thể.
- **Cổng/tên container bị trùng:** kiểm tra tiến trình/container cũ; launcher không tự xóa hoặc dừng ứng dụng khác.
- **Đã có database từ lần cài trước:** dùng `.env` tương ứng với database đó. Backend không đổi mật khẩu tài khoản đang tồn tại chỉ vì sửa `SUPERADMIN_PASSWORD`. Giữ khóa mã hóa đang dùng cho dữ liệu cũ.
- **Đã tùy chỉnh `.env.local`:** launcher giữ file đó. Kiểm tra lại `SMARTSTAY_API_TARGET` và `VITE_SMARTSTAY_API_BASE` nếu muốn đổi backend.

## 7. Phạm vi kiểm tra của bộ bổ sung

Bộ bổ sung được đối chiếu với mã nguồn `SmartStay-Booking-Fullstack.zip` ngày 23/10/2026. Đã kiểm tra thiết lập trên thư mục sạch, khóa khác nhau giữa hai lần cài độc lập, giữ nguyên khóa/cấu hình khi chạy lại, bảo toàn cấu hình frontend tùy chỉnh, quy tắc Git bỏ qua bí mật và trường hợp từ chối `.env` production.

Môi trường tạo bộ bổ sung không có Docker Engine và Windows, nên chưa xác nhận toàn bộ quá trình build/container/khởi động frontend trên máy của bạn. Launcher kiểm tra runtime và hiển thị lỗi thực tế khi chạy. Bộ bổ sung không sửa nghiệp vụ backend/frontend.
