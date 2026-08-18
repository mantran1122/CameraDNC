# coding=utf-8
"""
Dahua NetSDK Control Center  —  Professional Launcher
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Yêu cầu  : PyQt5  PyQtWebEngine
Chạy     : python launcher.py
"""
import sys
import os
import re
import time
import socket
import threading
import platform
import importlib
import json
from dataclasses import dataclass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import List, Optional

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QFont

from bridge import Bridge


# ══════════════════════════════════════════════════════════════════════
#  DEMO METADATA
# ══════════════════════════════════════════════════════════════════════
@dataclass
class DemoItem:
    label:       str
    module_path: str
    module_name: str
    class_name:  str
    icon_key:    str   # FA5 class, e.g. "fa-search"
    icon_fb:     str   # 2-char monogram (unused in web UI)
    description: str
    category:    str
    accent:      str
    keywords:    List[str]


DEMOS: List[DemoItem] = [
    DemoItem(
        "Tìm kiếm thiết bị",
        "Demo.SearchDeviceDemo.SearchDeviceDemo", "SearchDeviceDemo", "MyMainWindow",
        "fa-search", "SD",
        "Quét và phát hiện thiết bị Dahua trong mạng nội bộ.",
        "Thiết bị", "#3B82F6",
        ["tìm kiếm", "thiết bị", "mạng", "scan", "device", "network"],
    ),
    DemoItem(
        "Xem camera trực tiếp",
        "Demo.RealPlayDemo.RealPlayDemo", "RealPlayDemo", "MyMainWindow",
        "fa-video", "LV",
        "Mở luồng live view từ thiết bị hoặc camera.",
        "Camera", "#06B6D4",
        ["camera", "live", "view", "stream", "trực tiếp", "realplay"],
    ),
    DemoItem(
        "Chụp ảnh",
        "Demo.CapturePicture.CaptureDemo", "CaptureDemo", "CaptureWnd",
        "fa-camera", "CP",
        "Chụp snapshot từ luồng camera hiện tại.",
        "Camera", "#8B5CF6",
        ["chụp", "ảnh", "snapshot", "capture", "picture"],
    ),
    DemoItem(
        "Nghe cảnh báo",
        "Demo.AlarmListen.AlarmListenDemo", "AlarmListenDemo", "StartListenWnd",
        "fa-bell", "AL",
        "Lắng nghe và kiểm thử sự kiện cảnh báo từ thiết bị.",
        "Cảnh báo", "#F59E0B",
        ["cảnh báo", "alarm", "sự kiện", "event", "listen"],
    ),
    DemoItem(
        "Xem lại video",
        "Demo.PlayBackDemo.PlayBackDemo", "PlayBackDemo", "MyMainWindow",
        "fa-play-circle", "PB",
        "Truy xuất và phát lại video đã được ghi trên thiết bị.",
        "Playback", "#A855F7",
        ["playback", "xem lại", "video", "record", "replay"],
    ),
    DemoItem(
        "Điều khiển thiết bị",
        "Demo.DeviceControlDemo.DeviceControlDemo", "DeviceControlDemo", "MyMainWindow",
        "fa-sliders-h", "DC",
        "Thao tác cấu hình và điều khiển thiết bị từ xa.",
        "Thiết bị", "#64748B",
        ["điều khiển", "control", "config", "device", "thiết bị"],
    ),
    DemoItem(
        "Nhận diện khuôn mặt",
        "Demo.FaceRecognitionDemo.FaceRecognitionDemo", "FaceRecognitionDemo", "MyMainWindow",
        "fa-user-circle", "FR",
        "Demo tính năng AI nhận diện và phân tích khuôn mặt.",
        "AI", "#10B981",
        ["face", "khuôn mặt", "ai", "nhận diện", "recognition"],
    ),
    DemoItem(
        "Giao thông thông minh",
        "Demo.IntelligentTrafficDemo.TrafficDemo", "TrafficDemo", "TrafficWnd",
        "fa-road", "IT",
        "Kiểm thử demo phân tích giao thông thông minh.",
        "Giao thông", "#F43F5E",
        ["giao thông", "traffic", "intelligent", "xe", "biển số"],
    ),
]

CATEGORIES = ["Tất cả", "Thiết bị", "Camera", "Cảnh báo", "Playback", "AI", "Giao thông"]


# ══════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════
def _platform_short() -> str:
    s = platform.system()
    if s == "Windows":
        return f"Win {platform.release()}"
    return s


def _qt_version() -> str:
    try:
        from PyQt5.QtCore import QT_VERSION_STR
        return QT_VERSION_STR
    except Exception:
        return "—"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_ui_server(root_dir: str) -> int:
    port = _free_port()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root_dir, **kw)
        def log_message(self, *_):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port


def _extract_qwebchannel(ui_dir: str):
    dest = os.path.join(ui_dir, "js", "qwebchannel.js")
    if os.path.exists(dest):
        return
    from PyQt5.QtCore import QFile, QIODevice
    f = QFile(":/qtwebchannel/qwebchannel.js")
    if f.open(QIODevice.ReadOnly):
        with open(dest, "wb") as out:
            out.write(bytes(f.readAll()))
        f.close()


# ══════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════
class Launcher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dahua NetSDK Control Center")
        self.resize(1120, 730)
        self.setMinimumSize(900, 600)

        self._active_window      = None
        self._active_module_path = ""
        self._demo_close_cb      = None

        # ── WebView ──────────────────────────────────────────────────
        self._view = QWebEngineView()
        self.setCentralWidget(self._view)

        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # ── Bridge + Channel ─────────────────────────────────────────
        self._bridge  = Bridge(self, self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("backend", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # ── HTTP server ───────────────────────────────────────────────
        root_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir   = os.path.join(root_dir, "ui")
        _extract_qwebchannel(ui_dir)
        port = _start_ui_server(root_dir)

        self._view.load(QUrl(f"http://127.0.0.1:{port}/ui/"))
        self._view.loadFinished.connect(self._on_load_finished)

    # ── Load finished ────────────────────────────────────────────────
    def _on_load_finished(self, ok: bool):
        if not ok:
            return

        app_data = {
            "demos": [
                {
                    "label":       d.label,
                    "module_path": d.module_path,
                    "module_name": d.module_name,
                    "class_name":  d.class_name,
                    "icon_key":    d.icon_key,
                    "description": d.description,
                    "category":    d.category,
                    "accent":      d.accent,
                    "keywords":    d.keywords,
                }
                for d in DEMOS
            ],
            "categories": CATEGORIES,
        }

        platform_info = {
            "python":   platform.python_version(),
            "platform": platform.system() + " " + platform.release(),
            "qt":       _qt_version(),
            "sdk":      "v3.052",
        }

        app_json  = json.dumps(app_data,      ensure_ascii=False)
        plat_json = json.dumps(platform_info, ensure_ascii=False)

        self._view.page().runJavaScript(
            f"window.initApp && window.initApp({app_json}, {plat_json});"
        )

    # ── Launch demo ──────────────────────────────────────────────────
    def launch(self, module_path: str):
        if self._active_window is not None:
            try:
                self._active_window.close()
            except Exception:
                pass
            self._active_window = None

        demo: Optional[DemoItem] = None
        for d in DEMOS:
            if d.module_path == module_path:
                demo = d
                break
        if demo is None:
            return

        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, demo.class_name)
            win = cls()

            if hasattr(mod, "wnd"):
                mod.wnd = win
            if hasattr(mod, "hwnd"):
                mod.hwnd = win

            win.setAttribute(Qt.WA_DeleteOnClose, True)
            win.show()

            self._active_window      = win
            self._active_module_path = module_path

            self._bridge.demo_started.emit(module_path)
            self._bridge.app_status.emit(f"Đang chạy: {demo.label}", "#F59E0B")

            self._demo_close_cb = lambda: self._on_demo_closed(module_path)
            win.destroyed.connect(self._demo_close_cb)

        except Exception as exc:
            err_msg = str(exc)
            self._bridge.demo_error.emit(module_path, err_msg)
            QMessageBox.critical(
                self, "Lỗi khởi chạy demo",
                f"Không thể mở demo:\n\n{err_msg}",
            )

    def _on_demo_closed(self, module_path: str):
        self._active_window      = None
        self._active_module_path = ""
        self._demo_close_cb      = None
        self._bridge.demo_stopped.emit(module_path)
        self._bridge.app_status.emit("Sẵn sàng", "#10B981")

    def _open_folder(self):
        folder = os.path.abspath(os.getcwd())
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", folder])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", folder])
        except Exception:
            pass

    # ── Keyboard ─────────────────────────────────────────────────────
    def keyPressEvent(self, event):
        key  = event.key()
        mods = event.modifiers()
        page = self._view.page()
        if mods == Qt.ControlModifier and key == Qt.Key_F:
            page.runJavaScript("window.focusSearch && window.focusSearch();")
        elif mods == Qt.ControlModifier and key == Qt.Key_Q:
            self.close()
        elif key == Qt.Key_Escape:
            page.runJavaScript("window.handleEsc && window.handleEsc();")
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._active_window is not None:
            try:
                self._active_window.close()
            except Exception:
                pass
        event.accept()


# ══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    launcher = Launcher()
    launcher.show()
    sys.exit(app.exec_())
