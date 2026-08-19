# Hướng dẫn mở Cosmos thủ công

Tài liệu này dùng khi ứng dụng báo:

```text
Cosmos: không kết nối được
<urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
```

Lỗi trên có nghĩa là dịch vụ Cosmos tại cổng `8765` chưa chạy hoặc đã bị tắt.

## Cách mở nhanh từ PowerShell

Mở một cửa sổ PowerShell mới và chạy nguyên lệnh sau:

```powershell
wsl -d Ubuntu-20.04 -- bash -lc 'cd ~/CameraDNC/cosmos_code_base && source .venv/bin/activate && export CUDA_HOME=/usr/local/cuda && export PATH=/usr/local/cuda/bin:$PATH && export VLLM_USE_FLASHINFER_SAMPLER=0 && python live_service.py --host 0.0.0.0 --port 8765 --gpu-memory-utilization 0.55 --max-model-len 6144 --max-new-tokens 512'
```

Giữ nguyên cửa sổ PowerShell này trong lúc sử dụng chức năng phân tích Live. Không bấm `Ctrl+C` và không đóng cửa sổ, vì làm vậy sẽ tắt Cosmos.

Khi xuất hiện dòng dưới đây thì HTTP server đã mở:

```text
Uvicorn running on http://0.0.0.0:8765
```

Model có thể vẫn cần thêm thời gian để nạp GPU. Trong lúc đó `/health` có thể trả về trạng thái `loading`.

## Cách mở từng bước trong Ubuntu

Từ PowerShell:

```powershell
wsl -d Ubuntu-20.04
```

Sau đó chạy trong Ubuntu:

```bash
cd ~/CameraDNC/cosmos_code_base
source .venv/bin/activate
export CUDA_HOME=/usr/local/cuda
export PATH=/usr/local/cuda/bin:$PATH
export VLLM_USE_FLASHINFER_SAMPLER=0
python live_service.py --host 0.0.0.0 --port 8765 --gpu-memory-utilization 0.55 --max-model-len 6144 --max-new-tokens 512
```

## Kiểm tra từ PowerShell

Mở cửa sổ PowerShell khác và chạy:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing | Select-Object -ExpandProperty Content
```

Các trạng thái thường gặp:

```json
{"status":"loading"}
```

Cosmos đang nạp model, tiếp tục chờ.

```json
{"status":"ready"}
```

Cosmos đã sẵn sàng phân tích.

Nếu PowerShell vẫn báo `Unable to connect to the remote server`, quay lại cửa sổ đang chạy Cosmos và đọc lỗi cuối cùng ở đó.

## Kiểm tra cổng trong WSL

```powershell
wsl -d Ubuntu-20.04 -- bash -lc "ss -ltnp | grep ':8765' || true"
```

Nếu không có kết quả thì tiến trình Cosmos không còn chạy.

## Khi cổng 8765 đã bị chiếm

Nếu có lỗi:

```text
address already in use
```

Kiểm tra tiến trình trước:

```powershell
wsl -d Ubuntu-20.04 -- bash -lc "ss -ltnp | grep ':8765' || true"
```

Nếu dịch vụ cũ bị treo và cần khởi động lại, đóng ứng dụng camera trước rồi chạy:

```powershell
wsl -d Ubuntu-20.04 -- bash -lc "fuser -k 8765/tcp || true"
```

Sau đó chạy lại lệnh mở Cosmos ở đầu tài liệu.

## Phân biệt hai dịch vụ

- `live_service.py`, cổng `8765`: phân tích hình ảnh từ camera Live trong ứng dụng NetSDK.
- `app/streamlit_app.py`, cổng `8501`: trang web phân tích video Playback/upload.

Lỗi `Cosmos: không kết nối được ... 10061` trong cửa sổ Live liên quan đến `live_service.py` ở cổng `8765`, không phải Streamlit.

## Mở trang Streamlit thủ công

Từ PowerShell:

```powershell
cd D:\dnc\cosmos_code_base
.\run_streamlit.bat
```

Sau đó mở:

```text
http://127.0.0.1:8501
```

Streamlit và `live_service.py` là hai tiến trình riêng. Tùy chức năng đang dùng, có thể cần mở một hoặc cả hai.
