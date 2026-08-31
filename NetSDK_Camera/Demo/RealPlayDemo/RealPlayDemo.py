# coding=utf-8
"""Dahua connection and live-preview MVP."""
import os
import sys
import json
import shutil
import hashlib
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
from urllib.parse import quote, urlparse
from ctypes import POINTER, c_ubyte, cast, sizeof

# Preload torch on Windows before PyQt5 loads C++ runtime/DLLs to prevent WinError 1114 in c10.dll
try:
    import torch
except Exception:
    pass

from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPlainTextEdit, QSizePolicy, QSplitter, QVBoxLayout,
    QPushButton, QStyle, QToolButton,
)

from Demo.RealPlayDemo.RealPlayUI import Ui_MainWindow
from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect, fSnapRev
from NetSDK.SDK_Enum import SDK_RealPlayType, EM_LOGIN_SPAC_CAP_TYPE
from NetSDK.SDK_Struct import C_LLONG, SNAP_PARAMS, NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY, NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY
from connection_preferences import clear_connection, load_connection, save_connection
from theme import THEMES


def _positive_float_from_env(name, default):
    try:
        return max(float(os.getenv(name, str(default))), 1.0)
    except ValueError:
        return float(default)


class MyMainWindow(QMainWindow, Ui_MainWindow):
    """Connect to one Dahua recorder and render a selected channel."""

    connection_changed = pyqtSignal(bool)
    cosmos_result = pyqtSignal(dict)
    cosmos_status = pyqtSignal(str)
    audio_result = pyqtSignal(dict)
    audio_status = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._theme = THEMES[self._saved_theme_name()]
        self.loginID = C_LLONG()
        self.playID = C_LLONG()
        self.m_DisConnectCallBack = fDisConnect(self.DisConnectCallBack)
        self.m_ReConnectCallBack = fHaveReConnect(self.ReConnectCallBack)
        self.m_SnapCallBack = fSnapRev(self.SnapshotCallBack)
        self.sdk = NetClient()
        self.sdk.InitEx(self.m_DisConnectCallBack)
        self.sdk.SetAutoReconnect(self.m_ReConnectCallBack)
        self.sdk.SetSnapRevCallBack(self.m_SnapCallBack, 0)
        self.connection_changed.connect(self._set_connection_state)
        self.cosmos_result.connect(self._show_cosmos_result)
        self.cosmos_status.connect(self._show_cosmos_status)
        self.audio_result.connect(self._show_audio_result)
        self.audio_status.connect(self._show_audio_status)
        self._snapshot_pending = False
        self._inference_inflight = False
        self._ai_enabled = False
        self._audio_enabled = False
        self._audio_inflight = False
        self._audio_cancel = None
        self._audio_thread = None
        self._sound_enabled = False
        self._snap_serial = 0
        self._capture_times = {}
        self._last_replay = None
        self._replay_events = []
        self._replay_windows = []
        self._local_audio_pipeline = None
        self._live_transcripts = []
        self.cosmos_url = os.getenv('COSMOS_LIVE_URL', 'http://127.0.0.1:8765/analyze')
        self.cosmos_interval_seconds = _positive_float_from_env('COSMOS_SAMPLE_INTERVAL_SECONDS', 10)
        self.audio_interval_seconds = _positive_float_from_env('COSMOS_AUDIO_INTERVAL_SECONDS', 8)
        self.audio_chunk_seconds = _positive_float_from_env('COSMOS_AUDIO_CHUNK_SECONDS', 8)
        self.audio_connect_timeout_seconds = _positive_float_from_env('COSMOS_AUDIO_CONNECT_TIMEOUT_SECONDS', 8)
        self.cosmos_stop_on_exit = os.getenv('COSMOS_STOP_ON_LIVE_CLOSE', '').strip().lower() in {'1', 'true', 'yes'}
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle('Xem camera trực tiếp')
        self.setMinimumSize(980, 640)
        self.resize(1280, 780)
        self.login_btn.setText('Đăng nhập')
        self.play_btn.setText('Bắt đầu xem')
        self.play_btn.setEnabled(False)
        connection = load_connection()
        self.IP_lineEdit.setText(connection['host'])
        self.Port_lineEdit.setText(connection['port'])
        self.Name_lineEdit.setText(connection['username'])
        self.Pwd_lineEdit.setText(connection['password'])
        self.Port_lineEdit.setValidator(QIntValidator(1, 65535, self))
        self.remember_check = QCheckBox('Lưu thông tin đăng nhập trên máy này', self.centralwidget)
        self.remember_check.setChecked(connection['remember'])
        self.remember_check.toggled.connect(self._on_remember_toggled)
        self.ai_check = QCheckBox('Phân tích Cosmos (mỗi {} giây)'.format(int(self.cosmos_interval_seconds)), self.centralwidget)
        self.ai_check.setEnabled(False)
        self.ai_check.toggled.connect(self._on_ai_toggled)
        self.audio_check = QCheckBox('Chuyển tiếng nói thành văn bản (mỗi {} giây)'.format(int(self.audio_interval_seconds)), self.centralwidget)
        self.audio_check.setEnabled(False)
        self.audio_check.toggled.connect(self._on_audio_toggled)
        self.replay_event_combo = QComboBox(self.centralwidget)
        self.replay_event_combo.setEnabled(False)
        self.replay_event_combo.setToolTip('Chọn một cảnh báo AI để xem lại đoạn ghi trên đầu ghi.')
        self.replay_btn = QPushButton('Xem lại cảnh báo đã chọn', self.centralwidget)
        self.replay_btn.setEnabled(False)
        self.replay_btn.clicked.connect(self._open_last_replay)
        self.cosmos_label = QLabel('Cosmos: đã tắt', self.centralwidget)
        self.cosmos_label.setWordWrap(True)
        self.cosmos_log = QPlainTextEdit(self.centralwidget)
        self.cosmos_log.setReadOnly(True)
        self.cosmos_log.setMaximumBlockCount(80)
        self.cosmos_log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.audio_label = QLabel('Tiếng nói: đã tắt', self.centralwidget)
        self.audio_label.setWordWrap(True)
        self.audio_log = QPlainTextEdit(self.centralwidget)
        self.audio_log.setReadOnly(True)
        self.audio_log.setMaximumBlockCount(80)
        self.audio_log.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.audio_copy_btn = QPushButton('Sao chép', self.centralwidget)
        self.audio_copy_btn.setToolTip('Sao chép toàn bộ nhật ký tiếng nói vào Clipboard')
        self.audio_copy_btn.clicked.connect(self._copy_audio_log)
        self.audio_save_btn = QPushButton('Lưu .txt', self.centralwidget)
        self.audio_save_btn.setToolTip('Lưu nhật ký phân tích tiếng nói ra file')
        self.audio_save_btn.clicked.connect(self._save_audio_log)
        self.audio_clear_btn = QPushButton('Xóa', self.centralwidget)
        self.audio_clear_btn.setToolTip('Xóa nội dung nhật ký tiếng nói đang hiển thị')
        self.audio_clear_btn.clicked.connect(self._clear_audio_log)
        self._build_responsive_layout()
        self.statusbar.showMessage('Chưa kết nối đầu ghi')
        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint)
        self.login_btn.clicked.connect(self.login_btn_onclick)
        self.play_btn.clicked.connect(self.play_btn_onclick)
        self.sample_timer = QTimer(self)
        self.sample_timer.setInterval(int(self.cosmos_interval_seconds * 1000))
        self.sample_timer.timeout.connect(self._request_snapshot)
        self.audio_timer = QTimer(self)
        self.audio_timer.setInterval(int(self.audio_interval_seconds * 1000))
        self.audio_timer.timeout.connect(self._request_audio)

    def _build_responsive_layout(self):
        """Build an operations-first camera workspace without absolute positioning."""
        layout = QVBoxLayout(self.centralwidget)
        layout.setContentsMargins(12, 12, 12, 10)
        layout.setSpacing(10)

        self.header_panel = QFrame(self.centralwidget)
        header = QHBoxLayout(self.header_panel)
        header.setContentsMargins(14, 8, 14, 8)
        self.header_title = QLabel('GIÁM SÁT TRỰC TIẾP', self.header_panel)
        self.header_title.setStyleSheet('font-size: 15px; font-weight: 700;')
        self.header_status = QLabel('Chưa kết nối đầu ghi', self.header_panel)
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
        connection_form.setLabelAlignment(Qt.AlignLeft)
        connection_form.setSpacing(8)
        connection_form.addRow(self.IP_label, self.IP_lineEdit)
        connection_form.addRow(self.Port_label, self.Port_lineEdit)
        connection_form.addRow(self.Name_label, self.Name_lineEdit)
        connection_form.addRow(self.Pwd_label, self.Pwd_lineEdit)
        connection_layout.addLayout(connection_form)
        connection_layout.addWidget(self.remember_check)
        connection_layout.addWidget(self.login_btn)

        device_title = QLabel('CAMERA ĐANG XEM', self.connection_panel)
        device_title.setStyleSheet('font-weight: 700; margin-top: 10px;')
        connection_layout.addWidget(device_title)
        device_form = QFormLayout()
        device_form.setSpacing(8)
        device_form.addRow(self.Channel_label, self.Channel_comboBox)
        device_form.addRow(self.label_5, self.StreamTyp_comboBox)
        connection_layout.addLayout(device_form)
        connection_layout.addWidget(self.play_btn)
        connection_layout.addStretch(1)

        self.video_panel = QFrame(workspace)
        video_layout = QVBoxLayout(self.video_panel)
        video_layout.setContentsMargins(10, 10, 10, 10)
        video_layout.setSpacing(8)
        self.PlayWnd.setMinimumSize(480, 300)
        self.PlayWnd.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.PlayWnd.setAlignment(Qt.AlignCenter)
        video_layout.addWidget(self.PlayWnd, 1)
        self.video_caption = QLabel('Luồng trực tiếp từ đầu ghi', self.video_panel)
        self.sound_btn = QToolButton(self.video_panel)
        self.sound_btn.setEnabled(False)
        self.sound_btn.setAutoRaise(True)
        self.sound_btn.setToolTip('Bật âm thanh camera')
        self.sound_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaVolumeMuted))
        self.sound_btn.clicked.connect(self._toggle_sound)
        caption_row = QHBoxLayout()
        caption_row.setContentsMargins(0, 0, 0, 0)
        caption_row.addWidget(self.video_caption)
        caption_row.addStretch(1)
        caption_row.addWidget(self.sound_btn)
        video_layout.addLayout(caption_row)

        self.ai_panel = QFrame(workspace)
        ai_layout = QVBoxLayout(self.ai_panel)
        ai_layout.setContentsMargins(14, 14, 14, 14)
        ai_layout.setSpacing(10)
        ai_title = QLabel('SỰ KIỆN AI', self.ai_panel)
        ai_title.setStyleSheet('font-weight: 700;')
        ai_layout.addWidget(ai_title)
        ai_layout.addWidget(self.ai_check)
        ai_layout.addWidget(self.audio_check)
        ai_layout.addWidget(self.replay_event_combo)
        ai_layout.addWidget(self.replay_btn)
        event_columns = QSplitter(Qt.Horizontal, self.ai_panel)
        event_columns.setChildrenCollapsible(False)
        image_events = QFrame(event_columns)
        image_layout = QVBoxLayout(image_events)
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(5)
        image_layout.addWidget(QLabel('HÌNH ẢNH', image_events))
        image_layout.addWidget(self.cosmos_label)
        image_layout.addWidget(self.cosmos_log, 1)
        audio_events = QFrame(event_columns)
        audio_layout = QVBoxLayout(audio_events)
        audio_layout.setContentsMargins(0, 0, 0, 0)
        audio_layout.setSpacing(5)
        audio_layout.addWidget(QLabel('TIẾNG NÓI', audio_events))
        audio_layout.addWidget(self.audio_label)
        audio_layout.addWidget(self.audio_log, 1)
        audio_btn_row = QHBoxLayout()
        audio_btn_row.setSpacing(4)
        audio_btn_row.addWidget(self.audio_copy_btn)
        audio_btn_row.addWidget(self.audio_save_btn)
        audio_btn_row.addWidget(self.audio_clear_btn)
        audio_layout.addLayout(audio_btn_row)
        event_columns.setStretchFactor(0, 1)
        event_columns.setStretchFactor(1, 1)
        event_columns.setSizes([135, 135])
        ai_layout.addWidget(event_columns, 1)
        workspace.addWidget(self.connection_panel)
        workspace.addWidget(self.video_panel)
        workspace.addWidget(self.ai_panel)
        workspace.setStretchFactor(0, 0)
        workspace.setStretchFactor(1, 1)
        workspace.setStretchFactor(2, 0)
        workspace.setSizes([260, 720, 290])
        layout.addWidget(workspace, 1)
        self._apply_theme_styles()

    @staticmethod
    def _saved_theme_name():
        value = str(QSettings('DNC', 'DahuaControlCenter').value('appearance/theme', 'dark')).lower()
        return value if value in THEMES else 'dark'

    def apply_theme(self, theme_name):
        theme_name = str(theme_name).lower()
        if theme_name not in THEMES:
            return
        self._theme = THEMES[theme_name]
        self._apply_theme_styles()

    def _apply_theme_styles(self):
        t = self._theme
        self.centralwidget.setStyleSheet('background: {}; color: {};'.format(t.BG, t.P1))
        self.PlayWnd.setStyleSheet(
            'background: {}; border: 1px solid {}; border-radius: {}px; color: {};'.format(
                t.SIDEBAR, t.BD2, t.RADIUS_CARD, t.P2
            )
        )
        self.connection_panel.setStyleSheet(
            'QFrame {{ background: {}; border: 1px solid {}; border-radius: {}px; }} '
            'QLabel {{ color: {}; background: transparent; border: none; font-weight: 600; }} '
            'QLineEdit, QComboBox {{ background: {}; color: {}; border: 1px solid {}; border-radius: {}px; padding: 7px 9px; min-height: 22px; }} '
            'QPushButton {{ background: {}; color: {}; border: none; border-radius: {}px; padding: 8px 16px; font-weight: 700; min-height: 24px; }} '
            'QPushButton:disabled {{ background: {}; color: {}; }} '
            'QCheckBox {{ color: {}; background: transparent; }}'.format(
                t.S2, t.BD, t.RADIUS_CARD, t.P2, t.S1, t.P1, t.BD2, t.RADIUS_INPUT,
                t.ACCENT, t.P1, t.RADIUS_BTN, t.S3, t.P3, t.P2
            )
        )
        self.ai_panel.setStyleSheet(
            'QFrame {{ background: {}; border: 1px solid {}; border-radius: {}px; }} '
            'QLabel {{ color: {}; background: transparent; border: none; font-weight: 600; padding: 2px; }} '
            'QPlainTextEdit {{ background: {}; color: {}; border: none; font-family: {}; padding: 4px; }}'.format(
                t.S2, t.BD, t.RADIUS_CARD, t.P1, t.SIDEBAR, t.P2, t.MONO
            )
        )
        self.video_panel.setStyleSheet('background: {}; border: 1px solid {}; border-radius: {}px;'.format(t.S1, t.BD, t.RADIUS_CARD))
        self.sound_btn.setStyleSheet(
            'QToolButton {{ background: {}; color: {}; border: 1px solid {}; border-radius: {}px; padding: 6px; }} '
            'QToolButton:hover {{ background: {}; }} QToolButton:disabled {{ color: {}; }}'.format(
                t.S2, t.P1, t.BD2, t.RADIUS_BTN, t.S3, t.P3
            )
        )
        self.header_panel.setStyleSheet('background: {}; border: none; color: {}; QLabel {{ background: transparent; border: none; }}'.format(t.TOPBAR, t.P1))

    def _on_remember_toggled(self, checked):
        if not checked:
            self._clear_saved_connection()

    def _save_connection(self):
        save_connection(self.IP_lineEdit.text(), self.Port_lineEdit.text(),
                        self.Name_lineEdit.text(), self.Pwd_lineEdit.text())

    def _clear_saved_connection(self):
        clear_connection()

    def _on_ai_toggled(self, enabled):
        if enabled and not self._is_playing():
            self.ai_check.setChecked(False)
            return
        if enabled:
            self._ai_enabled = True
            self.cosmos_label.setText('Cosmos: đang chờ ảnh mẫu...')
            self.sample_timer.start()
            self._request_snapshot()
        else:
            self._ai_enabled = False
            self.sample_timer.stop()
            self.cosmos_label.setText('Cosmos: đã tắt')

    def _on_audio_toggled(self, enabled):
        if enabled and not self._is_playing():
            self.audio_check.setChecked(False)
            return
        self._audio_enabled = enabled
        if enabled:
            self.audio_label.setText('Tiếng nói: đang chờ đoạn âm thanh...')
            self.audio_timer.start()
            self._request_audio()
        else:
            self.audio_timer.stop()
            self._cancel_audio_capture()
            self.audio_label.setText('Tiếng nói: đã tắt')

    def _toggle_sound(self):
        if not self._is_playing():
            return
        if self._sound_enabled:
            if self.sdk.CloseSound(self.playID):
                self._set_sound_state(False)
            else:
                QMessageBox.warning(self, 'Âm thanh camera', self.sdk.GetLastErrorMessage())
        else:
            if self.sdk.OpenSound(self.playID):
                self._set_sound_state(True)
            else:
                QMessageBox.warning(self, 'Âm thanh camera', self.sdk.GetLastErrorMessage())

    def _set_sound_state(self, enabled):
        self._sound_enabled = bool(enabled)
        icon = QStyle.SP_MediaVolume if enabled else QStyle.SP_MediaVolumeMuted
        self.sound_btn.setIcon(self.style().standardIcon(icon))
        self.sound_btn.setToolTip('Tắt âm thanh camera' if enabled else 'Bật âm thanh camera')
        self.video_caption.setText(
            'Luồng trực tiếp từ đầu ghi — âm thanh đang bật'
            if enabled else 'Luồng trực tiếp từ đầu ghi — âm thanh đang tắt'
        )

    def _transcribe_url(self):
        value = self.cosmos_url.rstrip('/')
        if value.endswith('/transcribe'):
            return value
        if value.endswith('/analyze'):
            return value.rsplit('/', 1)[0] + '/transcribe'
        return value + '/transcribe'

    def _shutdown_url(self):
        value = self.cosmos_url.rstrip('/')
        if value.endswith('/shutdown'):
            return value
        if value.endswith('/analyze') or value.endswith('/transcribe'):
            return value.rsplit('/', 1)[0] + '/shutdown'
        return value + '/shutdown'

    def _audio_rtsp_url(self, ctx):
        """Use an explicit URL when the recorder has a non-standard RTSP layout."""
        template = os.getenv('COSMOS_AUDIO_RTSP_URL', '').strip()
        channel = ctx['channel']
        values = {
            'host': ctx['host'],
            'port': os.getenv('COSMOS_AUDIO_RTSP_PORT', '554').strip() or '554',
            'username': quote(ctx['username'], safe=''),
            'password': quote(ctx['password'], safe=''),
            'channel': int(channel or 0) + 1,
            'subtype': ctx['subtype'],
        }
        if template:
            return template.format(**values)
        return ('rtsp://{username}:{password}@{host}:{port}/'
                'cam/realmonitor?channel={channel}&subtype={subtype}').format(**values)

    def _safe_audio_error(self, message, ctx):
        """Never display an RTSP credential returned by FFmpeg."""
        safe = str(message)
        password = ctx['password']
        encoded_password = quote(password, safe='')
        for secret in (password, encoded_password, self._audio_rtsp_url(ctx)):
            if secret:
                safe = safe.replace(secret, '[đã ẩn]')
        return safe[-300:]

    def _request_audio(self):
        if not self._audio_enabled or not self._is_playing() or self._audio_inflight:
            return
        ctx = {
            'channel': self.Channel_comboBox.currentData(),
            'host': self.IP_lineEdit.text().strip(),
            'username': self.Name_lineEdit.text().strip(),
            'password': self.Pwd_lineEdit.text(),
            'subtype': self.StreamTyp_comboBox.currentIndex(),
            'play_handle': getattr(self.playID, 'value', self.playID),
        }
        self._audio_inflight = True
        captured_at = datetime.now().astimezone().isoformat(timespec='seconds')
        cancel = threading.Event()
        self._audio_cancel = cancel
        thread = threading.Thread(target=self._capture_and_transcribe_audio, args=(captured_at, ctx, cancel), daemon=True)
        self._audio_thread = thread
        thread.start()

    def _cancel_audio_capture(self, timeout=15.0):
        """Stop the audio worker and wait for it while SDK handles are still valid."""
        cancel = self._audio_cancel
        thread = self._audio_thread
        if cancel is not None:
            cancel.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout)
        self._audio_thread = None

    def _ffmpeg_path(self):
        configured = os.getenv('COSMOS_AUDIO_FFMPEG', '').strip()
        if configured and (os.path.isfile(configured) or shutil.which(configured)):
            return configured
        return shutil.which('ffmpeg') or 'ffmpeg'

    def _ffmpeg_audio_command(self, input_args):
        ffmpeg = self._ffmpeg_path()
        return [
            ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-threads', '2', '-probesize', '32768', '-analyzeduration', '0',
            *input_args,
            '-map', '0:a:0?', '-t', str(self.audio_chunk_seconds),
            '-vn', '-sn', '-dn',
            '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', '-f', 'wav', 'pipe:1',
        ]

    def _capture_audio_from_sdk(self, ctx, cancel):
        """Record the active NetSDK stream, avoiding a separately exposed RTSP port."""
        if cancel.is_set():
            return None, b''
        temp_dav = tempfile.NamedTemporaryFile(prefix='cosmos_live_', suffix='.dav', delete=False)
        media_path = temp_dav.name
        temp_dav.close()

        temp_wav = tempfile.NamedTemporaryFile(prefix='cosmos_live_', suffix='.wav', delete=False)
        wav_path = temp_wav.name
        temp_wav.close()

        play_handle = ctx['play_handle']
        try:
            os.unlink(media_path)
        except OSError:
            pass
        try:
            os.unlink(wav_path)
        except OSError:
            pass

        try:
            if not self.sdk.SaveRealData(play_handle, media_path):
                raise RuntimeError('NetSDK không bắt đầu được đoạn ghi: ' + self.sdk.GetLastErrorMessage())
            try:
                cancel.wait(self.audio_chunk_seconds)
            finally:
                self.sdk.StopSaveRealData(play_handle)
            if cancel.is_set():
                return None, b''
            if not os.path.exists(media_path) or os.path.getsize(media_path) < 512:
                self.audio_status.emit('Tiếng nói: Đang đồng bộ luồng âm thanh từ camera...')
                return None, b''

            ffmpeg = self._ffmpeg_path()
            command = [
                ffmpeg, '-y', '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-threads', '2', '-probesize', '2000000', '-analyzeduration', '2000000',
                '-i', media_path,
                '-map', '0:a:0?', '-t', str(self.audio_chunk_seconds),
                '-vn', '-sn', '-dn',
                '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
                wav_path,
            ]
            completed = subprocess.run(command, capture_output=True, timeout=self.audio_chunk_seconds + 20, check=False)
            if completed.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1024:
                self.audio_status.emit('Tiếng nói: Đang lắng nghe luồng âm thanh trực tiếp...')
                return None, b''

            with open(wav_path, 'rb') as f:
                wav_bytes = f.read()
            return completed, wav_bytes
        finally:
            for p in (media_path, wav_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def _capture_audio_from_rtsp(self, ctx, cancel):
        if cancel.is_set():
            return None, b''
        temp_wav = tempfile.NamedTemporaryFile(prefix='cosmos_rtsp_', suffix='.wav', delete=False)
        wav_path = temp_wav.name
        temp_wav.close()
        try:
            os.unlink(wav_path)
        except OSError:
            pass

        io_timeout_us = str(int(self.audio_connect_timeout_seconds * 1_000_000))
        process_timeout = self.audio_connect_timeout_seconds + self.audio_chunk_seconds + 12
        ffmpeg = self._ffmpeg_path()
        command = [
            ffmpeg, '-y', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-rtsp_transport', 'tcp', '-rw_timeout', io_timeout_us, '-timeout', io_timeout_us,
            '-analyzeduration', '2000000', '-probesize', '2000000', '-i', self._audio_rtsp_url(ctx),
            '-map', '0:a:0?', '-t', str(self.audio_chunk_seconds),
            '-vn', '-sn', '-dn',
            '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
            wav_path,
        ]
        try:
            completed = subprocess.run(command, capture_output=True, timeout=process_timeout, check=False)
            if cancel.is_set():
                return None, b''
            if completed.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1024:
                self.audio_status.emit('Tiếng nói: Đang lắng nghe luồng âm thanh trực tiếp...')
                return None, b''
            with open(wav_path, 'rb') as f:
                wav_bytes = f.read()
            return completed, wav_bytes
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass

    def _save_audio_debug_sample(self, wav_bytes, captured_at, source, channel):
        configured = os.getenv('COSMOS_AUDIO_DEBUG_DIR', '').strip()
        digest = hashlib.sha256(wav_bytes).hexdigest()
        if not configured:
            return None, digest
        debug_dir = Path(configured).expanduser().resolve()
        debug_dir.mkdir(parents=True, exist_ok=True)
        stamp = ''.join(char for char in captured_at if char.isdigit())[:14]
        path = debug_dir / 'audio_ch{}_{}_{}_{}.wav'.format(
            int(channel or 0) + 1, stamp, source, digest[:12]
        )
        path.write_bytes(wav_bytes)
        try:
            keep = max(1, int(os.getenv('COSMOS_AUDIO_DEBUG_MAX_FILES', '10')))
        except ValueError:
            keep = 10
        samples = sorted(debug_dir.glob('audio_ch*_*.wav'), key=lambda item: item.stat().st_mtime, reverse=True)
        for old_sample in samples[keep:]:
            try:
                old_sample.unlink()
            except OSError:
                pass
        return str(path), digest

    def _transcribe_locally(self, wav_bytes, captured_at, source, channel):
        """Perform in-process speech-to-text with multi-stage VAD and PhoWhisper."""
        import numpy as np

        marker = wav_bytes.find(b'data')
        offset = marker + 8 if marker >= 0 else 44
        pcm = wav_bytes[offset:]
        if len(pcm) % 2:
            pcm = pcm[:-1]
        samples = (
            np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
            if len(pcm) >= 2 else np.empty(0, dtype=np.float32)
        )
        if samples.size == 0:
            return {
                'status': 'ok',
                'captured_at': captured_at,
                'channel': channel,
                'transcription_ms': 0,
                'text': '',
                'speech_detected': False,
                'ignored_reason': 'empty_audio',
                'audio_rms': 0.0,
                'audio_peak': 0.0,
                'audio_source': source + ' (local)',
                'audio_sha256': hashlib.sha256(wav_bytes).hexdigest(),
                'audio_model': os.getenv('COSMOS_AUDIO_MODEL', 'vinai/PhoWhisper-small'),
            }

        # Khử DC Offset
        samples = samples - np.mean(samples)
        rms = float(np.sqrt(np.mean(np.square(samples))))
        peak = float(np.max(np.abs(samples)))

        min_rms = float(os.getenv('COSMOS_AUDIO_MIN_RMS', '0.012'))
        min_peak = float(os.getenv('COSMOS_AUDIO_MIN_PEAK', '0.064'))

        frame_size = 480  # 30 ms tại 16kHz
        frame_count = samples.size // frame_size

        # Tầng 1: Ngưỡng sàn năng lượng tuyệt đối (đã hạ 20% để nhạy hơn với âm lượng micro thực tế)
        if rms < min_rms or peak < min_peak or frame_count < 8:
            return {
                'status': 'ok',
                'captured_at': captured_at,
                'channel': channel,
                'transcription_ms': 0,
                'text': '',
                'speech_detected': False,
                'ignored_reason': 'below_minimum_energy',
                'audio_rms': round(rms, 6),
                'audio_peak': round(peak, 6),
                'audio_source': source + ' (local)',
                'audio_sha256': hashlib.sha256(wav_bytes).hexdigest(),
                'audio_model': os.getenv('COSMOS_AUDIO_MODEL', 'vinai/PhoWhisper-small'),
            }

        # Tầng 2: Sàn nhiễu nền tĩnh (Stationary Noise Floor) & Tỷ lệ động SNR
        frames = samples[:frame_count * frame_size].reshape(frame_count, frame_size)
        frame_rms = np.sqrt(np.mean(np.square(frames), axis=1))
        noise_floor = max(float(np.percentile(frame_rms, 20)), 1e-6)
        active_threshold = max(min_rms, noise_floor * 1.60)
        active_mask = frame_rms >= active_threshold
        active_seconds = float(np.count_nonzero(active_mask) * 0.03)
        dynamic_ratio = float(np.percentile(frame_rms, 90) / noise_floor)

        min_active_seconds = float(os.getenv('COSMOS_AUDIO_MIN_ACTIVE_SECONDS', '0.36'))
        min_dynamic_ratio = float(os.getenv('COSMOS_AUDIO_MIN_DYNAMIC_RATIO', '1.44'))

        if active_seconds < min_active_seconds or dynamic_ratio < min_dynamic_ratio:
            return {
                'status': 'ok',
                'captured_at': captured_at,
                'channel': channel,
                'transcription_ms': 0,
                'text': '',
                'speech_detected': False,
                'ignored_reason': f'stationary_noise (act={active_seconds:.2f}s, dyn={dynamic_ratio:.2f})',
                'audio_rms': round(rms, 6),
                'audio_peak': round(peak, 6),
                'audio_source': source + ' (local)',
                'audio_sha256': hashlib.sha256(wav_bytes).hexdigest(),
                'audio_model': os.getenv('COSMOS_AUDIO_MODEL', 'vinai/PhoWhisper-small'),
            }

        # Tầng 3: Kiểm tra dải phổ giọng nói con người (300Hz - 3400Hz)
        fft = np.abs(np.fft.rfft(samples))
        freqs = np.fft.rfftfreq(len(samples), 1 / 16000)
        speech_band = np.sum(fft[(freqs >= 300) & (freqs <= 3400)])
        total_band = np.sum(fft) + 1e-6
        speech_ratio = speech_band / total_band

        if speech_ratio < 0.30:
            return {
                'status': 'ok',
                'captured_at': captured_at,
                'channel': channel,
                'transcription_ms': 0,
                'text': '',
                'speech_detected': False,
                'ignored_reason': f'non_speech_spectrum (speech_ratio={speech_ratio:.2f})',
                'audio_rms': round(rms, 6),
                'audio_peak': round(peak, 6),
                'audio_source': source + ' (local)',
                'audio_sha256': hashlib.sha256(wav_bytes).hexdigest(),
                'audio_model': os.getenv('COSMOS_AUDIO_MODEL', 'vinai/PhoWhisper-small'),
            }

        # Tầng 4: Chuẩn hóa an toàn (Chỉ scale nhẹ nếu có âm thanh rõ ràng, tuyệt đối không khuếch đại tạp âm nền)
        if peak > 0.15:
            normalized_samples = (samples / peak * 0.85).astype(np.float32)
        else:
            normalized_samples = samples

        if self._local_audio_pipeline is None:
            self.audio_status.emit('Tiếng nói: đang nạp mô hình PhoWhisper vào bộ nhớ...')
            import torch
            from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

            model_id = os.getenv('COSMOS_AUDIO_MODEL', 'vinai/PhoWhisper-small').strip() or 'vinai/PhoWhisper-small'
            use_cuda = torch.cuda.is_available()
            if not use_cuda:
                # Giới hạn 2 luồng CPU để không chiếm dụng CPU, giữ luồng render video luôn mượt 100%
                torch.set_num_threads(min(2, os.cpu_count() or 2))
            dtype = torch.float16 if use_cuda else torch.float32
            if use_cuda:
                torch.backends.cudnn.benchmark = True
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id, torch_dtype=dtype, low_cpu_mem_usage=True, use_safetensors=False
            )
            if use_cuda:
                model.to('cuda')
            model.eval()
            processor = AutoProcessor.from_pretrained(model_id)
            self._local_audio_pipeline = pipeline(
                'automatic-speech-recognition',
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                dtype=dtype,
                device=0 if use_cuda else -1,
                max_new_tokens=128,
            )
            # Warm up pipeline to eliminate cold-start lag
            try:
                with torch.inference_mode():
                    dummy = np.zeros(16000, dtype=np.float32)
                    self._local_audio_pipeline(dummy, generate_kwargs={'task': 'transcribe', 'num_beams': 1, 'max_new_tokens': 8})
            except Exception:
                pass

        t0 = time.perf_counter()
        try:
            import torch
            import re
            beam_size = int(os.getenv('COSMOS_AUDIO_BEAM_SIZE', '1'))
            gen_kwargs = {
                'task': 'transcribe',
                'do_sample': False,
                'num_beams': beam_size,
                'condition_on_prev_tokens': False,
                'temperature': 0.0,
                'repetition_penalty': 1.35,
                'no_repeat_ngram_size': 3,
            }
            lang = os.getenv('COSMOS_AUDIO_LANGUAGE', 'vi').strip() or 'vi'
            if lang != 'auto':
                gen_kwargs['language'] = lang
            with torch.inference_mode():
                res = self._local_audio_pipeline(normalized_samples, generate_kwargs=gen_kwargs)
            text = ' '.join(str(res.get('text', '')).split()).strip()

            # Tầng 5 & 6: Bộ lọc kiểm định tốc độ nói & chống ảo giác triệt để
            if text:
                text_clean = text.strip()
                text_lower = text_clean.lower()
                words = re.findall(r'\w+', text_lower, flags=re.UNICODE)
                word_count = len(words)

                # 5.1: Kiểm tra tính hợp lý của tốc độ nói (Speech Rate Plausibility)
                # Tốc độ nói tiếng Việt tự nhiên ~ 2.5 - 3.5 từ/giây. Giới hạn 5.0 từ/giây để không chặn người nói nhanh
                if word_count > 0 and (word_count / max(active_seconds, 0.2)) > 5.0:
                    text = ''

                # 5.2: Kiểm tra đa dạng từ vựng (chống vòng lặp lặp từ)
                elif word_count >= 6 and (len(set(words)) / word_count < 0.45):
                    text = ''

                # 5.3: Danh sách đen các cụm từ ảo giác phổ biến
                else:
                    hallucinations = [
                        'cảm ơn các bạn đã xem', 'cảm ơn các bạn đã theo dõi', 'cảm ơn đã xem',
                        'hãy like và subscribe', 'đăng ký kênh', 'hãy đăng ký', 'subscribe',
                        'hẹn gặp lại', 'chúc các bạn', 'nhiều doanh nghiệp đã', 'nhiều người đã đặt',
                        'đoàn kệ thời gian', 'tới gói sáp', 'tới phết cổ', 'tinh thần tái diễn',
                        'nàng thông cáo', 'nhà hàng đầu có thể', 'nàng hơi', 'lalaschool',
                        'thanks for watching', 'subtitles by', 'bản quyền thuộc về'
                    ]
                    if any(h in text_lower for h in hallucinations) or len(text_clean) < 2:
                        text = ''

            latency = int((time.perf_counter() - t0) * 1000)
            return {
                'status': 'ok',
                'captured_at': captured_at,
                'channel': channel,
                'transcription_ms': latency,
                'text': text,
                'speech_detected': bool(text),
                'audio_rms': round(rms, 6),
                'audio_peak': round(peak, 6),
                'audio_active_seconds': round(active_seconds, 2),
                'audio_source': source + ' (local)',
                'audio_sha256': hashlib.sha256(wav_bytes).hexdigest(),
                'audio_model': os.getenv('COSMOS_AUDIO_MODEL', 'vinai/PhoWhisper-small'),
            }
        except Exception:
            return {
                'status': 'ok',
                'captured_at': captured_at,
                'channel': channel,
                'transcription_ms': 0,
                'text': '',
                'speech_detected': False,
                'audio_rms': round(rms, 6),
                'audio_peak': round(peak, 6),
                'audio_source': source + ' (local)',
                'audio_sha256': hashlib.sha256(wav_bytes).hexdigest(),
                'audio_model': os.getenv('COSMOS_AUDIO_MODEL', 'vinai/PhoWhisper-small'),
            }

    def _capture_and_transcribe_audio(self, captured_at, ctx, cancel):
        try:
            source = os.getenv('COSMOS_AUDIO_SOURCE', 'sdk').strip().lower()
            mode = os.getenv('COSMOS_AUDIO_MODE', 'local').strip().lower()
            completed, wav_bytes = self._capture_audio_from_rtsp(ctx, cancel) if source == 'rtsp' else self._capture_audio_from_sdk(ctx, cancel)
            if completed is None or cancel.is_set() or not wav_bytes:
                return

            channel = ctx['channel']
            debug_path, audio_sha256 = self._save_audio_debug_sample(
                wav_bytes, captured_at, source, channel
            )

            if mode == 'local':
                payload = self._transcribe_locally(wav_bytes, captured_at, source, channel)
                payload['audio_debug_path'] = debug_path
                self.audio_result.emit(payload)
                return

            endpoint = self._transcribe_url()
            req = urlrequest.Request(endpoint, data=wav_bytes, headers={
                'Content-Type': 'application/octet-stream',
                'X-Cosmos-Device-Id': os.getenv('COSMOS_DEVICE_ID', ctx['host']),
                'X-Cosmos-Channel': str(channel if channel is not None else ''),
                'X-Cosmos-Captured-At': captured_at,
                'X-Cosmos-Audio-Source': source,
                'X-Cosmos-Audio-Sha256': audio_sha256,
            }, method='POST')
            try:
                with urlrequest.urlopen(req, timeout=float(os.getenv('COSMOS_AUDIO_TIMEOUT_SECONDS', '120'))) as response:
                    payload = json.loads(response.read().decode('utf-8'))
                    payload['audio_debug_path'] = debug_path
                    self.audio_result.emit(payload)
            except Exception as net_err:
                fallback_local = os.getenv('COSMOS_AUDIO_FALLBACK_LOCAL', '1').strip().lower() in {'1', 'true', 'yes'}
                if fallback_local:
                    self.audio_status.emit('Tiếng nói: Service không hoạt động, chuyển sang PhoWhisper nội bộ...')
                    payload = self._transcribe_locally(wav_bytes, captured_at, source, channel)
                    payload['audio_debug_path'] = debug_path
                    self.audio_result.emit(payload)
                else:
                    raise net_err
        except HTTPError as exc:
            self.audio_status.emit('Tiếng nói: {} {}'.format(exc.code, exc.read().decode('utf-8', 'replace')[:100]))
        except subprocess.TimeoutExpired:
            if source == 'rtsp':
                self.audio_status.emit(
                    'Tiếng nói: RTSP quá thời gian kết nối; kiểm tra cổng RTSP và audio của kênh camera.'
                )
            else:
                self.audio_status.emit('Tiếng nói: FFmpeg xử lý đoạn media quá thời gian.')
        except (URLError, TimeoutError, ConnectionError, OSError) as exc:
            self.audio_status.emit('Tiếng nói: không kết nối được dịch vụ ({})'.format(exc))
        except Exception as exc:
            self.audio_status.emit('Tiếng nói: {}'.format(self._safe_audio_error(exc, ctx)))
        finally:
            self._audio_inflight = False

    def _request_snapshot(self):
        if (not self.ai_check.isChecked() or not self._is_playing() or
                self._snapshot_pending or self._inference_inflight):
            return
        channel = self.Channel_comboBox.currentData()
        if channel is None:
            return
        snap = SNAP_PARAMS()
        snap.Channel = channel
        snap.Quality = 3
        snap.ImageSize = 0
        snap.mode = 0
        self._snap_serial = (self._snap_serial + 1) % 65536
        self._capture_times[self._snap_serial] = datetime.now().astimezone().isoformat(timespec='seconds')
        snap.CmdSerial = self._snap_serial
        self._snapshot_pending = True
        if not self.sdk.SnapPictureEx(self.loginID, snap):
            self._snapshot_pending = False
            self.cosmos_status.emit('Cosmos: không lấy được ảnh mẫu từ đầu ghi')

    def SnapshotCallBack(self, login_id, buffer, length, encode_type, cmd_serial, user):
        current_login = getattr(self.loginID, 'value', self.loginID)
        callback_login = getattr(login_id, 'value', login_id)
        if not self._is_logged_in() or callback_login != current_login:
            return
        self._snapshot_pending = False
        image_format = getattr(encode_type, 'value', encode_type)
        if not self._ai_enabled or self._inference_inflight or image_format != 10:
            return
        byte_count = getattr(length, 'value', length)
        image_bytes = bytes(cast(buffer, POINTER(c_ubyte * byte_count)).contents)
        self._inference_inflight = True
        captured_at = self._capture_times.pop(int(cmd_serial), datetime.now().astimezone().isoformat(timespec='seconds'))
        threading.Thread(target=self._send_to_cosmos, args=(image_bytes, captured_at), daemon=True).start()

    def _send_to_cosmos(self, image_bytes, captured_at):
        try:
            channel = self.Channel_comboBox.currentData()
            req = urlrequest.Request(self.cosmos_url, data=image_bytes, headers={
                'Content-Type': 'application/octet-stream',
                'X-Cosmos-Device-Id': os.getenv('COSMOS_DEVICE_ID', self.IP_lineEdit.text().strip()),
                'X-Cosmos-Channel': str(channel if channel is not None else ''),
                'X-Cosmos-Captured-At': captured_at,
            }, method='POST')
            # First inference can include CUDA graph warm-up and take longer
            # than a normal frame.  Do not abandon it after 15 seconds: an
            # abandoned request keeps the service busy and causes 429s for
            # subsequent snapshots.
            timeout_seconds = float(os.getenv('COSMOS_TIMEOUT_SECONDS', '90'))
            with urlrequest.urlopen(req, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode('utf-8'))
            self.cosmos_result.emit(payload)
        except HTTPError as exc:
            if exc.code == 429:
                self.cosmos_status.emit('Cosmos: đang xử lý khung hình trước...')
            elif exc.code == 500:
                self.cosmos_status.emit('Cosmos: khung hình phức tạp, đang lấy mẫu tiếp theo...')
            else:
                self.cosmos_status.emit('Cosmos: mã lỗi HTTP {}'.format(exc.code))
        except (URLError, TimeoutError, ValueError) as exc:
            self.cosmos_status.emit('Cosmos: không kết nối được ({})'.format(exc))
        except Exception as exc:
            self.cosmos_status.emit('Cosmos: đang kết nối lại...')
        finally:
            self._inference_inflight = False

    def _show_cosmos_result(self, payload):
        if payload.get('duplicate'):
            self.cosmos_label.setText('Cosmos: kết quả không đổi — đã bỏ qua cảnh báo trùng lặp')
            return
        result = payload.get('result', {})
        text = '{} | {} | {} ms'.format(
            result.get('risk_level', 'none').upper(), result.get('summary', 'Không có mô tả'),
            payload.get('inference_ms', '?'))
        self._last_replay = payload.get('replay')
        if self._last_replay:
            self._add_replay_event(self._last_replay)
        self.cosmos_label.setText('Cosmos: đã nhận kết quả phân tích')
        current = self.cosmos_log.toPlainText().strip()
        if current:
            self.cosmos_log.setPlainText(text + '\n' + current)
        else:
            self.cosmos_log.setPlainText(text)

    def _add_replay_event(self, replay):
        """Keep a bounded, in-session list; the server retains the JSONL audit history."""
        self._replay_events.insert(0, replay)
        self.replay_event_combo.insertItem(0, self._replay_event_label(replay), replay)
        while self.replay_event_combo.count() > 50:
            self.replay_event_combo.removeItem(self.replay_event_combo.count() - 1)
            self._replay_events.pop()
        self.replay_event_combo.setCurrentIndex(0)
        self.replay_event_combo.setEnabled(True)
        self.replay_btn.setEnabled(True)

    @staticmethod
    def _replay_event_label(replay):
        summary = ' '.join(str(replay.get('summary', '')).split())[:90]
        return '{} | {} | {}'.format(
            replay.get('event_time', ''), str(replay.get('risk_level', 'none')).upper(), summary or 'Không có mô tả'
        )

    def _open_last_replay(self):
        replay = self.replay_event_combo.currentData() or self._last_replay
        if not replay:
            return
        try:
            from Demo.PlayBackDemo.PlayBackDemo import MyMainWindow as PlaybackWindow
            window = PlaybackWindow()
            # Ensure the native playback surface exists before NetSDK binds to it.
            window.show()
            window.configure_replay(
                host=self.IP_lineEdit.text().strip(), port=self.Port_lineEdit.text().strip(),
                username=self.Name_lineEdit.text().strip(), password=self.Pwd_lineEdit.text(),
                channel=int(replay['channel']), start_time=replay['replay_start'], end_time=replay['replay_end'],
            )
            self._replay_windows.append(window)
            window.destroyed.connect(lambda *_: self._replay_windows.remove(window) if window in self._replay_windows else None)
        except Exception as exc:
            QMessageBox.warning(self, 'Xem lại', 'Không thể mở cửa sổ Playback: {}'.format(exc))

    def _show_cosmos_status(self, text):
        self.cosmos_label.setText(text)

    def _show_audio_result(self, payload):
        text = str(payload.get('text', '')).strip()
        rms = float(payload.get('audio_rms', 0.0))
        peak = float(payload.get('audio_peak', 0.0))
        channel = payload.get('channel')
        try:
            channel_label = 'Kênh {}'.format(int(channel) + 1)
        except (TypeError, ValueError):
            channel_label = 'Kênh ?'

        captured_at = payload.get('captured_at', '')
        stamp = captured_at.replace('T', ' ')[:19] if captured_at else ''

        if not payload.get('speech_detected', bool(text)) or not text:
            if rms < 0.012:
                self.audio_label.setText(f'Tiếng nói: [{channel_label}] Yên tĩnh (RMS: {rms:.4f}) — Không có người nói')
            else:
                level_pct = min(100, int(peak * 100))
                self.audio_label.setText(f'Tiếng nói: [{channel_label}] Âm lượng {level_pct}% (RMS: {rms:.4f}) — Tạp âm/Đang lắng nghe')
            return

        level_pct = min(100, int(peak * 100))
        self.audio_label.setText(f'Tiếng nói: [{stamp} - {channel_label} - Âm lượng {level_pct}%] {text[:50]}...')

        # Chỉ ghi nội dung có lời nói thực tế đã qua xác thực vào khung nhật ký
        log_line = f"[{stamp} - {channel_label}]: {text}"
        self.audio_log.appendPlainText(log_line)

        self._live_transcripts.append({
            'captured_at': stamp,
            'channel': channel_label,
            'text': text,
            'rms': rms,
            'peak': peak,
            'latency_ms': payload.get('transcription_ms', 0),
            'model': payload.get('audio_model', 'PhoWhisper'),
        })

    def _copy_audio_log(self):
        text = self.audio_log.toPlainText().strip()
        if not text:
            QMessageBox.information(self, 'Thông báo', 'Chưa có nhật ký tiếng nói để sao chép.')
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.audio_label.setText('Tiếng nói: đã sao chép nhật ký vào Clipboard')

    def _save_audio_log(self):
        if not self._live_transcripts:
            text = self.audio_log.toPlainText().strip()
            if not text:
                QMessageBox.information(self, 'Thông báo', 'Chưa có nhật ký tiếng nói để lưu.')
                return
            save_path, _ = QFileDialog.getSaveFileName(self, 'Lưu nhật ký tiếng nói', 'camera_audio_log.txt', 'Text Files (*.txt)')
            if save_path:
                Path(save_path).write_text(text, encoding='utf-8')
                QMessageBox.information(self, 'Thành công', f'Đã lưu kết quả vào:\n{save_path}')
            return

        save_path, _ = QFileDialog.getSaveFileName(self, 'Lưu nhật ký tiếng nói', 'camera_transcript.txt', 'Text Files (*.txt);;SubRip Subtitles (*.srt)')
        if not save_path:
            return
        if save_path.lower().endswith('.srt'):
            srt_lines = []
            for idx, item in enumerate(self._live_transcripts, 1):
                srt_lines.append(str(idx))
                srt_lines.append('00:00:00,000 --> 00:00:10,000')
                srt_lines.append(item['text'])
                srt_lines.append('')
            Path(save_path).write_text('\n'.join(srt_lines), encoding='utf-8')
        else:
            lines = [f"[{item['captured_at']} - {item['channel']}]: {item['text']}" for item in self._live_transcripts]
            Path(save_path).write_text('\n'.join(lines), encoding='utf-8')
        QMessageBox.information(self, 'Thành công', f'Đã lưu kết quả vào:\n{save_path}')

    def _clear_audio_log(self):
        self.audio_log.clear()
        self._live_transcripts.clear()
        self.audio_label.setText('Tiếng nói: đã dọn nhật ký')

    def _show_audio_status(self, text):
        # Chỉ cập nhật nhãn trạng thái, KHÔNG ghi đè thông báo hệ thống vào khung văn bản nói chuyện
        self.audio_label.setText(text)

    def _shutdown_cosmos_if_enabled(self):
        if not self.cosmos_stop_on_exit:
            return
        shutdown_url = self._shutdown_url()
        try:
            req = urlrequest.Request(shutdown_url, data=b'', method='POST')
            urlrequest.urlopen(req, timeout=2).close()
        except Exception:
            # Closing the camera UI must never be delayed by a stopped or
            # remote Cosmos service.
            pass

    def _is_logged_in(self):
        return bool(getattr(self.loginID, 'value', self.loginID))

    def _is_playing(self):
        return bool(getattr(self.playID, 'value', self.playID))

    def _set_login_fields_enabled(self, enabled):
        for field in (self.IP_lineEdit, self.Port_lineEdit, self.Name_lineEdit, self.Pwd_lineEdit):
            field.setEnabled(enabled)

    def _set_connection_state(self, connected):
        if connected:
            self.setWindowTitle('Xem trực tiếp - Trực tuyến')
            self.header_status.setText('TRỰC TUYẾN')
            self.statusbar.showMessage('Đã kết nối đầu ghi')
        else:
            self.setWindowTitle('Xem trực tiếp - Mất kết nối')
            self.header_status.setText('MẤT KẾT NỐI')
            self.statusbar.showMessage('Mất kết nối đầu ghi; SDK đang tự kết nối lại')

    def login_btn_onclick(self):
        if self._is_logged_in():
            self._logout()
            return
        ip = self.IP_lineEdit.text().strip()
        port_text = self.Port_lineEdit.text().strip()
        username = self.Name_lineEdit.text().strip()
        password = self.Pwd_lineEdit.text()
        if not ip or not port_text or not username or not password:
            QMessageBox.warning(self, 'Thiếu cấu hình', 'Nhập IP, cổng SDK, tên đăng nhập và mật khẩu.')
            return

        login_in = NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY()
        login_in.dwSize = sizeof(NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY)
        login_in.szIP = ip.encode()
        login_in.nPort = int(port_text)
        login_in.szUserName = username.encode()
        login_in.szPassword = password.encode()
        login_in.emSpecCap = EM_LOGIN_SPAC_CAP_TYPE.TCP
        login_in.pCapParam = None
        login_out = NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY()
        login_out.dwSize = sizeof(NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY)
        self.loginID, device_info, error_msg = self.sdk.LoginWithHighLevelSecurity(login_in, login_out)
        if not self._is_logged_in():
            QMessageBox.warning(self, 'Không thể đăng nhập', error_msg)
            return

        if self.remember_check.isChecked():
            self._save_connection()
        self._set_connection_state(True)
        self.login_btn.setText('Đăng xuất')
        self.play_btn.setEnabled(True)
        self._set_login_fields_enabled(False)
        self.Channel_comboBox.clear()
        for channel in range(int(device_info.nChanNum)):
            self.Channel_comboBox.addItem('Kênh {}'.format(channel + 1), channel)
        self.StreamTyp_comboBox.setEnabled(True)
        self.statusbar.showMessage('Đã kết nối. Phát hiện {} kênh camera.'.format(device_info.nChanNum))

    def _logout(self):
        self._stop_preview()
        if not self.sdk.Logout(self.loginID):
            QMessageBox.warning(self, 'Không thể đăng xuất', self.sdk.GetLastErrorMessage())
            return
        self.loginID = C_LLONG()
        self.login_btn.setText('Đăng nhập')
        self.play_btn.setEnabled(False)
        self.StreamTyp_comboBox.setEnabled(False)
        self.Channel_comboBox.clear()
        self._set_login_fields_enabled(True)
        self.setWindowTitle('Xem trực tiếp - Ngoại tuyến')
        self.header_status.setText('NGOẠI TUYẾN')
        self.statusbar.showMessage('Đã đăng xuất')

    def play_btn_onclick(self):
        if self._is_playing():
            self._stop_preview()
            return
        if self.Channel_comboBox.currentIndex() < 0:
            QMessageBox.warning(self, 'Chưa có camera', 'Đầu ghi không trả về kênh camera nào.')
            return
        channel = self.Channel_comboBox.currentData()
        stream_type = (SDK_RealPlayType.Realplay if self.StreamTyp_comboBox.currentIndex() == 0 else SDK_RealPlayType.Realplay_1)
        self.playID = self.sdk.RealPlayEx(self.loginID, channel, self.PlayWnd.winId(), stream_type)
        if not self._is_playing():
            QMessageBox.warning(self, 'Không thể mở luồng', self.sdk.GetLastErrorMessage())
            return
        self.play_btn.setText('Dừng xem')
        self.StreamTyp_comboBox.setEnabled(False)
        self.Channel_comboBox.setEnabled(False)
        self.ai_check.setEnabled(True)
        self.audio_check.setEnabled(True)
        self.sound_btn.setEnabled(True)
        self._set_sound_state(False)
        self.audio_check.setChecked(True)
        self.statusbar.showMessage('Đang xem Kênh {} ({})'.format(channel + 1, self.StreamTyp_comboBox.currentText()))

    def _stop_preview(self):
        self._cancel_audio_capture()
        if not self._is_playing():
            return
        self.ai_check.setChecked(False)
        self.ai_check.setEnabled(False)
        self.audio_check.setChecked(False)
        self.audio_check.setEnabled(False)
        if self._sound_enabled:
            self.sdk.CloseSound(self.playID)
        self._set_sound_state(False)
        self.sound_btn.setEnabled(False)
        if self.sdk.StopRealPlayEx(self.playID):
            self.playID = C_LLONG()
            self.play_btn.setText('Bắt đầu xem')
            self.StreamTyp_comboBox.setEnabled(True)
            self.Channel_comboBox.setEnabled(True)
            self.PlayWnd.repaint()
            self.statusbar.showMessage('Đã dừng xem trực tiếp')

    def DisConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.connection_changed.emit(False)

    def ReConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.connection_changed.emit(True)

    def closeEvent(self, event):
        self.sample_timer.stop()
        self.audio_timer.stop()
        self._cancel_audio_capture()
        self._stop_preview()
        if self._is_logged_in():
            self.sdk.Logout(self.loginID)
        self.sdk.Cleanup()
        self._shutdown_cosmos_if_enabled()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MyMainWindow()
    window.show()
    sys.exit(app.exec_())
