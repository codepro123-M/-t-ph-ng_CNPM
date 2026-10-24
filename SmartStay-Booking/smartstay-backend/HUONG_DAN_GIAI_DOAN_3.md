# Giai đoạn 3 — Nội dung lưu trú, hạng phòng và đồng bộ

## 1. Cập nhật dự án đang chạy trên Windows

Đóng terminal đang chạy lệnh kiểm thử, giải nén ZIP và chép toàn bộ nội dung vào
thư mục dự án cũ, chọn thay thế file trùng tên. Đặt `docker-compose.yml` đúng ở
thư mục gốc hiện tại, tránh lồng thêm một thư mục dự án. Giữ `.env` đang dùng.
ZIP không chứa `.env` hay dữ liệu MongoDB/S3 của bạn.

Trong Terminal PowerShell của VS Code, tại thư mục có `docker-compose.yml`, chạy
lần lượt và chờ mỗi lệnh hoàn thành:

```powershell
docker compose up -d --build
docker compose ps -a
python scripts/smoke_phase3.py
```

Backend, MongoDB, Redis và các dịch vụ đang bật phải healthy. `s3-init` kết thúc
với `Exited (0)` là bình thường. Nếu backend chưa healthy, chờ khoảng 30 giây rồi
chạy lại lệnh kiểm tra. Nếu thiếu `httpx` trên Windows:

```powershell
python -m pip install httpx==0.27.2
python scripts/smoke_phase3.py
```

Không cần chạy lại helper cấu hình Giai đoạn 2 hoặc S3 khi các phần đó đang hoạt
động. Không xóa các volume để cập nhật. Compose thêm volume `content_media` cho
file local; các volume cũ được giữ nguyên.

Smoke đọc tài khoản super-admin từ `.env`, tạo hai chủ lưu trú và một POI có tên
ngẫu nhiên để kiểm tra. Sau khi chạy, script xóa POI thử và vô hiệu hóa hai tài
khoản thử; hồ sơ đăng ký, thông báo và audit của chúng vẫn còn. Script không
chỉnh sửa POI hay tài khoản sẵn có. File thử được worker dọn sau thời gian chờ.
Thành công sẽ có các dòng `PASS` cho bài đăng/ảnh, delta/fallback/hạng phòng,
nearby và quyền/xóa POI.

Mở Swagger: http://127.0.0.1:8001/docs. Với Bearer, chọn **Authorize**, đánh dấu
scope **admin**, rồi đăng nhập bằng tài khoản super-admin hoặc chủ lưu trú tương
ứng. Nếu Swagger không gửi token, dùng script smoke trước để kiểm chứng backend.
Cookie Secure vẫn dùng https://localhost:8443 và CA đã cấu hình ở Giai đoạn 2.

## 2. Các nhóm API mới

| Nhóm Swagger | Chức năng |
|---|---|
| `content` | POI công khai, nearby, load-all, hạng phòng công khai; tạo/sửa/xóa POI yêu cầu quyền quản trị |
| `content-owner` | Chủ gửi bài, xem POI của mình, thông báo, ảnh và hạng phòng |
| `content-admin` | Duyệt bài, quản lý hạng phòng, nhập bản dịch/MP3, xem và thử lại tác vụ dọn media |
| `media` | Tải ảnh hoặc MP3 đã được công bố |

Các URL chuẩn là `/poi`, `/owner/...`, `/admin/...`, `/media/...`; alias
`/api/v1` tương ứng được giữ nhưng ẩn khỏi Swagger. Chủ chưa duyệt được xem trạng
thái hồ sơ/bài của mình, nhưng không được gửi bài hay sửa hạng phòng. Chủ đã duyệt
chỉ quản lý dữ liệu của mình. Việc xuất bản hoặc xóa POI yêu cầu
`content.publish` cùng quyền `poi.create/update/delete` phù hợp.

## 3. Chủ gửi nội dung và Admin duyệt

Đăng nhập bằng chủ đã được duyệt, mở `POST /owner/submissions`, chọn **Try it out**
và gửi:

```json
{
  "kind": "create",
  "payload": {
    "name": "Homestay Bên Biển",
    "description": "Homestay yên tĩnh, gần biển Đà Nẵng.",
    "check_in_instructions": "Nhận phòng từ 14 giờ, liên hệ lễ tân khi đến.",
    "category": "homestay",
    "address": "Đà Nẵng, Việt Nam",
    "latitude": 16.0544,
    "longitude": 108.2022,
    "images": [],
    "geofence_radius": 30,
    "audio_priority": 5
  }
}
```

Phản hồi `201` có `id` và `status: pending`. Chưa có POI công khai. `category`
chấp nhận `hotel`, `homestay`, `resort`, `hostel`, `apartment`, `guesthouse`, `villa`, `boutique`.
`geofence_radius` nhận alias `trigger_radius`, mặc định 30 mét. Tọa độ lưu bằng
GeoJSON `[longitude, latitude]`. Tên, mô tả và hướng dẫn nhận phòng là nguồn tiếng
Việt; bán kính và `audio_priority` được lưu để ứng dụng dùng ở giai đoạn phát âm
thanh, chưa có tác vụ tự phát âm thanh trên thiết bị.

Chuyển sang tài khoản Admin, xem `GET /admin/submissions?status=pending`, rồi gọi
`PATCH /admin/submissions/{id}` với ID bài gửi:

```json
{"status": "approved", "admin_note": "Đã xác minh nội dung và địa chỉ."}
```

Phản hồi có `poi_id`. Gọi `GET /poi/{poi_id}` hoặc `/poi/load-all` để xem kết quả.
Từ chối dùng `status: rejected`; nhận xét được giữ và gửi cho chủ. POI chính thức,
trạng thái bài, thông báo, dataset version và audit cùng nằm trong transaction.
Một bài chỉ được duyệt một lần.

Chủ xem `GET /owner/notifications` và đánh dấu đã đọc bằng
`PATCH /owner/notifications/{id}/read`. Có `unread_count`, bộ lọc `unread_only` và
phân trang `before`. Chủ xem danh sách POI cùng revision hiện tại qua
`GET /owner/pois`.

Để gửi sửa, dùng cùng endpoint với `kind: update`, thêm `poi_id` và
`expected_revision`, còn `payload` chứa **toàn bộ** nguồn tiếng Việt mới. Revision
phải lấy mới nhất; thay đổi POI, hạng phòng hoặc bản dịch đều làm revision tăng.
Nếu Admin duyệt sau khi dữ liệu đã đổi, API trả `409`, giữ bài pending; chủ cần
đọc dữ liệu và gửi bài sửa mới. Chủ không gọi trực tiếp PATCH POI để bỏ qua duyệt.

Admin có thể tạo trực tiếp qua `POST /poi`; sửa từng trường qua
`PATCH /poi/{id}` kèm `expected_revision`. `is_active: false` ẩn POI khỏi khách và
tạo sự kiện loại bỏ trong delta. Sửa lại thành `true` công bố POI trở lại.

## 4. Ảnh và hạng phòng

Chủ dùng `POST /owner/media/images`, chọn file trong trường `file`. Nhận `id` rồi
đưa ID vào mảng `images` của payload bài gửi. Tối đa 8 ID khác nhau; mỗi ảnh tối
đa **5 MiB (5 × 1024 × 1024 byte)**. Hỗ trợ JPEG, PNG, WebP không động, tối đa
20 megapixel. Backend kiểm tra nội dung ảnh thực; đổi đuôi file không bỏ qua kiểm
tra. Không gửi đường dẫn Windows, URL tùy ý hay dữ liệu base64 vào `images`.

Ảnh mới riêng tư, chủ xem qua `GET /owner/media/{id}` có xác thực. Sau khi duyệt,
POI công khai trả URL `/media/{id}`. Admin upload qua `/admin/media/images` và xem
riêng qua `/admin/media/{id}`. File managed local nằm ngoài `/static`; S3 được đọc
qua backend, không yêu cầu mở bucket công khai.

Sau khi đã có POI được duyệt, chủ tạo hạng phòng bằng `POST /owner/menu-items`:

```json
{
  "poi_id": "THAY_BANG_ID_POI_CUA_BAN",
  "name": "Phòng đôi hướng biển",
  "description": "Một giường đôi, có ban công.",
  "kind": "room_type",
  "price": "650000.00",
  "currency": "VND",
  "capacity": 2,
  "amenities": ["Wi-Fi", "Điều hòa", "Ăn sáng"],
  "is_available": true
}
```

`kind: service` dùng cho dịch vụ đi kèm. Giá được kiểm tra bằng Decimal và lưu/trả
dưới dạng chuỗi chính xác, không dùng số thực để tính tiền. Tối đa 2 chữ số thập
phân, tổng 14 chữ số. Mỗi POI có tối đa 200 hạng phòng/dịch vụ.

Chủ xem/sửa/xóa tại `/owner/pois/{poi_id}/menu-items` và
`/owner/pois/{poi_id}/menu-items/{item_id}`. PATCH gửi đầy đủ dữ liệu hạng phòng
kèm `expected_revision` của **hạng phòng**. Admin có các API `/admin/menu-items`
tương ứng. Thay đổi hạng phòng cũng cập nhật dataset để khách nhận delta. Khách
chỉ thấy những dòng `is_available: true` qua `/poi/{id}/menu-items` hoặc dữ liệu
nhúng trong POI.

Các API `/owner/rooms` và `/owner/posts` của Giai đoạn 2 vẫn giữ nguyên để tương
thích. Chúng dùng collection độc lập, không tự biến thành hạng phòng hoặc bài
duyệt Giai đoạn 3. Không tự chuyển dữ liệu cũ vì các bản ghi cũ không có POI đích;
hãy nhập hạng phòng chính thức qua `menu-items` sau khi có POI.

## 5. Nearby và fallback ngôn ngữ

Ví dụ truy vấn công khai:

```text
GET /poi/nearby?latitude=16.0544&longitude=108.2022&radius_m=5000&language=fr
GET /poi/load-all?language=fr&limit=200
```

Nearby trả khoảng cách mét, sắp theo gần nhất; mặc định bán kính tìm 5 km và tối
đa 50 kết quả. Có thể lọc `category`, đặt limit tối đa 200, bán kính tối đa 100 km.
Bán kính truy vấn này độc lập với geofence 30 m của từng POI. Startup tự tạo chỉ
mục `location: 2dsphere`. Phản hồi `query_engine` cho biết `geoNear` hay `haversine`.
Nếu truy vấn địa lý thất bại, backend quét POI đang công bố và tính Haversine,
giữ các kết quả gần nhất trong bộ nhớ. MongoDB vẫn phải đọc được dữ liệu; fallback
không thay thế database khi database mất kết nối hoàn toàn.

`load-all`, `nearby` và chi tiết POI dùng cùng chuỗi fallback:

| Tình huống | Ngôn ngữ trả về | `fallback_tier` | Audio |
|---|---|---|---|
| Có đúng bản dịch khách chọn | Ngôn ngữ yêu cầu | 1 | MP3 của bản đó nếu đã gắn |
| Thiếu bản yêu cầu, có tiếng Anh | `en` | 2 | MP3 tiếng Anh nếu đã gắn |
| Thiếu cả hai | Nguồn `vi` | 3 | Luôn `null` |

Khách chọn `vi` nhận nguồn tiếng Việt với Tier 1. Trả thêm `requested_language`,
`language` và `source_language` để ứng dụng hiển thị đúng. Tên và mô tả hạng phòng
hiện vẫn là tiếng Việt (`language: vi`), chưa có bộ dịch hạng phòng.

Để kiểm chứng fallback, Admin nhập bản dịch tại
`PUT /admin/pois/{poi_id}/localizations/en`:

```json
{
  "name": "Seaside Homestay",
  "description": "A quiet stay near the beach.",
  "check_in_instructions": "Check in after 2 PM.",
  "source_revision": 1,
  "audio_asset_id": null
}
```

Lấy `source_revision` hiện tại từ POI, không cố định số 1 khi nguồn đã sửa. Mỗi
POI tối đa 64 bản dịch. MP3 có thể upload bằng `POST /admin/media/audio`, tối đa
25 MiB mặc định, rồi gắn ID vào bản dịch. Backend kiểm tra định dạng MP3 thực bằng
ffprobe có sẵn trong Docker. Sửa nguồn tên/mô tả/hướng dẫn nhận phòng làm vô hiệu
các bản dịch cũ và xếp MP3 cũ vào hàng đợi dọn. Các trường địa chỉ, ảnh, tọa độ
hoặc giá phòng không làm mất bản dịch của phần văn bản đó.

Bản này có API nhập bản dịch và MP3, chưa tự dịch hay sinh TTS; đó là nghiệp vụ
các giai đoạn tiếp theo.

## 6. Hợp đồng đồng bộ cho ứng dụng du khách

Lần đầu gọi `/poi/load-all?language=vi&limit=200`. Dữ liệu trả gồm `items`,
`removed_poi_ids`, `has_more`, `sync_cursor`, `dataset_version`, `as_of` và header
`ETag`. Mỗi trang giữ nguyên snapshot theo dataset version tại lúc bắt đầu, kể cả
khi Admin sửa/xóa POI trong lúc ứng dụng đang tải.

1. Đọc và áp dụng toàn bộ trang. Khi `has_more: true`, gọi tiếp
   `/poi/load-all?cursor=<sync_cursor>`; không cần truyền lại language hoặc limit.
2. Khi `has_more: false`, lưu cursor cuối làm checkpoint. Full sync thay thế tập
   POI cache sau khi tải đủ, không gộp với các bản ghi cũ đã bị xóa trước đó.
3. Lần sau gửi checkpoint vào `cursor`. Server trả POI có thay đổi và các ID cần
   xóa khỏi cache trong `removed_poi_ids`; tiếp tục tải hết trang rồi lưu checkpoint
   mới. Thay đổi hạng phòng/bản dịch cũng trả lại POI liên quan.
4. Thay ngôn ngữ thì bắt đầu full sync mới. Đang phân trang phải giữ nguyên ngôn
   ngữ và page size. Cursor phân trang có hạn tổng cộng một giờ kể từ lúc bắt đầu
   chuỗi trang; checkpoint hoàn tất không có hạn thời gian cố định.

Cursor sai/chỉnh sửa/hết hạn trả `400`; dataset đã reset trả `409`. Client bắt đầu
full sync mới trong các trường hợp này. Cursor được ký riêng mục đích sync, không
dùng được làm token đăng nhập. Không phân tích hay tự sửa nội dung cursor ở client.

Có thể dùng `updated_after=<as_of lần trước>` thay checkpoint. Mốc phải có múi giờ
(`Z` hoặc `+00:00`), lấy nguyên giá trị server trả về, không dùng đồng hồ thiết bị.
Nếu URL có dấu `+`, cần URL-encode đúng. Không dùng đồng thời cursor và
updated_after. Cursor ưu tiên hơn cho luồng client mới vì không phụ thuộc so sánh
mốc thời gian tự xây dựng.

Gửi `If-None-Match` với ETag đã nhận cho **cùng truy vấn và ngôn ngữ** để nhận `304`
khi representation không đổi. `304` không có JSON body. Các trang tiếp theo luôn
trả trang, không bị chặn bởi ETag. ETag của full sync và delta không dùng thay
cho nhau; không gửi ETag của trang trước cho một truy vấn khác. CORS đã expose
`ETag`/`Content-Language` và cho phép `If-None-Match`.

`content_changes` giữ lịch sử snapshot và tombstone để tránh mất thay đổi, hỗ trợ
client offline. Hiện chưa tự nén/xóa lịch sử; database tăng theo số lần sửa nội
dung. Khi cần chính sách lưu lịch sử, phải thiết kế reset/full sync tương ứng,
không tự xóa collection này trong khi client còn dùng cursor.

## 7. Xóa toàn vẹn và dọn file

Admin gọi `DELETE /poi/{id}`. Một MongoDB transaction xóa POI, hạng phòng, bản
dịch, hủy các bài sửa pending của POI, tạo thông báo cho chủ, ghi audit, thêm
tombstone và tăng version dataset. Ảnh/MP3 cũ được ghi vào
`media_cleanup_jobs` **trong cùng transaction**. Nếu bước ghi audit/thông báo thất
bại thì toàn bộ thay đổi database được rollback.

Không thể rollback thao tác xóa file trên S3 cùng MongoDB. Vì vậy worker chỉ xóa
file sau khi transaction đã commit và qua thời gian chờ; mặc định 24 giờ để các
trang sync đang tải còn đọc được media cũ. File mới chưa được dùng, ảnh bị thay
và MP3 bị vô hiệu cũng có cleanup intent. Trước khi xóa, worker kiểm tra POI, bài
pending và bản dịch còn tham chiếu; có tham chiếu thì giữ file. File từng công bố
có thể tiếp tục đọc bằng URL đã biết trong thời gian chờ dọn.

Worker chạy cùng backend, claim tác vụ bằng lease, xóa idempotent và retry lỗi với
backoff. Bucket versioned được xóa đúng VersionId; PUT mất phản hồi được xử lý
bằng cách liệt kê đúng key ngẫu nhiên đã dành trước. Sau 10 lần lỗi, trạng thái
`failed` cần Admin kiểm tra storage rồi thử lại:

```text
GET /admin/media-cleanup?state=failed
POST /admin/media-cleanup/{job_id}/retry
```

Các cấu hình tùy chọn có giá trị mặc định, không bắt buộc sửa `.env` hiện tại:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `CONTENT_MEDIA_DIR` | `/app/runtime_data/content-media` trong Docker | Thư mục local riêng tư, ngoài STATIC_DIR, mount volume mới |
| `CONTENT_CLEANUP_INTERVAL_SECONDS` | 30 | Chu kỳ worker dọn media |
| `CONTENT_MEDIA_GRACE_SECONDS` | 86400 | Thời gian chờ; tối thiểu 3600 giây |
| `CONTENT_QUERY_TIMEOUT_MS` | 10000 | Timeout truy vấn nội dung nặng |
| `MAX_AUDIO_SIZE_BYTES` | 26214400 | Giới hạn MP3 25 MiB |

S3 dùng cấu hình và bucket hiện tại, prefix `content/image/` và `content/audio/`.
Tham khảo quyền runtime trong `HUONG_DAN_S3.md`. Không tự chuyển file khi đổi
backend/bucket; asset nhớ backend/bucket lúc upload, nên phải giữ nơi lưu cũ và
credential truy cập được trong thời gian còn tham chiếu. Nếu đổi S3 endpoint, cần
lập kế hoạch di chuyển media trước vì cấu hình endpoint dùng chung cho runtime.

## 8. Kiểm thử và xử lý lỗi

```powershell
python -m pip install -r backend/requirements-test.txt
python -m pytest -q
python -m ruff check backend scripts
```

Các kiểm thử này dùng database giả lập; smoke ở bước 1 kiểm tra chính Docker
đang chạy. Xem phạm vi kiểm tra dịch vụ thật trong
`KET_QUA_KIEM_TRA_GIAI_DOAN_3.md`. Workflow CI đã thêm smoke Giai đoạn 3 cho cả
local và S3; chưa có kết quả GitHub Actions của bản này.

Nếu smoke lỗi, lấy nội dung terminal và:

```powershell
docker compose logs --tail=100 backend
```

`401` thường do token cũ hoặc thiếu token; đăng nhập lại sau khi duyệt chủ.
`403` là tài khoản thiếu quyền hoặc chủ chưa được xác minh. `404` ở dữ liệu chủ
khác bảo vệ việc cách ly dữ liệu. `409` yêu cầu đọc revision hiện tại hoặc reset
sync như thông báo. `413` là quá dung lượng; `415` là định dạng file không hợp lệ.
`503` cần kiểm tra kết nối MongoDB/S3 và log backend.
