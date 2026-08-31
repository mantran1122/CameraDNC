# coding=utf-8
import os
import sys

from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import Qt, QDateTime
from ctypes import *

from Demo.DeviceControlDemo.DeviceControlUI import Ui_MainWindow
from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect
from NetSDK.SDK_Enum import EM_DEV_CFG_TYPE, EM_LOGIN_SPAC_CAP_TYPE
from NetSDK.SDK_Struct import LOG_SET_PRINT_INFO, NET_TIME, C_LDWORD, C_LLONG, NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY, NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY
from connection_preferences import load_connection

import tempfile

file = os.path.join(tempfile.gettempdir(), "dnc_dahua_sdk.log")
@WINFUNCTYPE(c_int, c_char_p, c_uint, C_LDWORD)
def SDKLogCallBack(szLogBuffer, nLogSize, dwUser):
    try:
        with open(file, 'a', encoding='utf-8', errors='replace') as f:
            f.write(szLogBuffer.decode('utf-8', 'replace'))
    except Exception as e:
        print(e)
    return 1

class MyMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MyMainWindow, self).__init__(parent)
        self.setupUi(self)

        # 界面初始化
        self._init_ui()

        # NetSDK用到的相关变量和回调
        self.loginID = C_LLONG()
        self.m_DisConnectCallBack = fDisConnect(self.DisConnectCallBack)
        self.m_ReConnectCallBack = fHaveReConnect(self.ReConnectCallBack)

        # 获取NetSDK对象并初始化
        self.sdk = NetClient()
        self.sdk.InitEx(self.m_DisConnectCallBack)
        self.sdk.SetAutoReconnect(self.m_ReConnectCallBack)

    # 初始化界面
    def _init_ui(self):
        self.Login_pushButton.setText('Đăng nhập')

        connection = load_connection()
        self.IP_lineEdit.setText(connection['host'])
        self.Port_lineEdit.setText(connection['port'])
        self.Name_lineEdit.setText(connection['username'])
        self.Pwd_lineEdit.setText(connection['password'])

        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint)
        self.setFixedSize(self.width(), self.height())

        self.Login_pushButton.clicked.connect(self.login_btn_onclick)
        self.OpenLog_pushButton.clicked.connect(self.openlog_btn_onclick)
        self.CloseLog_pushButton.clicked.connect(self.closelog_btn_onclick)
        self.GetTime_pushButton.clicked.connect(self.gettime_btn_onclick)
        self.SetTime_pushButton.clicked.connect(self.settime_btn_onclick)
        self.Restart_pushButton.clicked.connect(self.restart_btn_onclick)

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
                self.setWindowTitle('Điều khiển thiết bị - Trực tuyến')
                self.Login_pushButton.setText('Đăng xuất')
            else:
                QMessageBox.about(self, 'Thông báo', error_msg)
        else:
            result = self.sdk.Logout(self.loginID)
            if result:
                self.setWindowTitle("Điều khiển thiết bị - Ngoại tuyến")
                self.Login_pushButton.setText("Đăng nhập")
                self.loginID = 0

    def openlog_btn_onclick(self):
        log_info = LOG_SET_PRINT_INFO()
        log_info.dwSize = sizeof(LOG_SET_PRINT_INFO)
        log_info.bSetFilePath = 1
        log_info.szLogFilePath = os.path.join(os.getcwd(), 'sdk_log.log').encode('gbk')
        log_info.cbSDKLogCallBack = SDKLogCallBack
        result = self.sdk.LogOpen(log_info)
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())

    def closelog_btn_onclick(self):
        result = self.sdk.LogClose()
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())

    def gettime_btn_onclick(self):
        time = NET_TIME()
        result = self.sdk.GetDevConfig(self.loginID, int(EM_DEV_CFG_TYPE.TIMECFG), -1, time, sizeof(NET_TIME))
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
        else:
            get_time = QDateTime(time.dwYear, time.dwMonth, time.dwDay, time.dwHour, time.dwMinute, time.dwSecond)
            self.Time_dateTimeEdit.setDateTime(get_time)

    def settime_btn_onclick(self):
        device_date = self.Time_dateTimeEdit.date()
        device_time = self.Time_dateTimeEdit.time()
        deviceDateTime = NET_TIME()
        deviceDateTime.dwYear = device_date.year()
        deviceDateTime.dwMonth = device_date.month()
        deviceDateTime.dwDay = device_date.day()
        deviceDateTime.dwHour = device_time.hour()
        deviceDateTime.dwMinute = device_time.minute()
        deviceDateTime.dwSecond = device_time.second()

        result = self.sdk.SetDevConfig(self.loginID, int(EM_DEV_CFG_TYPE.TIMECFG), -1,
                                       deviceDateTime, sizeof(NET_TIME))
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())

    def restart_btn_onclick(self):
        result = self.sdk.RebootDev(self.loginID)
        if not result:
            QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
        else:
            QMessageBox.about(self, 'Thông báo', 'Khởi động lại thành công!')

    # 实现断线回调函数功能
    def DisConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle("Điều khiển thiết bị - Ngoại tuyến")

    # 实现断线重连回调函数功能
    def ReConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle('Điều khiển thiết bị - Trực tuyến')

    # 关闭主窗口时清理资源
    def closeEvent(self, event):
        event.accept()
        if self.loginID:
            self.sdk.Logout(self.loginID)
        self.sdk.Cleanup()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    my_wnd = MyMainWindow()
    wnd = my_wnd
    my_wnd.show()
    sys.exit(app.exec_())
