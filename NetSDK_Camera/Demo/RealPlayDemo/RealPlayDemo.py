# coding=utf-8
"""Dahua connection and live-preview MVP."""
import os
import sys
import json
import threading
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
from ctypes import POINTER, c_ubyte, cast, sizeof

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import QApplication, QCheckBox, QLabel, QMainWindow, QMessageBox

from Demo.RealPlayDemo.RealPlayUI import Ui_MainWindow
from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect, fSnapRev
from NetSDK.SDK_Enum import SDK_RealPlayType, EM_LOGIN_SPAC_CAP_TYPE
from NetSDK.SDK_Struct import C_LLONG, SNAP_PARAMS, NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY, NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY
from connection_preferences import clear_connection, load_connection, save_connection


def _positive_float_from_env(name, default):
    try:
        return max(float(os.getenv(name, str(default))), 1.0)
    except ValueError:
        return float(default)


class MyMainWindow(QMainWindow, Ui_MainWindow):
    """Connect to one Dahua recorder and render a selected channel."""

    connection_changed = pyqtSignal(bool)
    cosmos_result = pyqtSignal(str)
    cosmos_status = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
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
        self.cosmos_url = os.getenv('COSMOS_LIVE_URL', 'http://127.0.0.1:8765/analyze')
        self.cosmos_interval_seconds = _positive_float_from_env('COSMOS_SAMPLE_INTERVAL_SECONDS', 10)
        self.cosmos_stop_on_exit = os.getenv('COSMOS_STOP_ON_EXIT', '').strip().lower() in {'1', 'true', 'yes'}
        self._init_ui()

    def _init_ui(self):
        self.login_btn.setText('Đăng nhập')
        self.play_btn.setText('Bắt đầu xem')
        self.play_btn.setEnabled(False)
        # Credentials are saved only with the explicit checkbox consent below.
        # Environment variables remain useful deployment defaults.
        connection = load_connection()
        self.IP_lineEdit.setText(connection['host'])
        self.Port_lineEdit.setText(connection['port'])
        self.Name_lineEdit.setText(connection['username'])
        self.Pwd_lineEdit.setText(connection['password'])
        self.Port_lineEdit.setValidator(QIntValidator(1, 65535, self))
        self.remember_check = QCheckBox('Lưu thông tin đăng nhập trên máy này', self.centralwidget)
        self.remember_check.setGeometry(10, 445, 260, 24)
        self.remember_check.setChecked(connection['remember'])
        self.remember_check.toggled.connect(self._on_remember_toggled)
        self.ai_check = QCheckBox('Phân tích Cosmos (mỗi {} giây)'.format(int(self.cosmos_interval_seconds)), self.centralwidget)
        self.ai_check.setGeometry(270, 445, 220, 24)
        self.ai_check.setEnabled(False)
        self.ai_check.toggled.connect(self._on_ai_toggled)
        self.cosmos_label = QLabel('Cosmos: đã tắt', self.centralwidget)
        self.cosmos_label.setGeometry(10, 515, 480, 20)
        # Make room for the consent control in the generated demo UI.
        self.StreamTyp_comboBox.move(90, 485)
        self.label_5.move(10, 485)
        self.play_btn.move(260, 478)
        self.resize(self.width(), 560)
        self.statusbar.showMessage('Chưa kết nối đầu ghi')
        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint)
        self.setFixedSize(self.width(), self.height())
        self.login_btn.clicked.connect(self.login_btn_onclick)
        self.play_btn.clicked.connect(self.play_btn_onclick)
        self.sample_timer = QTimer(self)
        self.sample_timer.setInterval(int(self.cosmos_interval_seconds * 1000))
        self.sample_timer.timeout.connect(self._request_snapshot)

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
        threading.Thread(target=self._send_to_cosmos, args=(image_bytes,), daemon=True).start()

    def _send_to_cosmos(self, image_bytes):
        try:
            req = urlrequest.Request(self.cosmos_url, data=image_bytes,
                                     headers={'Content-Type': 'application/octet-stream'}, method='POST')
            # First inference can include CUDA graph warm-up and take longer
            # than a normal frame.  Do not abandon it after 15 seconds: an
            # abandoned request keeps the service busy and causes 429s for
            # subsequent snapshots.
            timeout_seconds = float(os.getenv('COSMOS_TIMEOUT_SECONDS', '90'))
            with urlrequest.urlopen(req, timeout=timeout_seconds) as response:
                payload = json.loads(response.read().decode('utf-8'))
            result = payload.get('result', {})
            self.cosmos_result.emit('{} | {} | {} ms'.format(
                result.get('risk_level', 'none').upper(), result.get('summary', 'Không có mô tả'),
                payload.get('inference_ms', '?')))
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

    def _show_cosmos_result(self, text):
        self.cosmos_label.setText('Cosmos: ' + text)

    def _show_cosmos_status(self, text):
        self.cosmos_label.setText(text)

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
            self.statusbar.showMessage('Đã kết nối đầu ghi')
        else:
            self.setWindowTitle('Xem trực tiếp - Mất kết nối')
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
