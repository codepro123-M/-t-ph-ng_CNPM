# Giai đoạn 2 — Xác thực, RBAC và API dành cho chủ lưu trú

Bản này bổ sung phần backend/API của Giai đoạn 2 trên nền MongoDB Replica Set, Redis và S3 đã chạy ở Giai đoạn 1. Chưa có giao diện web đăng nhập hoặc dashboard; có thể kiểm tra mọi API bằng Swagger, PowerShell hoặc HTTP client.

## 1. Đưa bản mới vào VS Code trên Windows

1. Giải nén toàn bộ ZIP vào thư mục dự án hiện tại, nơi có `docker-compose.yml`, chọn thay thế các file cùng tên. Giữ file `.env` và các Docker volume đang dùng; ZIP không chứa `.env` thật.
2. Trong Terminal của VS Code, đứng ở thư mục dự án và chạy:

```powershell
python scripts/configure_phase2.py
docker compose up -d --build
docker compose ps -a
```

Nếu máy chỉ nhận lệnh `py`, thay `python` bằng `py`. Helper dùng thư viện chuẩn, không cần cài pip trên Windows. Helper tạo các khóa còn dùng giá trị mẫu, tạo thông tin super-admin và bật cổng HTTPS cục bộ. Các khóa mạnh đang có, cấu hình S3, MongoDB và Redis được giữ nguyên. Chạy helper lần nữa sẽ không đổi khóa hay mật khẩu đã tạo.

3. Mở `.env` trên máy mình để đọc `SUPERADMIN_USERNAME` và `SUPERADMIN_PASSWORD`. Không gửi hai giá trị này hoặc nội dung `.env` lên chat. Thông thường tên tài khoản mới là `superadmin`; mật khẩu được sinh ngẫu nhiên riêng cho máy.
4. Kiểm tra [health/ready](http://127.0.0.1:8001/health/ready) có `status: ready`. Backend và gateway phải healthy; `s3-init` kết thúc với mã 0 là bình thường.

**Không chạy `docker compose down -v` trên dữ liệu đang dùng.** Khi nâng cấp, tài khoản người dùng cũ trong `auth_users` được giữ lại. Phiên JWT từ bản cũ sẽ cần đăng nhập lại. Đừng đổi `SECRET_KEY` sau khi đã nhận CCCD; thay khóa sẽ khiến dữ liệu cũ không thể giải mã. Bootstrap không ghi đè mật khẩu tài khoản đã tồn tại; sửa `SUPERADMIN_PASSWORD` trong `.env` sau đó không phải là thao tác đổi mật khẩu trong database.

## 2. Kiểm tra nhanh bằng Swagger ở cổng HTTP đang dùng

Mở [Swagger](http://127.0.0.1:8001/docs). Cổng HTTP hỗ trợ Bearer để kiểm tra API; cookie Secure cần HTTPS ở bước 4.

### Đăng nhập quản trị viên

Bấm **Authorize** ở đầu trang, nhập tài khoản super-admin từ `.env`, đánh dấu scope **admin**, rồi bấm **Authorize**. Scope này chỉ chọn thư mục tài khoản `admin_users`; quyền thực tế vẫn do role trong database quyết định. Để đăng nhập tài khoản thường trong `auth_users`, bỏ chọn scope `admin`.

Ngoài ra có thể gọi `POST /admin/auth/login` với JSON:

```json
{
  "username": "superadmin",
  "password": "mật khẩu trong .env của bạn",
  "mode": "bearer"
}
```

`mode: bearer` trả `access_token`, `refresh_token`, `token_type`, `expires_in` và thông tin công khai của tài khoản. Gửi `Authorization: Bearer <access_token>` khi gọi API được bảo vệ. Không đặt token trong URL.

### Đăng ký rồi duyệt một chủ lưu trú

Gọi `POST /admin/auth/register-owner` (API công khai):

```json
{
  "username": "chu_homestay_demo",
  "password": "MotMatKhauRieng@2026",
  "full_name": "Chủ Homestay Demo",
  "email": "demo@example.com",
  "phone": "+84912345678",
  "property_name": "Homestay Demo",
  "property_address": "Đà Nẵng",
  "national_id": "000000000001"
}
```

Dùng thông tin giả khi thử. Kết quả có `registration_id`, `status: pending` và tài khoản `poi_owner` chưa xác minh. Người đăng ký không được gửi thêm `role`, `is_verified` hoặc `is_poi_owner_verified`.

Dùng super-admin gọi `GET /admin/registrations?status=pending`. Duyệt bằng `PATCH /admin/registrations/{registration_id}`:

```json
{"status": "approved", "reason": "Đã kiểm tra hồ sơ"}
```

Có thể dùng `status: rejected` để từ chối. Mỗi hồ sơ chỉ được duyệt một lần. Tài khoản không được tự duyệt hồ sơ của chính mình.

Đăng nhập bằng tài khoản chủ vừa duyệt (chọn scope `admin`). Chủ đã đăng nhập từ trước phải refresh hoặc đăng nhập lại vì thao tác duyệt thu hồi hiệu lực access token cũ.

Gọi `POST /owner/rooms`:

```json
{"name": "Phòng đôi", "price": 500000, "currency": "VND", "max_guests": 2}
```

Sau đó gọi `GET /owner/rooms`, `PATCH /owner/rooms/{id}` hoặc `DELETE /owner/rooms/{id}`. PATCH phòng dùng đầy đủ nội dung phòng như POST. Tất cả truy vấn đều giới hạn theo tài khoản chủ đang đăng nhập; không nhận `owner_id` từ request.

Gọi `POST /owner/posts` với `{"title":"Giới thiệu homestay","body":"Nội dung giới thiệu"}`, rồi `POST /owner/posts/{id}/submit` để chuyển từ `draft` sang `pending`. Sửa nội dung đưa bài về `draft`. Các API phòng và bài đăng yêu cầu cả hai cờ xác minh cùng với quyền tương ứng.

## 3. API chính

| Nhóm | API | Quyền/chức năng |
|---|---|---|
| Auth thường | `POST /api/v1/auth/register`, `/login`, `/session`, `/refresh`, `/logout`; `GET /me` | Giữ API cũ; `/login` nhận form OAuth2, `/session` nhận JSON |
| Auth quản trị/chủ | `POST /admin/auth/login`, `/refresh`, `/logout`; `GET /admin/auth/me` | JSON login, cookie hoặc Bearer |
| Đăng ký chủ | `POST /admin/auth/register-owner` | Công khai, luôn tạo hồ sơ pending |
| Hồ sơ | `GET /admin/registrations` | `owner.read` |
| Duyệt/từ chối | `PATCH /admin/registrations/{id}` | `owner.approve` hoặc `owner.reject` theo hành động |
| Đình chỉ chủ | `POST /admin/owners/{id}/suspend` | `owner.suspend`, tắt cả hai cờ và thu hồi token cũ |
| Xem CCCD | `GET /admin/registrations/{id}/pii` | Cần đồng thời `owner.approve` và `user.read`; có audit, không cache |
| Danh mục quyền | `GET /admin/permissions` | `role.read` |
| Vai trò | `GET/POST /admin/roles`; `PATCH/DELETE /admin/roles/{name}` | Quyền `role.*` tương ứng |
| Tài khoản | `GET/POST /admin/users`; `PATCH/DELETE /admin/users/{id}` | Quyền `user.*`; DELETE vô hiệu hóa và xóa ciphertext PII |
| Nhật ký | `GET /admin/audit-logs?limit=50` | `audit.read`, phân trang bằng `before`/`next_before` |
| Hồ sơ của chủ | `GET /owner/profile` | Chủ có thể xem trạng thái khi còn pending |
| Phòng/dịch vụ | `GET/POST /owner/rooms`; `GET/PATCH/DELETE /owner/rooms/{id}` | `menu.*`, chỉ chủ đã xác minh, dữ liệu của chính mình |
| Bài đăng | `GET/POST /owner/posts`; `GET/PATCH/DELETE /owner/posts/{id}`; `POST /owner/posts/{id}/submit` | `content.*` tương ứng, chỉ chủ đã xác minh |

Các URL cũ `/api/v1/admin/...` và `/api/v1/owner/...` vẫn hoạt động, nhưng Swagger hiển thị `/admin/...` và `/owner/...` để khớp yêu cầu. `/admin/users` mặc định quản lý `admin_users`; GET/PATCH/DELETE có tham số `realm=auth_users` để quản lý tài khoản thường.

## 4. Cookie HttpOnly và HTTPS trên Windows

Cookie access/refresh luôn có `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, không đặt Domain. Cookie mode không trả token trong JSON. Access hết hạn sau 30 phút, refresh sau 7 ngày tính từ lần đăng nhập ban đầu; refresh không kéo dài mốc 7 ngày.

Caddy cung cấp [https://localhost:8443/docs](https://localhost:8443/docs) bằng CA cục bộ riêng trong Docker volume. Để Windows tin chứng chỉ, chạy trong PowerShell tại thư mục dự án:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\trust_local_https.ps1
```

Script xuất **chứng chỉ công khai** vào `dev-certs/root.crt` và thêm CA của dự án vào kho tin cậy **CurrentUser** của Windows. Đây là CA cho phát triển cục bộ. Chỉ chạy script từ bản dự án của bạn; không nhập CA từ nguồn không rõ. Trình duyệt có kho chứng chỉ riêng có thể cần nhập cùng file. Không chia sẻ private key trong volume `https_data`.

Đăng nhập `POST /admin/auth/login` qua HTTPS bằng `mode: cookie` (hoặc bỏ mode). Request thay đổi dữ liệu, refresh và logout dùng cookie phải gửi thêm `X-CSRF-Token` bằng giá trị cookie `csrf_token` JavaScript có thể đọc. Ví dụ sau chạy trong Console của trang HTTPS cùng host:

```javascript
const csrf = decodeURIComponent(document.cookie.split('; ').find(x => x.startsWith('csrf_token=')).split('=').slice(1).join('='));
await fetch('/admin/auth/refresh', {
  method: 'POST', credentials: 'include',
  headers: {'X-CSRF-Token': csrf}
});
```

SameSite/HttpOnly không thay thế việc phòng XSS trong frontend. Backend bổ sung CSRF token gắn với phiên và kiểm tra Origin; CORS chỉ cho phép các origin cấu hình trong `TRUSTED_ORIGINS`. Không dùng wildcard với credentials. Giữ cùng host `localhost` khi thử cookie.

Đối với Bearer/mobile, gửi refresh token trong JSON `{"refresh_token":"..."}` đến `/admin/auth/refresh` hoặc `/api/v1/auth/refresh`. Mỗi lần refresh phải lưu token mới và bỏ token cũ. Không refresh song song: phát lại token đã dùng sẽ thu hồi cả phiên. Logout nhận refresh token trong JSON, refresh Bearer header hoặc refresh cookie, rồi thu hồi cả access/refresh trong phiên.

## 5. RBAC và danh mục 32 quyền

Đề bài chưa quy định từng tên quyền. Bản này chọn danh mục sau, cố định tại `backend/app/core/permissions.py`; role trong MongoDB chọn quyền từ danh mục này.

| Miền | Quyền |
|---|---|
| poi (4) | `poi.read`, `poi.create`, `poi.update`, `poi.delete` |
| menu (4) | `menu.read`, `menu.create`, `menu.update`, `menu.delete` |
| user (4) | `user.read`, `user.create`, `user.update`, `user.delete` |
| role (4) | `role.read`, `role.create`, `role.update`, `role.delete` |
| analytics (2) | `analytics.read`, `analytics.export` |
| audit (2) | `audit.read`, `audit.export` |
| system (2) | `system.read`, `system.update` |
| owner (4) | `owner.read`, `owner.approve`, `owner.reject`, `owner.suspend` |
| content (6) | `content.read`, `content.create`, `content.update`, `content.delete`, `content.submit`, `content.publish` |

| Role mặc định | Priority | Quyền |
|---|---:|---|
| super_admin | 0 | Cả 32 quyền, role bất biến |
| admin | 1 | Tất cả trừ `system.update`, `role.delete` |
| poi_owner | 10 | `menu.*`, `poi.read/update`, `content.read/create/update/delete/submit`; thêm điều kiện xác minh và sở hữu dữ liệu |
| user | 100 | `poi.read`, `menu.read`, `content.read` |

Số priority nhỏ hơn có thẩm quyền cao hơn. Người quản lý không được tạo/sửa/gán vai trò ngang hoặc cao hơn mình, hoặc cấp quyền mình không có. Super-admin có thể phân quyền quản trị; API bảo vệ tài khoản super-admin khỏi bị sửa/xóa và không cho xóa 4 role mặc định. Role tùy chỉnh đang được gán cho tài khoản không thể xóa.

JWT mang role, priority, permissions, cờ xác minh và phiên bản quyền. Guards `require_permission`, `require_role`, `require_any_permission`, `require_verified_owner_permission` nằm trong `core/rbac.py`; chỉ đọc JWT và Redis, không đọc MongoDB theo mỗi request. Login/refresh mới đọc tài khoản và role trong MongoDB.

Redis giữ allowlist phiên và phiên bản user/role. Thay quyền, khóa tài khoản, duyệt/đình chỉ chủ làm access token cũ trả 401 ngay ở request tiếp theo; client refresh để nhận claims mới. Redis không sẵn sàng: API bảo vệ trả 503. Nếu mất toàn bộ Redis, phiên cũ không được tự khôi phục; đăng nhập lại.

Thay phiên bản trong Redis trước khi commit MongoDB ưu tiên chặn token cũ. Nếu mutation/commit thất bại sau bước này, tài khoản/role đó có thể tạm bị yêu cầu đăng nhập lại; quản trị viên phải thực hiện lại thay đổi để database bắt kịp phiên bản. Không sửa trực tiếp role/is_active trong MongoDB rồi kỳ vọng cache tự biết: hãy dùng API quản trị.

32 quyền là danh mục cho toàn hệ thống. Các API POI, analytics, cấu hình hệ thống, xuất báo cáo và xuất bản nội dung của những giai đoạn sau chưa được tạo chỉ vì đã có tên quyền.

## 6. Mã hóa PII, retention và audit

- Bcrypt băm mật khẩu, giới hạn 8–72 byte UTF-8 để tránh bị cắt ngầm. JWT HS256 dùng hai secret riêng; xác thực issuer, audience, thời hạn, token type và session ID.
- CCCD/định danh dùng Fernet, lưu `v1:<ciphertext>` trong `admin_users.national_id_encrypted`. Khóa Fernet được dẫn xuất bằng HKDF-SHA256 từ `SECRET_KEY`, tách mục đích với các khóa JWT. Plaintext không nằm trong hồ sơ đăng ký, JWT, audit hoặc các API liệt kê.
- `pii_expires_at = created_at + 180 ngày`. API giải mã từ chối ngay khi hết hạn (410). Tác vụ nền mặc định mỗi giờ xóa ciphertext theo lô và ghi audit; cũng dọn khi khởi động. Không dùng MongoDB TTL trên tài khoản vì TTL xóa cả document. TTL chỉ dùng với refresh session.
- Audit ghi `user_id`, `user_realm`, `resource`, `resource_id`, `action`, `created_at`, metadata giới hạn. Thao tác tạo/sửa/xóa/duyệt và audit nằm trong cùng MongoDB transaction. Audit thất bại thì nghiệp vụ rollback. Xem CCCD cũng được ghi audit.
- Rate limit Redis áp dụng cho login/đăng ký. Qua gateway cục bộ, IP nhìn thấy từ backend là IP proxy, nên giới hạn IP được chia sẻ; triển khai thực tế cần cấu hình proxy tin cậy và giới hạn ở gateway phù hợp.

## 7. Kiểm tra tự động

Unit/regression:

```powershell
python -m pip install -r backend/requirements-test.txt
python -m pytest -q
python -m ruff check backend scripts
```

Kiểm tra dịch vụ Docker đang chạy, cần `httpx` trong môi trường Python máy bạn:

```powershell
python scripts/smoke_auth.py
python scripts/smoke_phase2.py --cookie-url https://localhost:8443 --ca-file dev-certs/root.crt
```

Smoke tạo tài khoản thử có tên ngẫu nhiên, duyệt rồi vô hiệu hóa tài khoản chủ thử; audit và tài khoản thử vẫn được giữ. Dùng database phát triển. Không chạy smoke trên dữ liệu production. CI chạy hai cấu hình local/S3 và kiểm tra các API này trên MongoDB, Redis và HTTPS Docker thực.

Khi gặp 401 sau đổi quyền/duyệt: refresh hoặc đăng nhập lại. 403: thiếu quyền, chưa xác minh hoặc thiếu CSRF header. 409: hồ sơ đã duyệt, role còn được dùng hoặc có cập nhật đồng thời; tải lại trạng thái trước khi thử lại. 503: kiểm tra health/log của database, Redis, S3 hoặc cấu hình mã hóa.

## 8. Phạm vi triển khai

Backend Giai đoạn 2 đã có các luồng nêu trong đề, cùng API phòng và bài đăng tối thiểu để kiểm chứng chốt chặn. Chưa phải một giao diện cổng đối tác hoàn chỉnh, chưa có email xác minh/khôi phục mật khẩu, không tự gắn role vào các router stub của những giai đoạn tiếp theo. HTTPS cục bộ dùng CA nội bộ; khi triển khai cần domain/chứng chỉ thật, secret riêng và trusted origins HTTPS phù hợp.
