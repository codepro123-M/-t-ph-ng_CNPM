# Sửa dịch thuật khi Google trả 429 — 25/10/2026

Gói này tiếp nối bản sửa 5 lỗi. Backend và frontend cũ vẫn dùng công cụ cập nhật có sao lưu `AP_DUNG_SUA_5_LOI.py`.

## Thay đổi

- Chế độ mặc định `auto`: dùng Google trước; khi Google lỗi hoặc đang trong thời gian chờ, thử MyMemory. Không cần API key để dùng MyMemory ẩn danh.
- Khi Google trả HTTP 429, lưu thời gian chờ ít nhất 15 phút hoặc theo `Retry-After` nếu dài hơn. Khởi động lại backend vẫn giữ thời gian chờ.
- Lưu bản dịch thành công theo nội dung nguồn, ngôn ngữ nguồn/đích và chế độ nhà cung cấp trong thư mục riêng của runtime media. Mặc định dùng lại trong 30 ngày; đổi nội dung hoặc ngôn ngữ sẽ có khóa khác.
- Chống các yêu cầu đồng thời tạo cùng bản dịch; dùng chung giới hạn 3 lượt dịch/TTS.
- Chia nội dung gửi MyMemory thành các đoạn tối đa **500 byte UTF-8**, giữ nguyên ký tự tiếng Việt và emoji khi chia đoạn.
- Nếu MyMemory hết hạn mức hoặc trả phản hồi sai, báo lỗi rõ và trả `Retry-After`. Thông báo hết hạn mức không được lưu làm bản dịch hay chuyển thành MP3.
- Lệnh kiểm tra in rõ nhà cung cấp thực tế và `cache: HIT/MISS`. HIT dùng kết quả đã lưu; MISS mới cần gọi mạng.

## Cập nhật trên Windows

1. Tải ZIP mới và giải nén vào thư mục riêng, ví dụ `Downloads\SmartStay_SuaDich_429`.
2. Mở thư mục `SmartStay-Booking` bên trong gói vừa giải nén. Thư mục này có file hướng dẫn đang đọc.
3. Mở Terminal tại thư mục đó, chạy:

```powershell
python .\AP_DUNG_SUA_5_LOI.py --project "C:\Users\ACER NITRO 5\Downloads\SmartStay-Booking-Fullstack\SmartStay-Booking"
```

4. Chỉ khi hiện `DA CAP NHAT`, chuyển về backend cũ rồi build và kiểm tra:

```powershell
cd "C:\Users\ACER NITRO 5\Downloads\SmartStay-Booking-Fullstack\SmartStay-Booking\smartstay-backend"
docker compose up -d --build backend
docker compose exec -T backend python integration/check_providers.py
```

Không cần sửa `.env` cho chế độ mặc định. Công cụ cập nhật giữ cấu hình riêng và dữ liệu Docker, đồng thời sao lưu mã trước khi chép.

Nếu muốn kiểm tra riêng MyMemory:

```powershell
docker compose exec -T backend python integration/check_providers.py --provider mymemory
```

Tùy chọn `--fresh` bỏ qua cache kết quả và tạo câu kiểm tra giọng nói mới. Tùy chọn này vẫn tôn trọng thời gian chờ của nhà cung cấp; mỗi lần chạy sẽ phát sinh yêu cầu mới và tiêu thụ hạn mức.

## Hạn mức và cấu hình

Theo tài liệu MyMemory đã kiểm tra ngày 25/10/2026:

- Ẩn danh: **5.000 ký tự/ngày**.
- Cung cấp email liên hệ hợp lệ bằng tham số `de`: **50.000 ký tự/ngày**.
- Mỗi đoạn gửi: tối đa **500 byte UTF-8**. Một mô tả dài dịch sang nhiều ngôn ngữ sẽ tiêu thụ hạn mức tương ứng.

Nếu muốn dùng email liên hệ của mình, thêm vào `.env` backend cũ rồi tạo lại container backend:

```dotenv
MYMEMORY_EMAIL=email-lien-he-cua-ban
```

Đổi giá trị trên thành email hợp lệ của bạn. Để trống nếu muốn tiếp tục dùng chế độ ẩn danh. Email được gửi cho MyMemory cùng yêu cầu theo cơ chế hạn mức của họ.

Các tùy chọn khác:

```dotenv
TRANSLATION_PROVIDER=auto
TRANSLATION_CACHE_TTL_SECONDS=2592000
TRANSLATION_GOOGLE_COOLDOWN_SECONDS=900
```

`TRANSLATION_PROVIDER` nhận `auto`, `google` hoặc `mymemory`. Cache của từng chế độ tách riêng. Mặc định `auto` nên Google bị 429 sẽ có nguồn dự phòng; không xoay proxy, không tự giải CAPTCHA và không tắt kiểm tra TLS.

## Phạm vi xác nhận

Đã có kiểm tra tự động mô phỏng hợp đồng HTTP của nhà cung cấp, Google 429, hết hạn mức, cache qua khởi động lại, nội dung nhiều byte, giới hạn đồng thời và luồng API on-demand → bản dịch → MP3 → media công khai. Các cuộc gọi nhà cung cấp trong unit test được giả lập; nội dung giả lập chỉ dùng trong kiểm thử.

Mạng kiểm tra độc lập chưa xác nhận được phản hồi MyMemory trực tiếp. Cần chạy lệnh `check_providers.py` trên Docker của bạn để xác nhận kết nối thực tế. Bản vá này sửa cách xử lý lỗi và bổ sung dự phòng; không mở khóa IP ở Google và không bảo đảm hạn mức miễn phí luôn còn.

Gói này tập trung vào lỗi nhà cung cấp dịch thuật. Những khác biệt giai đoạn 4 đã đối chiếu trước đó như Activation Gate tự động khi sửa mô tả, header `X-Static-Url`, bảng điều khiển SSE trên React và giới hạn warmup/manifest vẫn cần hoàn thiện riêng.

Nguồn: [MyMemory API](https://mymemory.translated.net/doc/spec.php), [MyMemory usage limits](https://mymemory.translated.net/doc/usagelimits.php).
