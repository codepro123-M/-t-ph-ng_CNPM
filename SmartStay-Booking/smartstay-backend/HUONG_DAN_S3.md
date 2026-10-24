# Hoàn thiện S3-compatible storage readiness

## Cập nhật vào VS Code hiện tại

1. Giải nén ZIP và chép đè nội dung vào **thư mục dự án cũ** như lần trước.
2. Giữ nguyên `.env` hiện tại. ZIP không chứa `.env` hoặc dữ liệu của bạn.
3. Mở terminal VS Code tại thư mục chứa `docker-compose.yml` rồi chạy lần lượt:

```powershell
python scripts/configure_local_s3.py
docker compose up -d --build
```

Lệnh đầu chỉ cần Python, không cần cài thêm thư viện trên Windows. Nó thêm cấu
hình S3 vào `.env`, tạo cặp khóa ngẫu nhiên cho storage cục bộ và giữ nguyên các
khóa JWT cùng cấu hình MongoDB/Redis đang có. Chạy lại không đổi các khóa S3 đã tạo.
Không dùng helper này để ghi đè một endpoint S3 bên ngoài đã cấu hình.

`COMPOSE_FILE` và `COMPOSE_PATH_SEPARATOR` trong `.env` giúp Docker tự kết hợp
`docker-compose.yml` với `docker-compose.s3.yml`. Vì vậy các lệnh `docker compose`
sau đó vẫn dùng được như trước. Nếu bạn đã đặt các biến này trong PowerShell,
giá trị trong shell có độ ưu tiên cao hơn `.env`; cần bỏ giá trị shell cũ hoặc dùng
hai tham số `-f` một cách tường minh.

Compose sẽ:

1. Khởi động MongoDB/Redis cùng bộ S3-compatible **RustFS 1.0.3**.
2. Chạy `s3-init` để tạo bucket `smartstay-media` nếu chưa tồn tại. Bucket đã có
   được giữ nguyên; không bật public access hay xóa nội dung.
3. Khởi động backend sau khi bucket sẵn sàng.
4. Chạy probe S3 thật trong `lifespan()` trước khi phục vụ API.

S3-init là tác vụ chạy một lần, vì vậy `Exited (0)` của dịch vụ này là bình thường.
Các dịch vụ MongoDB, Redis, S3 và backend phải ở trạng thái healthy.

## Kiểm tra kết quả

```powershell
docker compose ps -a
docker compose logs --tail=60 s3-init backend
```

Mở http://127.0.0.1:8001/health/ready. Phản hồi thành công phải có:

```json
{
  "status": "ready",
  "mongodb_tx_ready": true,
  "redis_ready": true,
  "media_backend": "s3",
  "media_ready": true,
  "mounted_routers": 11
}
```

Log backend có dòng:

```text
S3 media readiness OK: bucket access, write, read and cleanup verified.
```

Muốn ép kiểm tra ngay, không dùng kết quả cache:

```powershell
docker compose exec backend python -c "import asyncio; from app.core.media_storage import media_storage; print(asyncio.run(media_storage.check_backend_health(force=True)))"
```

Kết quả phải là `True`; lỗi kết nối hoặc quyền truy cập làm lệnh thất bại.

## Probe thực hiện những gì?

- Kiểm tra bucket bằng HeadBucket.
- Ghi nội dung nhỏ vào key ngẫu nhiên `_healthchecks/<uuid>.txt`.
- Đọc lại và so sánh chính xác nội dung.
- Xóa file probe. Nếu bucket bật versioning, xóa đúng VersionId vừa tạo.
- Đóng stream và kết nối SDK, kể cả khi thao tác bị lỗi.

Lỗi ghi, đọc, xóa hoặc nội dung sai đều làm startup thất bại. Sau startup,
`/health/ready` trả HTTP 503 khi probe phát hiện S3 không sẵn sàng. Kết quả thành
công cache tối đa 30 giây, lỗi cache tối đa 2 giây; không phải lần gọi nào cũng tạo
một object mới. Nhiều yêu cầu đồng thời dùng chung một lần probe.

SDK chạy trong thread pool để không chặn event loop. Các yêu cầu mạng có timeout
kết nối/đọc và không retry tự động. Lỗi hiển thị tên loại/mã lỗi, không in access
key, secret key hoặc thông điệp lỗi gốc có thể chứa dữ liệu nhạy cảm.

Nếu server trả lời PUT không rõ kết quả hoặc bị mất kết nối trong lúc xóa, file
probe có thể còn lại trong `_healthchecks/`. Hệ thống báo lỗi; nó không báo thành
công khi cleanup thất bại. Với bucket triển khai thật, có thể đặt lifecycle cho
riêng prefix probe để dọn các object còn sót sau sự cố.

## Dữ liệu và địa chỉ

| Mục | Địa chỉ / vị trí |
| --- | --- |
| Swagger | http://127.0.0.1:8001/docs |
| API S3 từ Windows | http://127.0.0.1:9000 |
| Console storage | http://127.0.0.1:9001 |
| Endpoint backend dùng trong Docker | `http://s3:9000` |
| Bucket mặc định | `smartstay-media` |
| Dữ liệu S3 | Named volume `s3_data` của dự án |
| Khóa đăng nhập console | `S3_ACCESS_KEY`, `S3_SECRET_KEY` trong `.env` |

Cổng S3/console chỉ bind vào loopback của máy. Không cần tài khoản AWS để chạy
bộ S3 cục bộ này. S3 dùng volume mới, không thay thế các volume MongoDB, Redis
hay static đã có. Các file MP3/ảnh hiện tại trong static không được tự di chuyển.

## Kiểm tra khi S3 bị ngắt

Có thể dừng riêng S3 để kiểm tra trạng thái không sẵn sàng:

```powershell
docker compose stop s3
```

Sau khi kết quả cache cũ hết hạn (tối đa 30 giây), `/health/ready` phải trả 503.
Khôi phục lại bằng:

```powershell
docker compose up -d s3
```

Khi storage đã khỏe trở lại, readiness phục hồi ở lần kiểm tra sau. Liveness
`/health` vẫn có thể trả alive trong lúc storage lỗi: tiến trình đang sống nhưng
chưa đủ điều kiện phục vụ các chức năng cần storage.

## Kết nối MinIO, AWS S3 hoặc nhà cung cấp khác

Bộ kiểm tra dùng Boto3/S3 Signature V4, không phụ thuộc riêng RustFS. Với storage
bên ngoài, chuẩn bị bucket và credential trước, rồi cấu hình `.env`:

```dotenv
MEDIA_BACKEND=s3
S3_ENDPOINT_URL=https://your-s3-endpoint.example
S3_BUCKET=your-bucket
S3_REGION=your-region
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_ADDRESSING_STYLE=path
COMPOSE_FILE=docker-compose.yml
```

Với AWS S3 nguyên bản, để `S3_ENDPOINT_URL` trống và đặt region đúng. Khi nhà cung
cấp yêu cầu virtual-hosted addressing, đổi `S3_ADDRESSING_STYLE=virtual` hoặc
`auto`. Credential tạm thời có thể bổ sung `S3_SESSION_TOKEN`. Với CA nội bộ,
`S3_CA_BUNDLE` phải trỏ đến file CA được mount vào container; không tắt xác minh TLS.

Runtime cần quyền `s3:ListBucket` để HeadBucket, cùng `s3:PutObject`,
`s3:GetObject`, `s3:DeleteObject` cho prefix `_healthchecks/*`. Bucket versioned
cần thêm `s3:GetObjectVersion` và `s3:DeleteObjectVersion`. Media Giai đoạn 3 dùng
prefix `content/*`, cần quyền Put/Get/Delete tương ứng. Worker xử lý PUT mất phản
hồi trên bucket versioned cần `s3:ListBucketVersions` và `s3:DeleteObjectVersion`
để dọn đúng key ngẫu nhiên đã dành trước. Backend không tự tạo bucket
trong startup; tác vụ `s3-init` chỉ phục vụ môi trường local/test và từ chối chạy
trong non-dev.

## Kiểm thử và giới hạn

- Kết quả readiness hạ tầng ban đầu: 72 kiểm thử tự động đạt, gồm auth,
  lifecycle, cấu hình S3, quyền S3, cleanup, cache và helper `.env`. Kết quả bản
  hiện tại nằm trong `KET_QUA_KIEM_TRA_GIAI_DOAN_3.md`.
- Đã dùng RustFS 1.0.3 binary chính thức, xác minh SHA256 phát hành, chạy S3 thật:
  tạo bucket idempotent, Head/Put/Get/Delete, dọn version, từ chối sai khóa, bucket
  không tồn tại và storage bị dừng.
- Môi trường kiểm tra không có Docker Engine; image/volume và toàn bộ Compose
  vẫn cần kiểm tra trên Docker của bạn. CI có hai chế độ local/S3 và probe thật.
  Cấu hình merge đã được xác minh bằng Docker Compose CLI 5.6.1: tự chọn hai file
  qua `.env`, đủ 5 dịch vụ, dependency/init, credential, port và healthcheck khớp.
- Giai đoạn 3 đã bổ sung upload ảnh/MP3, phát media qua API và hàng đợi dọn file
  local/S3. Hướng dẫn: `HUONG_DAN_GIAI_DOAN_3.md`. TTS và dịch tự động thuộc giai
  đoạn tiếp theo.

Nguồn tham khảo kỹ thuật:

- https://docs.aws.amazon.com/boto3/latest/reference/services/s3.html
- https://docs.rustfs.com/en/installation/container/docker
- https://docs.docker.com/compose/how-tos/environment-variables/envvars/
