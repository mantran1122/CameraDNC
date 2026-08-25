# Chuyển tiếng nói camera live thành văn bản

Luồng này chạy song song với Cosmos hình ảnh:

```text
NetSDK live stream -> đoạn DAV tạm -> FFmpeg (WAV 16 kHz) -> POST /transcribe -> Whisper -> cột TIẾNG NÓI
```

## Điều kiện

- Camera/đầu ghi phải bật audio cho kênh đang xem và phía vận hành phải cho phép xử lý audio.
- Máy chạy `NetSDK_Camera` cần có `ffmpeg` trong `PATH`.
- `live_service.py` cần chạy ở máy GPU, có `transformers` và quyền tải model
  `openai/whisper-small` lần đầu.

## Chạy service

```bash
export COSMOS_LIVE_PROMPT_PROFILE=admissions
export COSMOS_AUDIO_LANGUAGE=vi
export COSMOS_AUDIO_MIN_RMS=0.003
python live_service.py --host 0.0.0.0 --port 8766 --gpu-memory-utilization 0.55
```

## Chạy app camera trên Windows

```powershell
$env:COSMOS_LIVE_URL = "http://127.0.0.1:8766/analyze"
$env:COSMOS_SAMPLE_INTERVAL_SECONDS = "10"
$env:COSMOS_AUDIO_INTERVAL_SECONDS = "15"
$env:COSMOS_AUDIO_CHUNK_SECONDS = "10"
python .\launcher.py
```

Trong **Xem camera trực tiếp**, bật cả hai ô: **Phân tích Cosmos** và
**Chuyển tiếng nói thành văn bản**.

Nút biểu tượng loa dưới khung video bật/tắt âm thanh nghe trực tiếp qua NetSDK.
Nút này độc lập với ô chuyển lời nói thành văn bản.

Service dùng VAD theo từng frame để bỏ qua im lặng/nhiễu đều, áp ngưỡng no-speech
của Whisper, chặn transcript lặp giữa các chunk và các mẫu hallucination phổ biến
như lời mời đăng ký kênh. Có thể tăng `COSMOS_AUDIO_MIN_RMS` nếu camera có nhiễu
nền liên tục, hoặc giảm nhẹ nếu giọng nói ở xa bị bỏ qua.

Mặc định app ghi một đoạn ngắn trực tiếp từ `playID` NetSDK đang mở. Vì vậy
không cần public/NAT cổng RTSP 554. Đoạn DAV tạm được xóa ngay sau khi FFmpeg
tách audio.

Chỉ khi chủ động đặt `$env:COSMOS_AUDIO_SOURCE = "rtsp"`, app mới dùng RTSP Dahua:

```text
rtsp://<user>:<password>@<host>:554/cam/realmonitor?channel=<1-based>&subtype=<0-or-1>
```

Nếu đầu ghi dùng RTSP URL khác, đặt template này trước khi mở app. Các biến
`{host}`, `{username}`, `{password}`, `{channel}`, `{subtype}` sẽ được thay tự động:

```powershell
$env:COSMOS_AUDIO_RTSP_URL = "rtsp://{username}:{password}@{host}:554/cam/realmonitor?channel={channel}&subtype={subtype}"
```

Nếu đầu ghi không mở RTSP ở cổng 554, đặt cổng thật trước khi mở app:

```powershell
$env:COSMOS_AUDIO_RTSP_PORT = "554"
$env:COSMOS_AUDIO_CONNECT_TIMEOUT_SECONDS = "8"
```

Lỗi `RTSP quá thời gian kết nối` nghĩa là Windows không truy cập được cổng
RTSP của đầu ghi, không phải lỗi Whisper. Kiểm tra nhanh bằng
`Test-NetConnection <IP> -Port <RTSP_PORT>`.

NetSDK tạo một đoạn DAV tạm trong thư mục temp của Windows để lấy cả audio từ
kết nối SDK; client xóa đoạn này ngay sau khi FFmpeg xử lý. WAV được gửi trong
bộ nhớ và service xóa file WAV tạm ngay sau khi Whisper hoàn tất.
