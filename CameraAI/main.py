import os
import json
import asyncio
from urllib.parse import quote
from typing import List, Optional
from datetime import date
import requests
from requests.auth import HTTPDigestAuth

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import config
import database
import summary_engine
import video_clipper
from audio_analysis_worker import AudioAnalysisWorker
from dahua_client import DahuaNVRListener
from simulator import NVRDataSimulator

import cv2
import numpy as np
import time

app = FastAPI(
    title="Dahua DHI-NVR5832-EI2 Internet AI Metadata & Anomaly Summarizer",
    description="Hệ thống Phân tích Metadata & Tóm tắt Hoạt động Ngày (Video + Audio) Kết nối Đầu ghi qua Internet/WAN/DDNS",
    version="2.0.0"
)

static_dir = config.BASE_DIR / "static"
templates_dir = config.BASE_DIR / "templates"
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/clips", StaticFiles(directory=str(config.CLIPS_DIR)), name="clips")

templates = Jinja2Templates(directory=str(templates_dir))

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

nvr_listener = None
simulator_thread = None
audio_analysis_worker = None
# The FastAPI/Uvicorn event loop belongs to the server thread. Listener and
# simulator threads use this stored reference to schedule WebSocket broadcasts.
server_event_loop: Optional[asyncio.AbstractEventLoop] = None

def broadcast_event_sync(event_obj: dict):
    loop = server_event_loop
    if loop is None or not loop.is_running():
        # This is expected while the application is starting or stopping.
        return

    try:
        asyncio.run_coroutine_threadsafe(manager.broadcast(event_obj), loop)
    except Exception as e:
        print(f"[WebSocket Broadcast Error] {e}")

def restart_listener_service():
    global nvr_listener, simulator_thread, audio_analysis_worker
    if nvr_listener:
        nvr_listener.stop()
    if simulator_thread:
        simulator_thread.stop()
    if audio_analysis_worker:
        audio_analysis_worker.stop()

    nvr_listener = None
    simulator_thread = None
    audio_analysis_worker = AudioAnalysisWorker(on_updated=broadcast_audio_analysis_update)
    audio_analysis_worker.start()

    # Demo data must never be created while connected to a production NVR.
    if config.DEMO_MODE:
        simulator_thread = NVRDataSimulator(
            broadcast_callback=broadcast_event_sync,
            audio_job_callback=audio_analysis_worker.enqueue,
        )
        simulator_thread.start()

    # Process alarm clips that were saved before this feature was enabled.
    # The cap avoids a restart unexpectedly creating an unbounded backlog.
    for event_id in database.get_unanalyzed_audio_event_ids(config.AUDIO_ANALYSIS_BACKFILL_LIMIT):
        database.create_audio_analysis(event_id)
        audio_analysis_worker.enqueue(event_id)

    nvr_listener = DahuaNVRListener(
        broadcast_callback=broadcast_event_sync,
        audio_job_callback=audio_analysis_worker.enqueue,
    )
    nvr_listener.start()

@app.on_event("startup")
async def startup_event():
    global server_event_loop
    server_event_loop = asyncio.get_running_loop()
    database.init_db()
    restart_listener_service()
    print("[Server Startup] Dahua Internet Metadata & Anomaly Summarizer online.")

@app.on_event("shutdown")
async def shutdown_event():
    global nvr_listener, simulator_thread, audio_analysis_worker, server_event_loop
    if nvr_listener:
        nvr_listener.stop()
    if simulator_thread:
        simulator_thread.stop()
    if audio_analysis_worker:
        audio_analysis_worker.stop()
    server_event_loop = None


def broadcast_audio_analysis_update(event_id: int):
    event = database.get_event_by_id(event_id)
    if event:
        event["audio_analysis"] = database.get_audio_analysis(event_id)
        broadcast_event_sync(event)

# --- ROUTES & APIS ---

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/events")
async def get_events_api(
    event_type: Optional[str] = None,
    channel: Optional[int] = None,
    only_anomalies: bool = False,
    limit: int = 50
):
    events = database.get_events(
        event_type=event_type,
        channel=channel,
        limit=limit,
        only_anomalies=only_anomalies
    )
    for event in events:
        event["audio_analysis"] = database.get_audio_analysis(event["id"])
    return {"events": events, "count": len(events)}

@app.get("/api/events/{event_id}")
async def get_event_detail(event_id: int):
    ev = database.get_event_by_id(event_id)
    if not ev:
        return JSONResponse(status_code=404, content={"error": "Event not found"})
    ev["audio_analysis"] = database.get_audio_analysis(event_id)
    return ev

@app.post("/api/events/{event_id}/audio-analysis")
async def request_audio_analysis(event_id: int):
    """Queue speech-to-text for the anomaly clip selected by an operator."""
    event = database.get_event_by_id(event_id)
    if not event:
        return JSONResponse(status_code=404, content={"error": "Event not found"})
    if event["event_type"] not in {"audio_anomaly", "video_anomaly"}:
        return JSONResponse(status_code=400, content={"error": "Chỉ sự kiện bất thường mới có thể phân tích âm thanh."})
    if not event.get("clip_filename"):
        return JSONResponse(status_code=409, content={"error": "Sự kiện này chưa có clip để phân tích."})
    clip_path = config.CLIPS_DIR / os.path.basename(str(event["clip_filename"]))
    if not clip_path.is_file():
        return JSONResponse(status_code=409, content={"error": "Không tìm thấy file clip đang xem lại để phân tích."})
    if audio_analysis_worker is None:
        return JSONResponse(status_code=503, content={"error": "Audio worker chưa sẵn sàng."})

    analysis = database.get_audio_analysis(event_id)
    active_statuses = {"pending", "waiting_for_post_buffer", "downloading_clip", "extracting_audio", "transcribing", "generating_suggestion"}
    if analysis and analysis["status"] in active_statuses | {"completed", "no_audio"}:
        return {"queued": False, "audio_analysis": analysis}

    if analysis is None:
        database.create_audio_analysis(event_id)
    else:
        database.update_audio_analysis(event_id, status="pending", error_message=None)
    analysis = database.get_audio_analysis(event_id)
    broadcast_audio_analysis_update(event_id)
    audio_analysis_worker.enqueue(event_id)
    return {"queued": True, "audio_analysis": analysis}

@app.get("/api/summary/daily")
async def get_daily_summary_api(date_str: Optional[str] = None):
    summary = summary_engine.generate_daily_summary(date_str)
    return summary

def generate_frames(channel: int):
    rtsp_user = quote(str(config.NVR_USER), safe="")
    rtsp_password = quote(str(config.NVR_PASSWORD), safe="")
    rtsp_url = f"rtsp://{rtsp_user}:{rtsp_password}@{config.NVR_HOST}:{config.RTSP_PORT}/cam/realmonitor?channel={channel}&subtype=1"
    
    if config.DEMO_MODE:
        cap = None
    else:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    
    while True:
        if config.DEMO_MODE:
            frame = np.full((360, 640, 3), (20, 24, 33), dtype=np.uint8)
            cv2.putText(frame, f"LIVE CAM {channel:02d} (DEMO MODE)", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(frame, f"NVR: {config.NVR_HOST}:{config.RTSP_PORT}", (50, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 200), 2)
            if int(time.time() * 2) % 2 == 0:
                cv2.circle(frame, (600, 30), 10, (0, 0, 255), -1)
            ret = True
            time.sleep(0.1)
        else:
            if cap is None or not cap.isOpened():
                break
            ret, frame = cap.read()
            if not ret:
                break
            
        ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
               
    if cap is not None:
        cap.release()

@app.get("/api/stream/live/{channel}")
async def live_stream(channel: int):
    return StreamingResponse(generate_frames(channel), media_type="multipart/x-mixed-replace; boundary=frame")

class NVRConfigModel(BaseModel):
    nvr_host: str
    use_https: bool = False
    nvr_port: int = 80
    rtsp_port: int = 554
    nvr_user: str = "admin"
    nvr_password: str
    active_channels: List[int] = list(range(1, 33))
    demo_mode: bool = False

@app.get("/api/config/nvr")
async def get_nvr_config():
    return {
        "nvr_host": config.NVR_HOST,
        "use_https": config.USE_HTTPS,
        "nvr_port": config.NVR_PORT,
        "rtsp_port": config.RTSP_PORT,
        "nvr_user": config.NVR_USER,
        "active_channels": config.ACTIVE_CHANNELS,
        "demo_mode": config.DEMO_MODE,
        "ffmpeg_available": True
    }

@app.post("/api/config/nvr/test")
async def test_nvr_connection(cfg: NVRConfigModel):
    """
    Tests connection to Dahua NVR over Internet / DDNS / WAN using CGI device info API.
    """
    if cfg.demo_mode:
        return {
            "success": True,
            "demo": True,
            "device_model": "DHI-NVR5832-EI2 (Chế độ Giả lập)",
            "serial_number": "7G098234910293",
            "firmware": "v4.002.0000000.1.R",
            "message": "✅ Chế độ Giả lập (Demo Mode) đang hoạt động hoàn hảo!"
        }

    protocol = "https" if cfg.use_https else "http"
    url = f"{protocol}://{cfg.nvr_host}:{cfg.nvr_port}/cgi-bin/devInfo.cgi?action=getDeviceInfo"
    auth = HTTPDigestAuth(cfg.nvr_user, cfg.nvr_password)

    try:
        res = requests.get(url, auth=auth, timeout=8, verify=False)
        if res.status_code == 200:
            lines = res.text.splitlines()
            info_dict = {}
            for line in lines:
                if "=" in line:
                    k, v = line.split("=", 1)
                    info_dict[k.strip()] = v.strip()

            device_type = info_dict.get("deviceType", "Dahua NVR")
            serial_no = info_dict.get("serialNumber", "N/A")
            firmware_ver = info_dict.get("softwareVersion", "N/A")

            return {
                "success": True,
                "demo": False,
                "device_model": device_type,
                "serial_number": serial_no,
                "firmware": firmware_ver,
                "message": f"✅ KẾT NỐI THÀNH CÔNG TỚI ĐẦU GHI {device_type}! (S/N: {serial_no})"
            }
        elif res.status_code in [401, 403]:
            return {
                "success": False,
                "message": f"❌ Lỗi Xác thực ({res.status_code}): Sai Tên đăng nhập hoặc Mật khẩu NVR."
            }
        else:
            return {
                "success": False,
                "message": f"❌ Đầu ghi phản hồi mã lỗi HTTP {res.status_code}. Kiểm tra lại cấu hình NAT/Port Forwarding."
            }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": f"❌ Hết thời gian chờ (Timeout 8s). Không thể kết nối tới IP/Tên miền {cfg.nvr_host}:{cfg.nvr_port}. Kiểm tra DDNS/IP Tĩnh và Cổng HTTP."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Không thể kết nối tới NVR qua Internet: {str(e)}"
        }

@app.post("/api/config/nvr")
async def update_nvr_config(cfg: NVRConfigModel):
    cfg_dict = cfg.dict()
    config.update_global_config(cfg_dict)
    restart_listener_service()
    return {"status": "success", "message": f"Cấu hình kết nối NVR ({cfg.nvr_host}) đã được cập nhật thành công!"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
