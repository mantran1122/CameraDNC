# Chuyển tiếng nói camera live thành văn bản

Luồng này chạy song song với Cosmos hình ảnh:

```text
RTSP audio của đầu ghi -> FFmpeg (WAV 16 kHz) -> POST /transcribe -> Whisper -> cột TIẾNG NÓI
```

## Điều kiện

- Camera/đầu ghi phải bật audio cho kênh đang xem và phía vận hành phải cho phép xử lý audio.
- Máy chạy `NetSDK_Camera` cần có `ffmpeg` trong `PATH`.
- `live_service.py` cần chạy ở máy GPU, có `transformers` và quyền tải model
  `openai/whisper-base` lần đầu.

## Chạy service

```bash
export COSMOS_LIVE_PROMPT_PROFILE=admissions
export COSMOS_AUDIO_LANGUAGE=vi
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

Mặc định app dùng RTSP Dahua:

```text
rtsp://<user>:<password>@<host>:554/cam/realmonitor?channel=<1-based>&subtype=<0-or-1>
```

Nếu đầu ghi dùng RTSP URL khác, đặt template này trước khi mở app. Các biến
`{host}`, `{username}`, `{password}`, `{channel}`, `{subtype}` sẽ được thay tự động:

```powershell
$env:COSMOS_AUDIO_RTSP_URL = "rtsp://{username}:{password}@{host}:554/cam/realmonitor?channel={channel}&subtype={subtype}"
```

Audio không được ghi vào đĩa: FFmpeg gửi WAV trong bộ nhớ; service xóa file tạm
ngay sau khi Whisper hoàn tất.
