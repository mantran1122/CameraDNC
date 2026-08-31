from PyQt5.QtWidgets import QMainWindow, QMessageBox, QHeaderView, QAbstractItemView, QApplication, QGroupBox, QMenu,QTableWidgetItem
from PyQt5.QtCore import Qt
import sys
import types
from Demo.AlarmListen.AlarmListenUI import Ui_MainWindow

from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Struct import *
from NetSDK.SDK_Enum import *
from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect,fMessCallBackEx1
from connection_preferences import load_connection

from PyQt5.QtCore import Qt, pyqtSignal

hwnd = None

@WINFUNCTYPE(None, c_long, C_LLONG, POINTER(c_char), C_DWORD, POINTER(c_char), c_long, c_int, c_long, C_LDWORD)
def MessCallback(lCommand, lLoginID, pBuf, dwBufLen, pchDVRIP, nDVRPort, bAlarmAckFlag, nEventID, dwUser):
    if hwnd is None or lLoginID != getattr(hwnd.loginID, 'value', hwnd.loginID):
        return
    if lCommand == SDK_ALARM_TYPE.EVENT_MOTIONDETECT and pBuf:
        try:
            buf = cast(pBuf, POINTER(ALARM_MOTIONDETECT_INFO)).contents
            data = {
                'year': int(buf.UTC.dwYear), 'month': int(buf.UTC.dwMonth), 'day': int(buf.UTC.dwDay),
                'hour': int(buf.UTC.dwHour), 'minute': int(buf.UTC.dwMinute), 'second': int(buf.UTC.dwSecond),
                'channel': int(buf.nChannelID),
                'action': int(buf.nEventAction),
            }
            hwnd.alarm_signal.emit(data)
        except Exception as exc:
            print(f"MessCallback error: {exc}")

class StartListenWnd(QMainWindow, Ui_MainWindow):
    alarm_signal = pyqtSignal(dict)

    def __init__(self):
        global hwnd
        super(StartListenWnd, self).__init__()
        hwnd = self
        self.setupUi(self)
        self.alarm_signal.connect(self._on_alarm_received)
        # 界面初始化
        self.init_ui()

        # NetSDK用到的相关变量和回调
        self.loginID = C_LLONG()
        self.m_DisConnectCallBack = fDisConnect(self.DisConnectCallBack)
        self.m_ReConnectCallBack = fHaveReConnect(self.ReConnectCallBack)

        # 获取NetSDK对象并初始化
        self.sdk = NetClient()
        self.sdk.InitEx(self.m_DisConnectCallBack)
        self.sdk.SetAutoReconnect(self.m_ReConnectCallBack)

        # 设置报警回调函数
        self.sdk.SetDVRMessCallBackEx1(MessCallback, 0)


    def init_ui(self):
        connection = load_connection()
        self.IP_lineEdit.setText(connection['host'])
        self.Port_lineEdit.setText(connection['port'])
        self.Username_lineEdit.setText(connection['username'])
        self.Password_lineEdit.setText(connection['password'])
        self.Login_pushButton.clicked.connect(self.login_btn_onclick)
        self.Logout_pushButton.clicked.connect(self.logout_btn_onclick)

        self.Alarmlisten_pushButton.clicked.connect(self.attach_btn_onclick)
        self.Stopalarmlisten_pushButton.clicked.connect(self.detach_btn_onclick)
        self.Login_pushButton.setEnabled(True)
        self.Logout_pushButton.setEnabled(False)
        self.Alarmlisten_pushButton.setEnabled(False)
        self.Stopalarmlisten_pushButton.setEnabled(False)
        self.row = 0
        self.column = 0

    def login_btn_onclick(self):
        self.Alarmlisten_tableWidget.setHorizontalHeaderLabels(['STT', 'Thời gian', 'Kênh', 'Loại cảnh báo', 'Trạng thái'])
        ip = self.IP_lineEdit.text()
        port = int(self.Port_lineEdit.text())
        username = self.Username_lineEdit.text()
        password = self.Password_lineEdit.text()
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
            self.setWindowTitle('Nghe cảnh báo - Trực tuyến')
            self.Login_pushButton.setEnabled(False)
            self.Logout_pushButton.setEnabled(True)
            if (int(device_info.nChanNum) > 0):
                self.Alarmlisten_pushButton.setEnabled(True)
        else:
            QMessageBox.about(self, 'Thông báo', error_msg)

    def logout_btn_onclick(self):
        # 登出
        if (self.loginID == 0):
            return
        # 停止报警监听
        self.sdk.StopListen(self.loginID)
        #登出
        result = self.sdk.Logout(self.loginID)
        self.Login_pushButton.setEnabled(True)
        self.Logout_pushButton.setEnabled(False)
        self.Alarmlisten_pushButton.setEnabled(False)
        self.Stopalarmlisten_pushButton.setEnabled(False)
        self.setWindowTitle("Nghe cảnh báo - Ngoại tuyến")
        self.loginID = 0
        self.row = 0
        self.column = 0
        self.Alarmlisten_tableWidget.clear()
        self.Alarmlisten_tableWidget.setHorizontalHeaderLabels(['STT', 'Thời gian', 'Kênh', 'Loại cảnh báo', 'Trạng thái'])

    def attach_btn_onclick(self):
        self.row = 0
        self.column = 0
        self.Alarmlisten_tableWidget.clear()
        self.Alarmlisten_tableWidget.setHorizontalHeaderLabels(['STT', 'Thời gian', 'Kênh', 'Loại cảnh báo', 'Trạng thái'])
        result = self.sdk.StartListenEx(self.loginID)
        if result:
            QMessageBox.about(self, 'Thông báo', "Đăng ký cảnh báo thành công!")
            self.Stopalarmlisten_pushButton.setEnabled(True)
            self.Alarmlisten_pushButton.setEnabled(False)
        else:
            QMessageBox.about(self, 'Thông báo', 'Lỗi: ' + str(self.sdk.GetLastError()))

    def detach_btn_onclick(self):
        if (self.loginID > 0):
            self.sdk.StopListen(self.loginID)
        self.Stopalarmlisten_pushButton.setEnabled(False)
        self.Alarmlisten_pushButton.setEnabled(True)

    # 关闭主窗口时清理资源
    def closeEvent(self, event):
        event.accept()
        if self.loginID:
            self.sdk.StopListen(self.loginID)
            self.sdk.Logout(self.loginID)
            self.loginID = 0
        self.sdk.Cleanup()

    def _on_alarm_received(self, data: dict):
        action_map = {0: 'Xung', 1: 'Bắt đầu', 2: 'Kết thúc'}
        action_text = action_map.get(data.get('action', 0), 'Không rõ')
        time_str = f"{data.get('year')}-{data.get('month'):02d}-{data.get('day'):02d} {data.get('hour'):02d}:{data.get('minute'):02d}:{data.get('second'):02d}"

        row = self.Alarmlisten_tableWidget.rowCount()
        self.Alarmlisten_tableWidget.setRowCount(row + 1)
        self.Alarmlisten_tableWidget.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.Alarmlisten_tableWidget.setItem(row, 1, QTableWidgetItem(time_str))
        self.Alarmlisten_tableWidget.setItem(row, 2, QTableWidgetItem(str(data.get('channel', 0))))
        self.Alarmlisten_tableWidget.setItem(row, 3, QTableWidgetItem('Phát hiện chuyển động'))
        self.Alarmlisten_tableWidget.setItem(row, 4, QTableWidgetItem(action_text))
        self.Alarmlisten_tableWidget.scrollToBottom()

    def update_buf(self, buf):
        pass

    def update_ui(self):
        pass

    # 实现断线回调函数功能
    def DisConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle("Nghe cảnh báo - Ngoại tuyến")

    # 实现断线重连回调函数功能
    def ReConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle('Nghe cảnh báo - Trực tuyến')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    wnd = StartListenWnd()
    hwnd = wnd
    wnd.show()
    sys.exit(app.exec_())
