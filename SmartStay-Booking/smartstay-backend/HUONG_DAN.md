# Smart Stay Concierge

**Bản sửa dành cho ZIP `smart-stay-current.zip` bạn gửi ngày 22/10/2026:** đọc
[BAT_DAU_CAP_NHAT.md](BAT_DAU_CAP_NHAT.md) để áp dụng có sao lưu và giữ `.env`.
Script `scripts/smoke_phase3.py` đã có sẵn trong bản này.

Bản hiện tại gồm hạ tầng Giai đoạn 1, xác thực/RBAC Giai đoạn 2 và backend/API Giai đoạn 3: POI, hạng phòng, kiểm duyệt bài đăng, thông báo, truy vấn vị trí, đồng bộ delta, fallback ngôn ngữ và media local/S3.

**Cập nhật từ bản Giai đoạn 2 và kiểm tra:** [HUONG_DAN_GIAI_DOAN_3.md](HUONG_DAN_GIAI_DOAN_3.md).
**Xác thực và tài khoản Giai đoạn 2:** [HUONG_DAN_GIAI_DOAN_2.md](HUONG_DAN_GIAI_DOAN_2.md).
**Hạ tầng S3 cục bộ:** [HUONG_DAN_S3.md](HUONG_DAN_S3.md).
**Kết quả kiểm tra bản này:** [KET_QUA_KIEM_TRA_GIAI_DOAN_3.md](KET_QUA_KIEM_TRA_GIAI_DOAN_3.md).

Giải nén toàn bộ ZIP vào thư mục dự án hiện tại, chọn thay thế file trùng tên, giữ `.env` và dữ liệu Docker. Trong Terminal của VS Code tại thư mục có `docker-compose.yml`:

```powershell
docker compose up -d --build
docker compose ps -a
python scripts/smoke_phase3.py
```

Nếu bắt đầu dự án mới, chạy `python scripts/configure_phase2.py` trước khi khởi động Docker để tạo khóa mạnh và tài khoản super-admin. Khi nâng cấp từ Giai đoạn 2 đã hoạt động, dùng ngay `.env` hiện tại. Script smoke cần `httpx`; có thể chạy `python -m pip install httpx==0.27.2` nếu máy chưa có.

- Swagger/Bearer: http://127.0.0.1:8001/docs
- Readiness: http://127.0.0.1:8001/health/ready
- Swagger/cookie Secure: https://localhost:8443/docs — xem bước tin cậy CA trong hướng dẫn Giai đoạn 2.

Trong Swagger, **Authorize**, đánh dấu scope **admin** để dùng tài khoản quản trị hoặc chủ lưu trú. Không đánh dấu để dùng tài khoản thường từ `/api/v1/auth/register`. Scope chỉ chọn thư mục tài khoản; quyền lấy từ role, không được tự yêu cầu bằng scope.

Trong Swagger, các API mới nằm ở nhóm `content`, `content-owner`, `content-admin` và `media`. Nhóm `content-admin` có API nhập bản dịch và MP3 để kiểm tra fallback. Các router analytics, localization tự động, AI, observability và UI i18n còn là khung; audio/maps vẫn có API thăm dò. Hệ thống hiện phục vụ backend/API, chưa có dashboard hay ứng dụng du khách.

API phòng/bài đăng độc lập từ Giai đoạn 2 được giữ lại. Hạng phòng chính thức ở Giai đoạn 3 dùng `menu_items`, liên kết với POI; xem hướng dẫn để tránh nhập nhầm vào nhóm API cũ.

Kiểm thử mã nguồn:

```powershell
python -m pip install -r backend/requirements-test.txt
python -m pytest -q
python -m ruff check backend scripts
```
