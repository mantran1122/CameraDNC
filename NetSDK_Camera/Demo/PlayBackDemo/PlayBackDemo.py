import sys
import os
import json
import shutil
import subprocess
import time
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PyQt5.QtWidgets import (
    QApplication, QFormLayout, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QSizePolicy, QSplitter, QVBoxLayout,
)
from PyQt5.QtCore import Qt, QDate, QDateTime, QSettings, QThread, pyqtSignal
from ctypes import *

from Demo.PlayBackDemo.PlayBackUI import Ui_MainWindow
from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Enum import EM_USEDEV_MODE, EM_QUERY_RECORD_TYPE, EM_LOGIN_SPAC_CAP_TYPE
from NetSDK.SDK_Struct import NET_TIME, NET_RECORDFILE_INFO, NET_IN_PLAY_BACK_BY_TIME_INFO, NET_OUT_PLAY_BACK_BY_TIME_INFO, \
    C_LLONG, C_DWORD, C_LDWORD, NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY, NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY
from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect
from connection_preferences import load_connection
from theme import THEMES


# 继承QThread

class Mythread(QThread):
    # 定义信号,定义参数为int, int类型
    breakSignal = pyqtSignal(int, int)

    def __init__(self, parent=None, dwTotalSize = 1, dwDownLoadSize = 0):
        super().__init__(parent)
        self.dwTotalSize = dwTotalSize
        self.dwDownLoadSize = dwDownLoadSize

    def run(self):
        self.breakSignal.emit(self.dwTotalSize, self.dwDownLoadSize)

    def update_data(self, total_size, download_size):
        self.breakSignal.emit(total_size, download_size)


class PlaybackHandoffWorker(QThread):
    """Convert a completed recorder download and hand it to Streamlit off the UI thread."""
    completed = pyqtSignal(str, str)

    def __init__(self, dav_path, mp4_path, manifest_path, manifest, parent=None):
        super().__init__(parent)
        self.dav_path = Path(dav_path)
        self.mp4_path = Path(mp4_path)
        self.manifest_path = Path(manifest_path)
        self.manifest = manifest

    def run(self):
        try:
            ffmpeg = os.getenv("COSMOS_FFMPEG") or shutil.which("ffmpeg")
            ffprobe = os.getenv("COSMOS_FFPROBE") or shutil.which("ffprobe")
            if not ffmpeg or not ffprobe:
                raise RuntimeError("Không tìm thấy FFmpeg/ffprobe. Cài FFmpeg hoặc cấu hình COSMOS_FFMPEG và COSMOS_FFPROBE.")
            primary = [ffmpeg, "-y", "-i", str(self.dav_path), "-map", "0:v:0", "-map", "0:a?", "-c:v", "copy", "-c:a", "aac", str(self.mp4_path)]
            result = subprocess.run(primary, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                fallback = [ffmpeg, "-y", "-i", str(self.dav_path), "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-c:a", "aac", str(self.mp4_path)]
                result = subprocess.run(fallback, capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode or not self.mp4_path.exists() or self.mp4_path.stat().st_size <= 0:
                raise RuntimeError("Chuyển DAV sang MP4 thất bại. File DAV được giữ lại để kiểm tra.")
            probe = subprocess.run([ffprobe, "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(self.mp4_path)], capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            info = json.loads(probe.stdout or "{}") if probe.returncode == 0 else {}
            duration = float((info.get("format") or {}).get("duration") or 0)
            if duration <= 0 or not any(s.get("codec_type") == "video" for s in info.get("streams", [])):
                raise RuntimeError("MP4 tạo ra không có video hợp lệ. File DAV được giữ lại để kiểm tra.")
            temporary = self.manifest_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(self.manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(str(temporary), str(self.manifest_path))
            self._open_streamlit()
            self.completed.emit("", str(self.mp4_path))
        except Exception as exc:
            retained = self.mp4_path if self.mp4_path.exists() and self.mp4_path.stat().st_size > 0 else self.dav_path
            self.completed.emit(str(exc), str(retained))

    def _open_streamlit(self):
        base_url = "http://127.0.0.1:8501"
        try:
            urlopen(base_url, timeout=1).close()
        except (URLError, OSError):
            project = Path(__file__).resolve().parents[3] / "cosmos_code_base"
            launcher = project / "run_streamlit.bat"
            if not launcher.exists():
                raise RuntimeError(f"Không tìm thấy Streamlit launcher: {launcher}")
            log_path = project / "playback_inbox" / "streamlit_startup.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("ab") as log_file:
                log_file.write(f"\n--- {datetime.now().astimezone().isoformat()} ---\n".encode("utf-8"))
                process = subprocess.Popen(
                    ["cmd.exe", "/d", "/c", str(launcher)],
                    cwd=str(project),
                    stdin=subprocess.DEVNULL,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            try:
                timeout_seconds = max(30, int(os.getenv("COSMOS_STREAMLIT_START_TIMEOUT", "180")))
            except ValueError:
                timeout_seconds = 180
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                try:
                    urlopen(base_url, timeout=1).close()
                    break
                except (URLError, OSError):
                    if process.poll() is not None:
                        try:
                            details = log_path.read_text(encoding="utf-8", errors="replace")[-2000:].strip()
                        except OSError:
                            details = ""
                        suffix = f"\n\nLog cuối:\n{details}" if details else ""
                        raise RuntimeError(f"Streamlit dừng khi khởi động (mã {process.returncode}). Xem log: {log_path}{suffix}")
                    time.sleep(1)
            else:
                raise RuntimeError(f"Streamlit chưa sẵn sàng sau {timeout_seconds} giây. Xem log: {log_path}")
        webbrowser.open(f"{base_url}/?playback_token={self.manifest['token']}")

wnd = None

@WINFUNCTYPE(None, C_LLONG, C_DWORD, C_DWORD, C_LDWORD)
def DownLoadPosCallBack(lLoginID, pchDVRIP, nDVRPort, dwUser):
    pass


@WINFUNCTYPE(c_int, C_LLONG, C_DWORD, POINTER(c_ubyte), C_DWORD, C_LDWORD)
def DownLoadDataCallBack(lPlayHandle, dwDataType, pBuffer, dwBufSize, dwUser):
    # buf_data = cast(pBuffer, POINTER(c_ubyte * dwBufSize)).contents
    # with open('./buffer.dav', 'ab+') as buf_file:
    #     buf_file.write(buf_data)
    return 1


@WINFUNCTYPE(None, C_LLONG, C_DWORD, C_DWORD, c_int, NET_RECORDFILE_INFO, C_LDWORD)
def TimeDownLoadPosCallBack(lPlayHandle, dwTotalSize, dwDownLoadSize, index, recordfileinfo, dwUser):
    try:
        target = wnd
        if target is not None:
            target.update_download_progress_thread(dwTotalSize, dwDownLoadSize)
    except Exception as e:
        print(e)


class MyMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        global wnd
        super(MyMainWindow, self).__init__(parent)
        wnd = self
        self.setupUi(self)
        self._theme = THEMES[self._saved_theme_name()]

        # 界面初始化
        self._init_ui()

        # NetSDK用到的相关变量和回调
        self.loginID = C_LLONG()
        self.playbackID = C_LLONG()
        self.downloadID = C_LLONG()
        self.m_DisConnectCallBack = fDisConnect(self.DisConnectCallBack)
        self.m_ReConnectCallBack = fHaveReConnect(self.ReConnectCallBack)

        self.thread = Mythread()
        self.thread.breakSignal.connect(self.update_download_progress)
        self.thread.start()

        # 获取NetSDK对象并初始化
        self.sdk = NetClient()
        self.sdk.InitEx(self.m_DisConnectCallBack)
        self.sdk.SetAutoReconnect(self.m_ReConnectCallBack)

        # demo内需要用到的变量
        self.pause_state = False
        self._playback_cursor = None
        self._playback_range_start = None
        self._playback_range_end = None
        self._playback_clock_started = None
        self.record_count = 0
        self.record_infos = NET_RECORDFILE_INFO * 5000
        self.download_mode = None
        self.ai_download = None
        self.handoff_worker = None

    # 初始化界面
    def _init_ui(self):
        self.Login_pushButton.setText('Đăng nhập')
        self.PlayBack_pushbutton.setText('Xem lại')
        self.PlayBack_pushbutton.setEnabled(False)

        connection = load_connection()
        self.IP_lineEdit.setText(connection['host'])
        self.Port_lineEdit.setText(connection['port'])
        self.Name_lineEdit.setText(connection['username'])
        self.Pwd_lineEdit.setText(connection['password'])

        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint)
        self.setMinimumSize(980, 640)
        self.resize(1280, 780)

        self.Login_pushButton.clicked.connect(self.login_btn_onclick)
        self.PlayBack_pushbutton.clicked.connect(self.playback_btn_onclick)
        self.Pause_pushbutton.clicked.connect(self.pause_btn_onclick)
        self.Download_pushButton.clicked.connect(self.download_btn_onclick)
        self.AnalyzeAI_pushButton.clicked.connect(self.analyze_ai_btn_onclick)
        self.SelectDate_calendarWidget.selectionChanged.connect(self.selectdate_calendar_onselectionChanged)
        self.Channel_comboBox.currentIndexChanged.connect(self.selectdate_calendar_onselectionChanged)
        self.Start_dateTimeEdit.dateChanged.connect(self._sync_selected_date)
        self.End_dateTimeEdit.dateChanged.connect(self._sync_selected_date)
        self.StreamTyp_comboBox.currentIndexChanged.connect(self.stream_comboBox_oncurrentIndexChanged)
        self._build_workspace()
        self.seek_back_button.clicked.connect(lambda: self.seek_playback(-10))
        self.seek_forward_button.clicked.connect(lambda: self.seek_playback(10))
        self.stop_playback_button.clicked.connect(self.stop_playback)

    def _build_workspace(self):
        """Replace generated absolute-position groups with a stable Playback workspace."""
        for legacy_group in (self.groupBox, self.groupBox_2, self.groupBox_3):
            legacy_group.hide()

        layout = QVBoxLayout(self.centralwidget)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(10)
        self.header_panel = QFrame(self.centralwidget)
        header = QHBoxLayout(self.header_panel)
        header.setContentsMargins(14, 8, 14, 8)
        self.header_title = QLabel('XEM LẠI TỪ ĐẦU GHI', self.header_panel)
        self.header_title.setStyleSheet('font-size: 15px; font-weight: 700;')
        self.header_status = QLabel('Ngoại tuyến', self.header_panel)
        self.header_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header.addWidget(self.header_title)
        header.addStretch(1)
        header.addWidget(self.header_status)
        layout.addWidget(self.header_panel)

        workspace = QSplitter(Qt.Horizontal, self.centralwidget)
        workspace.setChildrenCollapsible(False)

        self.connection_panel = QFrame(workspace)
        connection_layout = QVBoxLayout(self.connection_panel)
        connection_layout.setContentsMargins(14, 14, 14, 14)
        connection_layout.setSpacing(10)
        connection_title = QLabel('KẾT NỐI ĐẦU GHI', self.connection_panel)
        connection_title.setStyleSheet('font-weight: 700;')
        connection_layout.addWidget(connection_title)
        connection_form = QFormLayout()
        connection_form.setSpacing(8)
        connection_form.addRow(self.label, self.IP_lineEdit)
        connection_form.addRow(self.label_2, self.Port_lineEdit)
        connection_form.addRow(self.label_3, self.Name_lineEdit)
        connection_form.addRow(self.label_4, self.Pwd_lineEdit)
        connection_layout.addLayout(connection_form)
        connection_layout.addWidget(self.Login_pushButton)
        connection_layout.addStretch(1)

        self.video_panel = QFrame(workspace)
        video_layout = QVBoxLayout(self.video_panel)
        video_layout.setContentsMargins(10, 10, 10, 10)
        self.PlayBackWnd.setMinimumSize(480, 300)
        self.PlayBackWnd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.PlayBackWnd.setAlignment(Qt.AlignCenter)
        video_layout.addWidget(self.PlayBackWnd, 1)
        self.video_caption = QLabel('Chọn thời gian và nhấn Phát để xem lại', self.video_panel)
        video_layout.addWidget(self.video_caption)

        self.controls_panel = QFrame(workspace)
        controls_layout = QVBoxLayout(self.controls_panel)
        controls_layout.setContentsMargins(14, 14, 14, 14)
        controls_layout.setSpacing(9)
        controls_title = QLabel('ĐIỀU KHIỂN XEM LẠI', self.controls_panel)
        controls_title.setStyleSheet('font-weight: 700;')
        controls_layout.addWidget(controls_title)
        view_form = QFormLayout()
        view_form.setSpacing(8)
        view_form.addRow(self.Channel_label, self.Channel_comboBox)
        view_form.addRow(self.label_5, self.StreamTyp_comboBox)
        controls_layout.addLayout(view_form)
        controls_layout.addWidget(self.SelectDate_calendarWidget)
        controls_layout.addWidget(self.exist_radioButton)
        time_form = QFormLayout()
        time_form.setSpacing(8)
        time_form.addRow(self.label_7, self.Start_dateTimeEdit)
        time_form.addRow(self.label_8, self.End_dateTimeEdit)
        controls_layout.addLayout(time_form)
        buttons = QHBoxLayout()
        self.seek_back_button = QPushButton('‹ 10 giây', self.controls_panel)
        self.seek_forward_button = QPushButton('10 giây ›', self.controls_panel)
        self.stop_playback_button = QPushButton('Dừng', self.controls_panel)
        self.seek_back_button.setToolTip('Tua lùi 10 giây')
        self.seek_forward_button.setToolTip('Tua tới 10 giây')
        self.seek_back_button.setEnabled(False)
        self.seek_forward_button.setEnabled(False)
        self.stop_playback_button.setEnabled(False)
        buttons.addWidget(self.seek_back_button)
        buttons.addWidget(self.PlayBack_pushbutton)
        buttons.addWidget(self.Pause_pushbutton)
        buttons.addWidget(self.seek_forward_button)
        controls_layout.addLayout(buttons)
        controls_layout.addWidget(self.stop_playback_button)
        controls_layout.addWidget(self.Download_pushButton)
        controls_layout.addWidget(self.AnalyzeAI_pushButton)
        controls_layout.addWidget(self.Download_progressBar)
        controls_layout.addStretch(1)

        workspace.addWidget(self.connection_panel)
        workspace.addWidget(self.video_panel)
        workspace.addWidget(self.controls_panel)
        workspace.setStretchFactor(0, 0)
        workspace.setStretchFactor(1, 1)
        workspace.setStretchFactor(2, 0)
        workspace.setSizes([250, 700, 310])
        layout.addWidget(workspace, 1)
        self._apply_theme_styles()

    @staticmethod
    def _saved_theme_name():
        value = str(QSettings('DNC', 'DahuaControlCenter').value('appearance/theme', 'dark')).lower()
        return value if value in THEMES else 'dark'

    def _apply_theme_styles(self):
        t = self._theme
        self.centralwidget.setStyleSheet('background: {}; color: {};'.format(t.BG, t.P1))
        panel_style = (
            'QFrame {{ background: {}; border: 1px solid {}; border-radius: {}px; }} '
            'QLabel {{ color: {}; background: transparent; border: none; font-weight: 600; }} '
            'QLineEdit, QComboBox, QDateTimeEdit, QCalendarWidget {{ background: {}; color: {}; border: 1px solid {}; border-radius: {}px; padding: 6px; }} '
            'QPushButton {{ background: {}; color: {}; border: none; border-radius: {}px; padding: 8px 12px; font-weight: 700; min-height: 22px; }} '
            'QPushButton:disabled {{ background: {}; color: {}; }} '
            'QRadioButton {{ color: {}; background: transparent; }} '
            'QProgressBar {{ border: none; text-align: center; color: {}; }} '
            'QProgressBar::chunk {{ background: {}; }}'
        ).format(t.S2, t.BD, t.RADIUS_CARD, t.P2, t.S1, t.P1, t.BD2, t.RADIUS_INPUT,
                 t.ACCENT, t.P1, t.RADIUS_BTN, t.S3, t.P3, t.P2, t.P1, t.ACCENT)
        self.connection_panel.setStyleSheet(panel_style)
        self.controls_panel.setStyleSheet(panel_style)
        calendar_style = (
            'QCalendarWidget {{ background: {s2}; color: {p1}; border: none; }} '
            'QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {s1}; border: none; }} '
            'QCalendarWidget QToolButton {{ color: {p1}; background: {s1}; border: none; padding: 5px; font-weight: 700; }} '
            'QCalendarWidget QToolButton:hover {{ background: {s3}; }} '
            'QCalendarWidget QMenu {{ background: {s2}; color: {p1}; }} '
            'QCalendarWidget QSpinBox {{ background: {s2}; color: {p1}; border: none; }} '
            'QCalendarWidget QAbstractItemView {{ background: {s2}; color: {p1}; selection-background-color: {accent}; selection-color: {p1}; outline: 0; }} '
            'QCalendarWidget QAbstractItemView:disabled {{ color: {p3}; }}'
        ).format(s1=t.S1, s2=t.S2, s3=t.S3, p1=t.P1, p3=t.P3, accent=t.ACCENT)
        self.SelectDate_calendarWidget.setStyleSheet(calendar_style)
        self.video_panel.setStyleSheet('background: {}; border: 1px solid {}; border-radius: {}px;'.format(t.S1, t.BD, t.RADIUS_CARD))
        self.header_panel.setStyleSheet('background: {}; border: none; color: {}; QLabel {{ background: transparent; border: none; }}'.format(t.TOPBAR, t.P1))


    def configure_replay(self, host, port, username, password, channel, start_time, end_time):
        """Open an independent recorder Playback window for a live AI event."""
        start = QDateTime.fromString(str(start_time), Qt.ISODate)
        end = QDateTime.fromString(str(end_time), Qt.ISODate)
        if not start.isValid() or not end.isValid() or start >= end:
            raise ValueError('Khoảng thời gian xem lại không hợp lệ.')
        self.IP_lineEdit.setText(str(host))
        self.Port_lineEdit.setText(str(port))
        self.Name_lineEdit.setText(str(username))
        self.Pwd_lineEdit.setText(str(password))
        self._pending_replay = (int(channel), start, end)
        self.login_btn_onclick()

    def _start_pending_replay(self):
        request = getattr(self, '_pending_replay', None)
        self._pending_replay = None
        if request is None:
            return
        channel, start, end = request
        if channel < 0 or channel >= self.Channel_comboBox.count():
            QMessageBox.warning(self, 'Xem lại', 'Kênh camera của sự kiện không tồn tại trên đầu ghi.')
            return
        self.Channel_comboBox.setCurrentIndex(channel)
        self.SelectDate_calendarWidget.setSelectedDate(start.date())
        self.Start_dateTimeEdit.setDateTime(start)
        self.End_dateTimeEdit.setDateTime(end)
        self.playback_btn_onclick()

    def login_btn_onclick(self):
        if not self.loginID:
            ip = self.IP_lineEdit.text()
            port = int(self.Port_lineEdit.text())
            username = self.Name_lineEdit.text()
            password = self.Pwd_lineEdit.text()
            stuInParam = NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY()
            stuInParam.dwSize = sizeof(NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY)
            stuInParam.szIP = ip.encode()
            stuInParam.nPort = port
            stuInParam.szUserName = username.encode()
            stuInParam.szPassword = password.encode()
            stuInParam.emSpecCap = EM_LOGIN_SPAC_CAP_TYPE.TCP
            stuInParam.pCapParam = None

            stuOutParam = NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY()
            stuOutParam.dwSize = sizeof(NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY)

            self.loginID, device_info, error_msg = self.sdk.LoginWithHighLevelSecurity(stuInParam, stuOutParam)
            if self.loginID != 0:
                self.setWindowTitle('Xem lại video - Trực tuyến')
                self.header_status.setText('TRỰC TUYẾN')
                self.Login_pushButton.setText('Đăng xuất')
                self.Download_pushButton.setEnabled(True)
                self.Channel_comboBox.setEnabled(True)
                self.StreamTyp_comboBox.setEnabled(True)
                self.SelectDate_calendarWidget.setEnabled(True)
                self.SelectDate_calendarWidget.setSelectedDate(QDate.currentDate())
                self.set_stream_type(0)
                for i in range(int(device_info.nChanNum)):
                    self.Channel_comboBox.addItem(str(i))
                self.selectdate_calendar_onselectionChanged()
                self._start_pending_replay()
            else:
                QMessageBox.about(self, 'Thông báo', error_msg)
        else:
            if self.playbackID:
                self.sdk.StopPlayBack(self.playbackID)
                self.playbackID = 0
            if self.downloadID:
                self.sdk.StopDownload(self.downloadID)
                self.downloadID = 0
            self.download_mode = None
            result = self.sdk.Logout(self.loginID)
            if result:
                self.setWindowTitle("Xem lại video - Ngoại tuyến")
                self.header_status.setText('NGOẠI TUYẾN')
                self.Login_pushButton.setText("Đăng nhập")
                self.loginID = 0
                self.StreamTyp_comboBox.setEnabled(False)
                self.PlayBack_pushbutton.setEnabled(False)
                self.Pause_pushbutton.setEnabled(False)
                self.seek_back_button.setEnabled(False)
                self.seek_forward_button.setEnabled(False)
                self.stop_playback_button.setEnabled(False)
                self.Download_pushButton.setEnabled(False)
                self.Channel_comboBox.setEnabled(False)
                self.StreamTyp_comboBox.setEnabled(False)
                self.SelectDate_calendarWidget.setEnabled(False)
                self.exist_radioButton.setChecked(False)
                self.PlayBack_pushbutton.setText("Xem lại")
                self.Pause_pushbutton.setText("Tạm dừng")
                self.pause_state = False
                self._playback_cursor = None
                self._playback_range_start = None
                self._playback_range_end = None
                self._playback_clock_started = None
                self.Download_pushButton.setText("Tải xuống")
                self.AnalyzeAI_pushButton.setEnabled(False)
                self.PlayBackWnd.repaint()
                self.Channel_comboBox.clear()
                self.Download_progressBar.setValue(0)
                self.thread.update_data(1, 0)

    def stream_comboBox_oncurrentIndexChanged(self):
        stream_type = self.StreamTyp_comboBox.currentIndex()
        self.set_stream_type(stream_type)

    def selectdate_calendar_onselectionChanged(self):
        if not self.loginID:
            return
        if self.playbackID:
            return
        self.exist_radioButton.setChecked(False)
        self.PlayBack_pushbutton.setEnabled(False)
        self.AnalyzeAI_pushButton.setEnabled(False)
        self.record_count = 0
        date = QDate(self.SelectDate_calendarWidget.selectedDate())
        startTime = NET_TIME()
        startTime.dwYear = date.year()
        startTime.dwMonth = date.month()
        startTime.dwDay = date.day()
        startTime.dwHour = 0
        startTime.dwMinute = 0
        startTime.dwSecond = 0

        endTime = NET_TIME()
        endTime.dwYear = date.year()
        endTime.dwMonth = date.month()
        endTime.dwDay = date.day()
        endTime.dwHour = 23
        endTime.dwMinute = 59
        endTime.dwSecond = 59

        result, fileCount, self.record_infos = self.query_file(startTime, endTime)
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
            return 0
        if fileCount > 0:
            self.record_count = fileCount
            self.exist_radioButton.setChecked(True)
            self.PlayBack_pushbutton.setEnabled(True)
            self._sync_selected_date()
            self._refresh_ai_button()

    def playback_btn_onclick(self):
        if not self.playbackID:
            start, end = self.Start_dateTimeEdit.dateTime(), self.End_dateTimeEdit.dateTime()
            if start >= end:
                QMessageBox.warning(self, "Xem lại", "Thời gian bắt đầu phải nhỏ hơn thời gian kết thúc.")
                return
            start_time = self._net_time_from_editor(self.Start_dateTimeEdit)
            end_time = self._net_time_from_editor(self.End_dateTimeEdit)
            result, file_count, _ = self.query_file(start_time, end_time)
            if not result or file_count <= 0:
                QMessageBox.warning(self, "Xem lại", "Không có bản ghi trong khoảng thời gian đã chọn.")
                return

            inParam = NET_IN_PLAY_BACK_BY_TIME_INFO()
            # PyQt5/SIP may expose winId() as sip.voidptr; ctypes needs a plain integer.
            inParam.hWnd = int(self.PlayBackWnd.winId())
            inParam.cbDownLoadPos = DownLoadPosCallBack
            inParam.dwPosUser = 0
            inParam.fDownLoadDataCallBack = DownLoadDataCallBack
            inParam.dwDataUser = 0
            inParam.nPlayDirection = 0
            inParam.nWaittime = 5000
            inParam.stStartTime.dwYear = start_time.dwYear
            inParam.stStartTime.dwMonth = start_time.dwMonth
            inParam.stStartTime.dwDay = start_time.dwDay
            inParam.stStartTime.dwHour = start_time.dwHour
            inParam.stStartTime.dwMinute = start_time.dwMinute
            inParam.stStartTime.dwSecond = start_time.dwSecond
            inParam.stStopTime.dwYear = end_time.dwYear
            inParam.stStopTime.dwMonth = end_time.dwMonth
            inParam.stStopTime.dwDay = end_time.dwDay
            inParam.stStopTime.dwHour = end_time.dwHour
            inParam.stStopTime.dwMinute = end_time.dwMinute
            inParam.stStopTime.dwSecond = end_time.dwSecond
            outParam = NET_OUT_PLAY_BACK_BY_TIME_INFO()

            nchannel = self.Channel_comboBox.currentIndex()
            self.playbackID = self.sdk.PlayBackByTimeEx2(self.loginID, nchannel, inParam, outParam)
            if self.playbackID != 0:
                if self._playback_range_start is None:
                    self._playback_range_start = start
                    self._playback_range_end = end
                self._playback_cursor = start
                self._playback_clock_started = time.monotonic()
                self.pause_state = False
                self.PlayBack_pushbutton.setText("Đang phát")
                self.PlayBack_pushbutton.setEnabled(False)
                self.Pause_pushbutton.setEnabled(True)
                self.seek_back_button.setEnabled(True)
                self.seek_forward_button.setEnabled(True)
                self.stop_playback_button.setEnabled(True)
                self.Channel_comboBox.setEnabled(False)
                self.StreamTyp_comboBox.setEnabled(False)
                self.SelectDate_calendarWidget.setEnabled(False)
                self.video_caption.setText("Đang xem lại — dùng ‹ / › để tua 10 giây")
                self.Channel_comboBox.repaint()
                self.StreamTyp_comboBox.repaint()
                self.PlayBackWnd.repaint()
            else:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
        else:
            self.stop_playback()

    def _current_playback_time(self):
        """Estimate the current recorder position between native seek requests."""
        cursor = self._playback_cursor or self.Start_dateTimeEdit.dateTime()
        if self._playback_clock_started is not None:
            cursor = cursor.addMSecs(int((time.monotonic() - self._playback_clock_started) * 1000))
        if self._playback_range_end is not None and cursor > self._playback_range_end:
            return self._playback_range_end
        return cursor

    def _reset_playback_ui(self):
        self.PlayBack_pushbutton.setText("Xem lại")
        self.PlayBack_pushbutton.setEnabled(bool(self.loginID and self.record_count > 0))
        self.PlayBackWnd.repaint()
        self.Pause_pushbutton.setText("Tạm dừng")
        self.Pause_pushbutton.setEnabled(False)
        self.seek_back_button.setEnabled(False)
        self.seek_forward_button.setEnabled(False)
        self.stop_playback_button.setEnabled(False)
        self.Channel_comboBox.setEnabled(True)
        self.StreamTyp_comboBox.setEnabled(True)
        self.SelectDate_calendarWidget.setEnabled(True)
        self.video_caption.setText("Chọn thời gian và nhấn Xem lại để phát video")

    def stop_playback(self):
        """Stop playback completely and return the recorder controls to idle."""
        if not self.playbackID:
            return
        result = self.sdk.StopPlayBack(self.playbackID)
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
            return
        self.playbackID = 0
        self.pause_state = False
        self._playback_cursor = None
        self._playback_range_start = None
        self._playback_range_end = None
        self._playback_clock_started = None
        self._reset_playback_ui()

    def seek_playback(self, seconds):
        """Restart recorder playback at a qualitative +/- 10-second position."""
        if not self.playbackID or self._playback_range_start is None or self._playback_range_end is None:
            return
        current = self._current_playback_time()
        target = current.addSecs(seconds)
        if target < self._playback_range_start:
            target = self._playback_range_start
        elif target > self._playback_range_end:
            target = self._playback_range_end
        if target == current:
            return
        if not self.sdk.StopPlayBack(self.playbackID):
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
            return
        self.playbackID = 0
        self.pause_state = False
        self._playback_cursor = target
        self._playback_clock_started = None
        self.Start_dateTimeEdit.blockSignals(True)
        self.Start_dateTimeEdit.setDateTime(target)
        self.Start_dateTimeEdit.blockSignals(False)
        self.playback_btn_onclick()

    def pause_btn_onclick(self):
        if self.playbackID:
            next_pause_state = not self.pause_state
            result = self.sdk.PausePlayBack(self.playbackID, next_pause_state)
            if not result:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
                return
            if next_pause_state:
                self._playback_cursor = self._current_playback_time()
                self._playback_clock_started = None
            else:
                self._playback_clock_started = time.monotonic()
            self.pause_state = next_pause_state
            if self.pause_state:
                self.Pause_pushbutton.setText("Tiếp tục")
            else:
                self.Pause_pushbutton.setText("Tạm dừng")
        else:
            pass

    def download_btn_onclick(self):
        if not self.downloadID:
            application_window = tk.Tk()
            application_window.withdraw()

            # 设置文件对话框会显示的文件类型
            save_filetypes = [('data', '.dav')]

            # 请求选择一个用以保存的文件
            save_file_name = filedialog.asksaveasfilename(parent=application_window,
                                                          initialdir=os.getcwd(),
                                                          title="Please select a file name for saving:",
                                                          filetypes=save_filetypes)
            if save_file_name == "":
                return

            stream_type = self.StreamTyp_comboBox.currentIndex()
            self.set_stream_type(stream_type)

            start_date = self.Start_dateTimeEdit.date()
            start_time = self.Start_dateTimeEdit.time()
            startDateTime = NET_TIME()
            startDateTime.dwYear = start_date.year()
            startDateTime.dwMonth = start_date.month()
            startDateTime.dwDay = start_date.day()
            startDateTime.dwHour = start_time.hour()
            startDateTime.dwMinute = start_time.minute()
            startDateTime.dwSecond = start_time.second()

            end_date = self.End_dateTimeEdit.date()
            end_time = self.End_dateTimeEdit.time()
            enddateTime = NET_TIME()
            enddateTime.dwYear = end_date.year()
            enddateTime.dwMonth = end_date.month()
            enddateTime.dwDay = end_date.day()
            enddateTime.dwHour = end_time.hour()
            enddateTime.dwMinute = end_time.minute()
            enddateTime.dwSecond = end_time.second()

            nchannel = self.Channel_comboBox.currentIndex()
            self.downloadID = self.sdk.DownloadByTimeEx(self.loginID, nchannel, int(EM_QUERY_RECORD_TYPE.ALL),
                                                        startDateTime, enddateTime, save_file_name,
                                                        TimeDownLoadPosCallBack, 0,
                                                        DownLoadDataCallBack, 0)
            if self.downloadID:
                self.Download_pushButton.setText("Dừng tải")
            else:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
        else:
            result = self.sdk.StopDownload(self.downloadID)
            if result:
                self.downloadID = 0
                self.Download_pushButton.setText("Tải xuống")
                self.Download_progressBar.setValue(0)
                self.thread.update_data(1, 0)
            else:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())

    def _sync_selected_date(self):
        """Keep download controls on the calendar date, preserving their selected times."""
        date = self.SelectDate_calendarWidget.selectedDate()
        self.Start_dateTimeEdit.setDate(date)
        self.End_dateTimeEdit.setDate(date)
        self._refresh_ai_button()

    def _refresh_ai_button(self):
        valid = bool(self.loginID and self.record_count > 0 and self.Channel_comboBox.currentIndex() >= 0)
        valid = valid and self.Start_dateTimeEdit.dateTime() < self.End_dateTimeEdit.dateTime()
        self.AnalyzeAI_pushButton.setEnabled(valid and not self.downloadID and self.handoff_worker is None)

    def _net_time_from_editor(self, editor):
        date, clock = editor.date(), editor.time()
        value = NET_TIME()
        value.dwYear, value.dwMonth, value.dwDay = date.year(), date.month(), date.day()
        value.dwHour, value.dwMinute, value.dwSecond = clock.hour(), clock.minute(), clock.second()
        return value

    def analyze_ai_btn_onclick(self):
        if self.downloadID:
            QMessageBox.warning(self, "Phân tích AI", "Một tác vụ tải xuống đang chạy.")
            return
        start, end = self.Start_dateTimeEdit.dateTime(), self.End_dateTimeEdit.dateTime()
        max_minutes = int(os.getenv("COSMOS_PLAYBACK_MAX_MINUTES", "30"))
        if start >= end or start.secsTo(end) > max_minutes * 60:
            QMessageBox.warning(self, "Phân tích AI", f"Khoảng thời gian phải lớn hơn 0 và không quá {max_minutes} phút.")
            return
        start_time, end_time = self._net_time_from_editor(self.Start_dateTimeEdit), self._net_time_from_editor(self.End_dateTimeEdit)
        result, count, _ = self.query_file(start_time, end_time)
        if not result or count <= 0:
            QMessageBox.warning(self, "Phân tích AI", "Không có bản ghi trong khoảng thời gian đã chọn.")
            return
        inbox = Path(__file__).resolve().parents[3] / "cosmos_code_base" / "playback_inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        token, channel = uuid.uuid4().hex, self.Channel_comboBox.currentIndex()
        stamp = start.toString("yyyyMMdd_HHmmss") + "_" + end.toString("HHmmss")
        dav_path = inbox / f"playback_ch{channel}_{stamp}_{token}.dav"
        self.ai_download = {"dav_path": dav_path, "mp4_path": dav_path.with_suffix(".mp4"), "token": token, "channel": channel, "start": start, "end": end}
        self.downloadID = self.sdk.DownloadByTimeEx(self.loginID, channel, int(EM_QUERY_RECORD_TYPE.ALL), start_time, end_time, str(dav_path), TimeDownLoadPosCallBack, 0, DownLoadDataCallBack, 0)
        if not self.downloadID:
            self.ai_download = None
            QMessageBox.warning(self, "Phân tích AI", self.sdk.GetLastErrorMessage())
            return
        self.download_mode = "ai"
        self.AnalyzeAI_pushButton.setEnabled(False)
        self.Download_pushButton.setEnabled(False)
        self.statusbar.showMessage("Đang tải đoạn video để phân tích AI...")

    def _start_handoff(self, request):
        if not request["dav_path"].exists() or request["dav_path"].stat().st_size <= 0:
            self._handoff_finished("File DAV tải về rỗng hoặc không tồn tại.", str(request["dav_path"]))
            return
        manifest = {"token": request["token"], "source": "dahua_playback", "video_path": str(request["mp4_path"].resolve()), "channel": request["channel"], "start_time": request["start"].toString(Qt.ISODate), "end_time": request["end"].toString(Qt.ISODate), "auto_analyze": True, "created_at": datetime.now().astimezone().isoformat()}
        manifest_path = request["mp4_path"].parent / "playback_handoff.json"
        self.handoff_worker = PlaybackHandoffWorker(request["dav_path"], request["mp4_path"], manifest_path, manifest, self)
        self.handoff_worker.completed.connect(self._handoff_finished)
        self.handoff_worker.start()
        self.statusbar.showMessage("Đang chuyển DAV sang MP4 và mở Streamlit...")

    def _handoff_finished(self, error, path):
        self.handoff_worker, self.ai_download = None, None
        self.Download_pushButton.setEnabled(bool(self.loginID))
        self._refresh_ai_button()
        if error:
            QMessageBox.warning(self, "Phân tích AI", f"{error}\nFile giữ lại: {path}")
        else:
            self.statusbar.showMessage("Đã mở Streamlit để phân tích video.")

    def set_stream_type(self, stream_type):
        # set stream type;设置码流类型
        stream_type = c_int(stream_type)
        result = self.sdk.SetDeviceMode(self.loginID, int(EM_USEDEV_MODE.RECORD_STREAM_TYPE), stream_type)
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
            return 0, 0, None

    def query_file(self, startTime, endTime):
        # query record file 查询录像文件
        result, fileCount, infos = self.sdk.QueryRecordFile(self.loginID, self.Channel_comboBox.currentIndex(), int(EM_QUERY_RECORD_TYPE.ALL), startTime,
                                                            endTime, None, 5000, False)
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
            return 0, 0, None
        return result, fileCount, infos

    def update_download_progress_thread(self, totalsize, downloadsize):
        try:
            self.thread.update_data(totalsize, downloadsize)
        except Exception as e:
            print(e)

    def update_download_progress(self, total_size, download_size):
        try:
            # C_DWORD is unsigned: NetSDK's -1/-2 sentinels can arrive as
            # 0xFFFFFFFF/0xFFFFFFFE depending on the ctypes/platform build.
            if download_size in (-1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
                completed_mode = self.download_mode
                request = self.ai_download
                handle = self.downloadID
                if handle:
                    self.sdk.StopDownload(handle)
                self.downloadID = 0
                self.Download_progressBar.setValue(0)
                self.download_mode = None
                if completed_mode == "ai" and request:
                    self._start_handoff(request)
                    return
                self.Download_pushButton.setText("Tải xuống")
                QMessageBox.about(self, 'Thông báo', "Tải xuống hoàn tất!")
            elif download_size in (-2, 0xFFFFFFFE, 0xFFFFFFFFFFFFFFFE):
                self.downloadID = 0
                self.download_mode = None
                self.ai_download = None
                self.Download_pushButton.setEnabled(bool(self.loginID))
                self._refresh_ai_button()
                self.Download_progressBar.setValue(0)
                self.Download_pushButton.setText("Tải xuống")
                QMessageBox.about(self, 'Thông báo', "Tải xuống thất bại!")
            else:
                if total_size <= 0:
                    self.Download_progressBar.setValue(0)
                elif download_size >= total_size:
                    self.Download_progressBar.setValue(100)
                else:
                    percentage = int(download_size * 100 / total_size)
                    self.Download_progressBar.setValue(percentage)
        except Exception as e:
            print(e)

    # 实现断线回调函数功能
    def DisConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle("Xem lại video - Ngoại tuyến")
        self.header_status.setText('MẤT KẾT NỐI')

    # 实现断线重连回调函数功能
    def ReConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle('Xem lại video - Trực tuyến')
        self.header_status.setText('TRỰC TUYẾN')

    # 关闭主窗口时清理资源
    def closeEvent(self, event):
        event.accept()
        if self.playbackID:
            self.sdk.StopPlayBack(self.playbackID)
            self.playbackID = 0
        if self.downloadID:
            self.sdk.StopDownload(self.downloadID)
            self.downloadID = 0
        if self.loginID:
            self.sdk.Logout(self.loginID)
        self.sdk.Cleanup()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    my_wnd = MyMainWindow()
    wnd = my_wnd
    my_wnd.show()
    sys.exit(app.exec_())
