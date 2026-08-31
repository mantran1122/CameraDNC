import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
CLIPS_DIR = STORAGE_DIR / "clips"
CONFIG_FILE = STORAGE_DIR / "nvr_config.json"

# Ensure directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

# Default NVR Configuration
DEFAULT_CONFIG = {
    "nvr_host": "192.168.1.108",
    "use_https": False,
    "nvr_port": 80,
    "rtsp_port": 554,
    "nvr_user": "admin",
    "nvr_password": "admin123",
    "active_channels": list(range(1, 33)),  # 1 to 32
    "demo_mode": True,
    "pre_buffer_sec": 5,
    "post_buffer_sec": 5
}

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                return merged
        except Exception as e:
            print(f"[Config] Error loading nvr_config.json: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(cfg_dict: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg_dict, f, indent=4, ensure_ascii=False)

# Load global variables
_current_cfg = load_config()

NVR_HOST = _current_cfg.get("nvr_host", "192.168.1.108")
USE_HTTPS = _current_cfg.get("use_https", False)
NVR_PORT = _current_cfg.get("nvr_port", 80)
RTSP_PORT = _current_cfg.get("rtsp_port", 554)
NVR_USER = _current_cfg.get("nvr_user", "admin")
NVR_PASSWORD = _current_cfg.get("nvr_password", "admin123")
ACTIVE_CHANNELS = _current_cfg.get("active_channels", list(range(1, 33)))
DEMO_MODE = _current_cfg.get("demo_mode", True)
PRE_BUFFER_SEC = _current_cfg.get("pre_buffer_sec", 5)
POST_BUFFER_SEC = _current_cfg.get("post_buffer_sec", 5)
CLIP_DURATION_SEC = PRE_BUFFER_SEC + POST_BUFFER_SEC
COSMOS_AUDIO_URL = os.getenv("COSMOS_AUDIO_URL", "http://127.0.0.1:8765/transcribe")

def get_ffmpeg_executable():
    import shutil
    env_path = os.getenv("FFMPEG_PATH")
    if env_path and os.path.exists(env_path):
        return env_path
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_executable()

def get_ffprobe_executable():
    import shutil
    return os.getenv("FFPROBE_PATH") or shutil.which("ffprobe") or "ffprobe"

FFPROBE_PATH = get_ffprobe_executable()

EVENT_CODES = [
    "All",
    "VideoMotion",
    "Intrusion",
    "CrossLine",
    "AudioAnomaly",
    "SoundDetection",
    "FaceDetection",
    "HumanTrait",
    "VehicleTrait",
    "Fight"
]

def update_global_config(new_cfg: dict):
    global NVR_HOST, USE_HTTPS, NVR_PORT, RTSP_PORT, NVR_USER, NVR_PASSWORD, ACTIVE_CHANNELS, DEMO_MODE
    save_config(new_cfg)
    NVR_HOST = new_cfg.get("nvr_host", NVR_HOST)
    USE_HTTPS = new_cfg.get("use_https", USE_HTTPS)
    NVR_PORT = new_cfg.get("nvr_port", NVR_PORT)
    RTSP_PORT = new_cfg.get("rtsp_port", RTSP_PORT)
    NVR_USER = new_cfg.get("nvr_user", NVR_USER)
    NVR_PASSWORD = new_cfg.get("nvr_password", NVR_PASSWORD)
    ACTIVE_CHANNELS = new_cfg.get("active_channels", ACTIVE_CHANNELS)
    DEMO_MODE = new_cfg.get("demo_mode", DEMO_MODE)
