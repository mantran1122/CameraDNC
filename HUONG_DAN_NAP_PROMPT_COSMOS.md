# Hướng dẫn quản lý và nạp prompt cho Cosmos theo camera

## 1. Mục đích

Hệ thống có nhiều camera với bối cảnh khác nhau, ví dụ:

- Phòng học.
- Sảnh và khu chờ.
- Phòng làm việc, phòng ban.
- Khu vực tuyển sinh.
- Hành lang, lối đi.

Không nên dùng một prompt chuyên biệt cho tất cả camera. Prompt tuyển sinh sẽ hiểu sai phòng học; prompt phòng học cũng không phù hợp với sảnh hoặc phòng làm việc.

Nên quản lý prompt theo **profile khu vực**, sau đó kích hoạt profile phù hợp trước khi phân tích.

## 2. Hai loại prompt đang có trong dự án

### 2.1. Prompt Playback và video upload

File đang được sử dụng:

```text
D:\dnc\CameraDNC\cosmos_code_base\prompts\chunk_prompt.txt
```

Áp dụng cho:

- Video lấy từ chức năng Playback.
- Video MP4 upload lên Streamlit.
- Video được chọn từ thư mục server trên Streamlit.

Pipeline đọc file này khi tiến trình `main.py` bắt đầu phân tích video.

### 2.2. Prompt camera Live

File đang được sử dụng:

```text
D:\dnc\CameraDNC\cosmos_code_base\prompts\live_admissions_prompt.txt
```

Áp dụng cho endpoint Live:

```text
http://127.0.0.1:8765/analyze
```

`live_service.py` đọc lại file prompt cho mỗi yêu cầu phân tích ảnh, vì vậy thay đổi nội dung prompt có hiệu lực ở frame tiếp theo.

## 3. Giới hạn quan trọng của Live hiện tại

Live hiện được viết chuyên cho khu tuyển sinh:

- Luôn chạy `YellowUniformDetector`.
- Luôn chèn số người mặc đồng phục vàng-xanh vào prompt.
- Luôn thêm sự kiện `nhan_vien_ao_vang` vào kết quả.

Do đó, chỉ thay nội dung `live_admissions_prompt.txt` chưa đủ để biến Live thành profile phòng học hoặc phòng ban. Camera không thuộc tuyển sinh vẫn có thể nhận dữ kiện không phù hợp về áo vàng.

Trong phiên bản hiện tại:

- Có thể thay prompt Playback an toàn theo từng loại khu vực.
- Live nên tiếp tục dùng cho camera tuyển sinh.
- Muốn Live tự chọn đúng profile cho từng camera cần bổ sung mapping `camera/channel -> prompt profile + detector profile` trong code.

## 4. Cấu trúc thư mục profile đề xuất

Tạo thư mục:

```text
cosmos_code_base\prompts\profiles\
```

Đặt tên file rõ ràng:

```text
profiles\playback_general.txt
profiles\playback_classroom.txt
profiles\playback_lobby.txt
profiles\playback_office.txt
profiles\playback_admissions.txt
profiles\live_admissions.txt
```

File đang hoạt động vẫn là:

```text
prompts\chunk_prompt.txt
prompts\live_admissions_prompt.txt
```

Các file trong `profiles` là bản mẫu. Khi cần dùng profile nào, sao chép profile đó vào file đang hoạt động.

## 5. Cách nạp prompt Playback

Ví dụ kích hoạt prompt phòng học:

```powershell
cd D:\dnc\CameraDNC\cosmos_code_base
Copy-Item .\prompts\profiles\playback_classroom.txt .\prompts\chunk_prompt.txt -Force
```

Kích hoạt prompt sảnh:

```powershell
Copy-Item .\prompts\profiles\playback_lobby.txt .\prompts\chunk_prompt.txt -Force
```

Kích hoạt prompt phòng ban:

```powershell
Copy-Item .\prompts\profiles\playback_office.txt .\prompts\chunk_prompt.txt -Force
```

Kích hoạt prompt tuyển sinh:

```powershell
Copy-Item .\prompts\profiles\playback_admissions.txt .\prompts\chunk_prompt.txt -Force
```

Sau khi sao chép:

- Nếu chưa bắt đầu phân tích: bấm **Phân tích AI** bình thường.
- Nếu một video đang phân tích: dừng tiến trình hiện tại rồi bấm **Phân tích lại**.
- Không cần khởi động lại Streamlit nếu chỉ thay `chunk_prompt.txt`, vì mỗi lần phân tích tạo một tiến trình `main.py` mới.
- Thay prompt không làm thay đổi kết quả cũ. Muốn kết quả cũ dùng prompt mới phải phân tích lại video.

## 6. Cách nạp prompt Live tuyển sinh

```powershell
cd D:\dnc\CameraDNC\cosmos_code_base
Copy-Item .\prompts\profiles\live_admissions.txt .\prompts\live_admissions_prompt.txt -Force
```

Prompt mới được đọc ở yêu cầu Live tiếp theo. Thông thường không cần nạp lại model.

Nếu giao diện vẫn hiện nội dung cũ, khởi động lại dịch vụ Live:

```powershell
wsl -d Ubuntu-20.04 -- bash -lc "fuser -k 8765/tcp || true"
```

Sau đó chạy lại lệnh Cosmos trong tài liệu:

```text
HUONG_DAN_MO_COSMOS_THU_CONG.md
```

## 7. Cách viết một prompt profile

Một profile nên có sáu phần.

### 7.1. Ngôn ngữ bắt buộc

Luôn giữ quy tắc:

```text
Toàn bộ giá trị văn bản trong JSON phải viết bằng tiếng Việt tự nhiên, có dấu.
Không dùng tiếng Trung, chữ Hán hoặc câu tiếng Anh.
Chỉ trả về JSON hợp lệ, không markdown và không giải thích ngoài JSON.
```

### 7.2. Bối cảnh camera

Nêu đúng loại khu vực và góc nhìn:

```text
Đây là camera góc rộng quan sát phòng học từ vị trí trên cao.
```

Không ghi những điều không chắc chắn, chẳng hạn tên người hoặc chức vụ cụ thể.

### 7.3. Đối tượng cần quan sát

Ví dụ:

```text
Quan sát người đang ngồi, đứng, di chuyển, ra vào và tương tác với thiết bị hoặc đồ vật.
```

Nếu nhận diện nhân viên bằng đồng phục, phải mô tả dấu hiệu thị giác cụ thể:

```text
Chỉ gọi là nhân viên áo vàng khi nhìn thấy rõ áo vàng hoặc đồng phục vàng-xanh.
```

### 7.4. Hoạt động bình thường

Nêu các hoạt động không nên báo động để giảm cảnh báo giả.

Ví dụ phòng học:

```text
Ngồi học, viết bài, nhìn bảng, giảng bài và di chuyển ngắn trong lớp là hoạt động bình thường.
```

### 7.5. Sự kiện cần chú ý

Chỉ liệt kê sự kiện có ý nghĩa đối với khu vực:

```text
Chú ý người bị ngã, xô xát, khói hoặc lửa, vật bị bỏ quên, lối đi bị chặn và người đi vào khu vực hạn chế.
```

Không nên biến mọi hoạt động thành bất thường. Ví dụ dùng điện thoại có thể cần chú ý ở lớp học nhưng hoàn toàn bình thường tại sảnh chờ.

### 7.6. Schema đầu ra

Không được xóa hoặc đổi tên các khóa mà code đang sử dụng:

```json
{
  "start": "{START_TIME}",
  "end": "{END_TIME}",
  "description": "Mô tả bằng tiếng Việt.",
  "people_count": "unknown",
  "phone_detected": false,
  "crowd_detected": false,
  "objects": [],
  "actions": [],
  "scene_changes": "không có thay đổi đáng kể",
  "abnormal": false,
  "abnormal_type": "none",
  "risk_level": "none",
  "important_event": {
    "has_event": false,
    "event": "none",
    "timestamp": "none"
  },
  "confidence": 0.0
}
```

Phải giữ nguyên hai placeholder:

```text
{START_TIME}
{END_TIME}
```

## 8. Nội dung riêng cho từng profile

### 8.1. Phòng học

Ưu tiên:

- Số người hiện diện.
- Người ngồi, đứng, đi lại hoặc ra vào.
- Hoạt động giảng dạy, viết bài, sử dụng máy tính.
- Người bị ngã, xô xát, khói/lửa.
- Tụ tập bất thường ở cửa hoặc lối đi.
- Dùng điện thoại chỉ đánh dấu theo chính sách thực tế của đơn vị.

Không suy đoán:

- Danh tính sinh viên hoặc giảng viên.
- Thái độ, cảm xúc hoặc mức độ chăm chỉ.
- Gian lận nếu không có bằng chứng hình ảnh rõ ràng.

### 8.2. Sảnh và khu chờ

Ưu tiên:

- Luồng người vào, ra và chờ đợi.
- Hàng chờ dài hoặc ùn tắc.
- Lối đi, cửa ra vào bị chặn.
- Người bị ngã hoặc cần hỗ trợ.
- Vật bị bỏ quên.
- Xô xát, khói/lửa hoặc xâm nhập khu vực cấm.

Dùng điện thoại và ngồi chờ thường là hoạt động bình thường.

### 8.3. Phòng ban và phòng làm việc

Ưu tiên:

- Số người hiện diện.
- Người ngồi tại bàn, sử dụng máy tính, trao đổi hoặc ra vào.
- Khách xuất hiện trong khu vực.
- Vật cản lối đi, người bị ngã, khói/lửa.
- Truy cập khu vực hạn chế khi có dấu hiệu thị giác rõ ràng.

Không dùng camera để suy đoán năng suất, cảm xúc hoặc nội dung màn hình riêng tư.

### 8.4. Tuyển sinh

Ưu tiên:

- Nhân viên mặc đồng phục vàng hoặc vàng-xanh.
- Quầy tiếp nhận, bàn nhập học, bàn tư vấn, khu chờ và lối đi.
- Nhân viên đang hỗ trợ, nhập liệu, hướng dẫn hoặc rời vị trí.
- Số người chờ, hàng chờ và ùn tắc.
- Quầy không có người phụ trách trong thời gian đáng chú ý.
- Xô xát, người bị ngã, vật bị bỏ quên, khói/lửa.

Không kết luận nhân viên vi phạm chỉ từ một khung hình. Cần mô tả bằng chứng nhìn thấy và giới hạn quan sát.

## 9. Sao lưu trước khi thay prompt

```powershell
cd D:\dnc\CameraDNC\cosmos_code_base
New-Item -ItemType Directory .\prompts\backup -Force | Out-Null
Copy-Item .\prompts\chunk_prompt.txt ".\prompts\backup\chunk_prompt_$(Get-Date -Format yyyyMMdd_HHmmss).txt"
```

Sao lưu prompt Live:

```powershell
Copy-Item .\prompts\live_admissions_prompt.txt ".\prompts\backup\live_prompt_$(Get-Date -Format yyyyMMdd_HHmmss).txt"
```

## 10. Kiểm tra prompt trước khi chạy

Kiểm tra file đúng UTF-8 và đúng nội dung:

```powershell
Get-Content .\prompts\chunk_prompt.txt -Encoding UTF8 -TotalCount 30
```

Kiểm tra hai placeholder:

```powershell
Select-String -Path .\prompts\chunk_prompt.txt -Pattern '\{START_TIME\}|\{END_TIME\}'
```

Phải tìm thấy cả hai giá trị.

Kiểm tra schema quan trọng:

```powershell
Select-String -Path .\prompts\chunk_prompt.txt -Pattern 'description|people_count|risk_level|important_event'
```

## 11. Quy trình thử prompt an toàn

1. Chọn một video ngắn từ 2 đến 5 phút, đúng camera cần cấu hình.
2. Kích hoạt profile tương ứng.
3. Phân tích video thử.
4. Kiểm tra từng timeline:
   - Có hoàn toàn bằng tiếng Việt không.
   - Có mô tả đúng loại khu vực không.
   - Có cảnh báo giả không.
   - Có bỏ sót sự kiện rõ ràng không.
5. Chỉ dùng cho video dài sau khi video thử đạt yêu cầu.

Không nên thử prompt mới lần đầu bằng video 20 đến 30 phút vì vừa tốn thời gian vừa khó xác định prompt sai ở đâu.

## 12. Khi quản lý nhiều camera đồng thời

Cách sao chép thủ công phù hợp để thử nghiệm, nhưng không phù hợp khi nhiều camera chạy đồng thời vì `chunk_prompt.txt` chỉ có một bản đang hoạt động.

Kiến trúc nên bổ sung trong phiên bản tiếp theo:

```json
{
  "1": {"name": "Phòng học A1", "prompt_profile": "classroom", "detector_profile": "general"},
  "5": {"name": "Sảnh chính", "prompt_profile": "lobby", "detector_profile": "general"},
  "18": {"name": "Tuyển sinh", "prompt_profile": "admissions", "detector_profile": "yellow_uniform"}
}
```

Khi đó Playback hoặc Live gửi thêm `channel`, backend tự chọn:

- File prompt đúng camera.
- Detector phù hợp.
- Quy tắc bất thường phù hợp.
- Tên khu vực hiển thị trong kết quả.

Đây là giải pháp đúng cho vận hành lâu dài; không nên tiếp tục đổi một file prompt chung khi nhiều camera phân tích cùng lúc.

## 13. Tóm tắt nhanh

- Playback/video: thay `prompts\chunk_prompt.txt`.
- Live tuyển sinh: thay `prompts\live_admissions_prompt.txt`.
- Prompt Playback mới áp dụng ở lần phân tích tiếp theo.
- Kết quả cũ phải phân tích lại.
- Giữ nguyên schema và `{START_TIME}`, `{END_TIME}`.
- Live hiện luôn dùng bộ nhận diện áo vàng, chưa phù hợp camera phòng học hoặc phòng ban.
- Nhiều camera đồng thời cần mapping camera sang prompt và detector, không dùng một prompt chung.
