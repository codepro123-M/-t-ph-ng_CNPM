# Kết quả kiểm tra Giai đoạn 2

Ngày kiểm tra: 21/10/2026. Kiểm tra trên bản mã trong ZIP này, trong môi trường Linux độc lập; chưa chạy trên máy Windows của người dùng.

| Hạng mục | Kết quả |
|---|---|
| Pytest unit và regression | **105 passed** trên Python 3.12.14 |
| Ruff cho backend và scripts | Đạt |
| Docker Compose config | Đạt với local + HTTPS và S3 + HTTPS; đã kiểm tra chạy lại cả hai helper cấu hình |
| MongoDB thực | 7.0.45, single-node Replica Set, transaction startup probe thành công |
| Redis thực | 6.2.14 từ bản binary phục vụ kiểm thử; Compose của dự án dùng Redis 7 |
| S3 thực | RustFS 1.0.3, khởi tạo bucket và backend readiness thành công |
| HTTPS thực | Caddy 2.11.7, CA nội bộ được kiểm tra bằng HTTP client có xác thực CA |
| Nâng cấp dữ liệu cũ | Giữ chỉ mục `auth_username_unique`, nạp `auth_version`, đăng nhập tài khoản cũ thành công |
| Auth thường | Đăng ký, trùng username, đăng nhập và `/me` thành công |
| Chủ lưu trú | Pending bị chặn; duyệt cập nhật hai cờ; access token cũ bị chặn; refresh nhận quyền mới |
| Phòng/bài đăng | Tạo, sửa, xóa phòng; tạo/gửi bài đăng; audit tương ứng |
| Cookie/CSRF | Secure/HttpOnly/SameSite, JSON không trả token ở cookie mode, thiếu CSRF bị chặn, refresh/logout thành công |
| Refresh đồng thời | Chỉ một request đổi được token; phát lại token cũ thu hồi cả phiên |
| Audit + transaction | Làm MongoDB từ chối ghi audit: thao tác tạo phòng bị rollback, không có phòng mồ côi |
| PII | Ciphertext có tiền tố `v1:`, không nằm trong audit; hết hạn bị ẩn ngay; worker xóa ciphertext và giữ tài khoản |

Unit tests dùng Motor/MongoDB và Redis giả lập để kiểm tra nhiều nhánh lỗi, đồng thời dùng bcrypt, PyJWT và Fernet thực. Các luồng tích hợp trong bảng được chạy bổ sung bằng binary dịch vụ thật và Uvicorn, không dùng Docker Engine. Môi trường này không có Docker Engine nên chưa trực tiếp build/chạy container; Dockerfile vẫn dùng Python 3.11. Workflow CI đã bổ sung smoke cho cả local/S3 và HTTPS, nhưng chưa có kết quả GitHub Actions của bản cập nhật.

Pytest có cảnh báo DeprecationWarning từ Starlette/AnyIO và mongomock khi chạy Python 3.12; không có kiểm thử thất bại. Không truy cập hoặc thay đổi database, tài khoản hay môi trường Docker trên máy người dùng trong quá trình kiểm tra này.
