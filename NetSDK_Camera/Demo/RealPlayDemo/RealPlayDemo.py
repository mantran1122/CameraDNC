# coding=utf-8
"""Dahua connection and live-preview MVP."""
import os
import sys
import json
import threading
from datetime import datetime
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
from ctypes import POINTER, c_ubyte, cast, sizeof

from PyQt5.QtCore import Qt, QSettings, QTimer, pyqtSignal
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPlainTextEdit, QSizePolicy, QSplitter, QVBoxLayout,
    QPushButton,
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
        self._snapshot_pending = False
        self._inference_inflight = False
        self._ai_enabled = False
        self._snap_serial = 0
        self._capture_times = {}
        self._last_replay = None
        self._replay_events = []
        self._replay_windows = []
        self.cosmos_url = os.getenv('COSMOS_LIVE_URL', 'http://127.0.0.1:8765/analyze')
        self.cosmos_interval_seconds = _positive_float_from_env('COSMOS_SAMPLE_INTERVAL_SECONDS', 10)
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
        self._build_responsive_layout()
        self.statusbar.showMessage('Chưa kết nối đầu ghi')
        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint)
        self.login_btn.clicked.connect(self.login_btn_onclick)
        self.play_btn.clicked.connect(self.play_btn_onclick)
        self.sample_timer = QTimer(self)
        self.sample_timer.setInterval(int(self.cosmos_interval_seconds * 1000))
        self.sample_timer.timeout.connect(self._request_snapshot)

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
        video_layout.addWidget(self.video_caption)

        self.ai_panel = QFrame(workspace)
        ai_layout = QVBoxLayout(self.ai_panel)
        ai_layout.setContentsMargins(14, 14, 14, 14)
        ai_layout.setSpacing(10)
        ai_title = QLabel('SỰ KIỆN AI', self.ai_panel)
        ai_title.setStyleSheet('font-weight: 700;')
        ai_layout.addWidget(ai_title)
        ai_layout.addWidget(self.ai_check)
        ai_layout.addWidget(self.cosmos_label)
        ai_layout.addWidget(self.replay_event_combo)
        ai_layout.addWidget(self.replay_btn)
        ai_layout.addWidget(self.cosmos_log)
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
            'QLabel {{ color: {}; font-weight: 600; }} '
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
            'QLabel {{ color: {}; background: transparent; font-weight: 600; padding: 2px; }} '
            'QPlainTextEdit {{ background: {}; color: {}; border: none; font-family: {}; padding: 4px; }}'.format(
                t.S2, t.BD, t.RADIUS_CARD, t.P1, t.SIDEBAR, t.P2, t.MONO
            )
        )
        self.video_panel.setStyleSheet('background: {}; border: 1px solid {}; border-radius: {}px;'.format(t.S1, t.BD, t.RADIUS_CARD))
        self.header_panel.setStyleSheet('background: {}; border: 1px solid {}; border-radius: {}px; color: {};'.format(t.TOPBAR, t.BD, t.RADIUS_CARD, t.P1))

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
                self.cosmos_status.emit('Cosmos: đang phân tích khung hình trước...')
            else:
                self.cosmos_status.emit('Cosmos: {} {}'.format(exc.code, exc.read().decode('utf-8', 'replace')[:100]))
        except (URLError, TimeoutError, ValueError) as exc:
            self.cosmos_status.emit('Cosmos: không kết nối được ({})'.format(exc))
        except Exception as exc:
            self.cosmos_status.emit('Cosmos: lỗi phân tích ({})'.format(exc))
        finally:
            self._inference_inflight = False

    def _show_cosmos_result(self, payload):
        result = payload.get('result', {})
        text = '{} | {} | {} ms'.format(
            result.get('risk_level', 'none').upper(), result.get('summary', 'Không có mô tả'),
            payload.get('inference_ms', '?'))
        self._last_replay = payload.get('replay')
        if self._last_replay:
            self._add_replay_event(self._last_replay)
        self.cosmos_label.setText('Cosmos: đã nhận kết quả phân tích')
        self.cosmos_log.appendPlainText(text)

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
        self.cosmos_log.appendPlainText(text)

    def _shutdown_cosmos_if_enabled(self):
        if not self.cosmos_stop_on_exit:
            return
        shutdown_url = self.cosmos_url.rsplit('/', 1)[0] + '/shutdown'
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
        self.statusbar.showMessage('Đang xem Kênh {} ({})'.format(channel + 1, self.StreamTyp_comboBox.currentText()))

    def _stop_preview(self):
        if not self._is_playing():
            return
        self.ai_check.setChecked(False)
        self.ai_check.setEnabled(False)
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
