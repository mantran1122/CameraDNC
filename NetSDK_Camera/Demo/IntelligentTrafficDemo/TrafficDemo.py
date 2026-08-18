# coding=utf-8
import sys
from PyQt5.QtWidgets import QMainWindow,QApplication, QTableWidgetItem, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from ctypes import *
import os.path

from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Struct import *
from NetSDK.SDK_Enum import EM_LOGIN_SPAC_CAP_TYPE, EM_EVENT_IVS_TYPE
from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect,fAnalyzerDataCallBack

from Demo.IntelligentTrafficDemo.IntelligentTrafficUI import Ui_MainWindow
from connection_preferences import load_connection


global wnd;
@WINFUNCTYPE(None, C_LLONG, C_DWORD, c_void_p, POINTER(c_ubyte), C_DWORD, C_LDWORD, c_int, c_void_p)
def AnalyzerDataCallBack(lAnalyzerHandle, dwAlarmType, pAlarmInfo, pBuffer, dwBufSize, dwUser, nSequence, reserved):
    print('Enter AnalyzerDataCallBack')
    # 当报警类型是交通卡口事件时在界面上进行显示相关信息
    if(lAnalyzerHandle == wnd.attachID)and(dwAlarmType == EM_EVENT_IVS_TYPE.TRAFFICJUNCTION):
        buf = cast(pAlarmInfo, POINTER(DEV_EVENT_TRAFFICJUNCTION_INFO)).contents
        wnd.update_buf(buf, pBuffer, dwBufSize, nSequence)
        wnd.update_table()


class TrafficWnd(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(TrafficWnd, self).__init__(parent)
        self.setupUi(self)
        # 界面初始化
        self._init_ui()

        # NetSDK用到的相关变量和回调
        self.loginID = C_LLONG()
        self.playID = C_LLONG()
        self.attachID = C_LLONG()
        self.m_DisConnectCallBack = fDisConnect(self.DisConnectCallBack)
        self.m_ReConnectCallBack = fHaveReConnect(self.ReConnectCallBack)

        # 获取NetSDK对象并初始化
        self.sdk = NetClient()
        self.sdk.InitEx(self.m_DisConnectCallBack)
        self.sdk.SetAutoReconnect(self.m_ReConnectCallBack)

    # 初始化界面
    def _init_ui(self):
        self.row = 0
        self.column = 0
        self.Login_pushButton.setEnabled(True)
        self.Play_pushButton.setEnabled(False)
        self.Logout_pushButton.setEnabled(False)
        self.StopPlay_pushButton.setEnabled(False)
        self.Attach_pushButton.setEnabled(False)
        self.Detach_pushButton.setEnabled(False)

        connection = load_connection()
        self.IP_lineEdit.setText(connection['host'])
        self.Port_lineEdit.setText(connection['port'])
        self.User_lineEdit.setText(connection['username'])
        self.Pwd_lineEdit.setText(connection['password'])

        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint)
        self.setFixedSize(self.width(), self.height())

        self.Login_pushButton.clicked.connect(self.login_btn_onclick)
        self.Logout_pushButton.clicked.connect(self.logout_btn_onclick)
        self.Play_pushButton.clicked.connect(self.play_btn_onclick)
        self.StopPlay_pushButton.clicked.connect(self.stop_play_btn_onclick)
        self.Attach_pushButton.clicked.connect(self.attach_btn_onclick)
        self.Detach_pushButton.clicked.connect(self.detach_btn_onclick)

    # 登录设备
    def login_btn_onclick(self):
        self.Attach_tableWidget.setHorizontalHeaderLabels(['Thời gian', 'Sự kiện', 'Biển số xe', 'Màu biển số', 'Loại xe', 'Màu xe'])
        ip = self.IP_lineEdit.text()
        port = int(self.Port_lineEdit.text())
        username = self.User_lineEdit.text()
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
        if self.loginID:
            self.setWindowTitle('Giao thông thông minh - Trực tuyến')
            self.Logout_pushButton.setEnabled(True)
            self.Login_pushButton.setEnabled(False)
            self.Play_pushButton.setEnabled(True)
            self.Attach_pushButton.setEnabled(True)
            for i in range(int(device_info.nChanNum)):
                self.Channel_comboBox.addItem(str(i))
        else:
            QMessageBox.about(self, 'Thông báo', error_msg)

    # 登出设备
    def logout_btn_onclick(self):
        # 停止拉流
        if self.playID:
            self.sdk.StopRealPlayEx(self.playID)
            self.playID = 0
        # 停止订阅
        if self.attachID:
            self.sdk.StopLoadPic(self.attachID)
            self.attachID = 0
        # 登出
        result = self.sdk.Logout(self.loginID)
        self.Login_pushButton.setEnabled(True)
        self.Logout_pushButton.setEnabled(False)
        self.Play_pushButton.setEnabled(False)
        self.StopPlay_pushButton.setEnabled(False)
        self.Attach_pushButton.setEnabled(False)
        self.Detach_pushButton.setEnabled(False)
        self.setWindowTitle("Giao thông thông minh - Ngoại tuyến")
        self.loginID = C_LLONG(0)
        self.Channel_comboBox.clear()
        self.Attach_tableWidget.clear()
        self.Video_label.clear()
        self.GlobalScene_label.clear()
        self.SmallScene_label.clear()
        self.row = 0
        self.column = 0
        self.Attach_tableWidget.setHorizontalHeaderLabels(['Thời gian', 'Sự kiện', 'Biển số xe', 'Màu biển số', 'Loại xe', 'Màu xe'])

    # 开始实施监视
    def play_btn_onclick(self):
        channel = self.Channel_comboBox.currentIndex()
        self.playID = self.sdk.RealPlayEx(self.loginID, channel, self.Video_label.winId())
        if self.playID:
            self.Play_pushButton.setEnabled(False)
            self.StopPlay_pushButton.setEnabled(True)
        else:
            QMessageBox.about(self, 'Thông báo', 'Lỗi: ' + str(self.sdk.GetLastError()))

    # 停止拉流
    def stop_play_btn_onclick(self):
        if self.playID:
        	self.sdk.StopRealPlayEx(self.playID)
        self.Play_pushButton.setEnabled(True)
        self.StopPlay_pushButton.setEnabled(False)
        self.playID = 0
        self.Video_label.repaint()

    # 智能交通卡口事件订阅
    def attach_btn_onclick(self):
        self.GlobalScene_label.clear()
        self.SmallScene_label.clear()
        self.Attach_tableWidget.setHorizontalHeaderLabels(['Thời gian', 'Sự kiện', 'Biển số xe', 'Màu biển số', 'Loại xe', 'Màu xe'])
        channel = self.Channel_comboBox.currentIndex()
        bNeedPicFile = 1
        dwUser = 0
        self.attachID = self.sdk.RealLoadPictureEx(self.loginID, channel, EM_EVENT_IVS_TYPE.TRAFFICJUNCTION, bNeedPicFile, AnalyzerDataCallBack, dwUser, None)
        if not self.attachID:
            QMessageBox.about(self, 'Thông báo', 'Lỗi: ' + str(self.sdk.GetLastError()))
        else:
            self.Attach_pushButton.setEnabled(False)
            self.Detach_pushButton.setEnabled(True)
            QMessageBox.about(self, 'Thông báo', "Đăng ký thành công!")

    # 取消订阅
    def detach_btn_onclick(self):
        self.GlobalScene_label.clear()
        self.SmallScene_label.clear()
        if (self.attachID == 0):
            return
        self.sdk.StopLoadPic(self.attachID)
        self.attachID = 0
        self.Attach_pushButton.setEnabled(True)
        self.Detach_pushButton.setEnabled(False)
        self.Attach_tableWidget.clear()
        self.row = 0
        self.column = 0
        self.Attach_tableWidget.viewport().update()
        self.Attach_tableWidget.setHorizontalHeaderLabels(['Thời gian', 'Sự kiện', 'Biển số xe', 'Màu biển số', 'Loại xe', 'Màu xe'])

    def update_buf(self, buf, pBuffer, dwBufSize, nSequence):
        self.buf = buf
        self.pBuffer = pBuffer
        self.dwBufSize = dwBufSize
        self.nSequence = nSequence

    def update_table(self):
        self.Attach_tableWidget.setRowCount(self.row + 1)
        item1 = QTableWidgetItem('{0}-{1}-{2} {3}:{4}:{5}'.format(str(self.buf.UTC.dwYear), str(self.buf.UTC.dwMonth),
                                                 str(self.buf.UTC.dwDay),
                                                 str(self.buf.UTC.dwHour), str(self.buf.UTC.dwMinute),
                                                 str(self.buf.UTC.dwSecond)))
        self.Attach_tableWidget.setItem(self.row, self.column, item1)
        item2 = QTableWidgetItem('Sự kiện nút giao thông')
        self.Attach_tableWidget.setItem(self.row, self.column + 1, item2)
        item3 = QTableWidgetItem(str(self.buf.stTrafficCar.szPlateNumber.decode('gb2312')))
        self.Attach_tableWidget.setItem(self.row, self.column + 2, item3)
        item4 = QTableWidgetItem(str(self.buf.stTrafficCar.szPlateColor.decode()))
        self.Attach_tableWidget.setItem(self.row, self.column + 3, item4)
        item5 = QTableWidgetItem(str(self.buf.stuVehicle.szObjectSubType.decode()))
        self.Attach_tableWidget.setItem(self.row, self.column + 4, item5)
        item6 = QTableWidgetItem(str(self.buf.stTrafficCar.szVehicleColor.decode()))
        self.Attach_tableWidget.setItem(self.row, self.column + 5, item6)
        self.GlobalScene_label.clear()
        self.SmallScene_label.clear()
        if self.buf.stuObject.bPicEnble:
            GlobalScene_buf = cast(self.pBuffer, POINTER(c_ubyte*self.buf.stuObject.stPicInfo.dwOffSet)).contents
            with open('./GlobalScene_buf.jpg', 'wb+') as big_pic:
                big_pic.write(GlobalScene_buf)
            image = QPixmap('./GlobalScene_buf.jpg').scaled(self.GlobalScene_label.width(), self.GlobalScene_label.height())
            self.GlobalScene_label.setPixmap(image)
            if (self.buf.stuObject.stPicInfo.dwFileLenth > 0):
                small_buf = self.pBuffer[self.buf.stuObject.stPicInfo.dwOffSet:self.buf.stuObject.stPicInfo.dwOffSet + self.buf.stuObject.stPicInfo.dwFileLenth]
                with open('./small_pic.jpg', 'wb+') as small_pic:
                    small_pic.write(bytes(small_buf))
                image1 = QPixmap('./small_pic.jpg').scaled(self.SmallScene_label.width(),
                                                            self.SmallScene_label.height())
                self.SmallScene_label.setPixmap(image1)
        else:
            GlobalScene_buf = cast(self.pBuffer, POINTER(c_ubyte * self.dwBufSize)).contents
            with open('./GlobalScene_buf.jpg', 'wb+') as big_pic:
                big_pic.write(GlobalScene_buf)
            image = QPixmap('./GlobalScene_buf.jpg').scaled(self.GlobalScene_label.width(),
                                                            self.GlobalScene_label.height())
            self.GlobalScene_label.setPixmap(image)
        self.row += 1
        # 刷新table
        self.Attach_tableWidget.update()
        self.Attach_tableWidget.viewport().update()

    # 实现断线回调函数功能
    def DisConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle("Giao thông thông minh - Ngoại tuyến")

    # 实现断线重连回调函数功能
    def ReConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle('Giao thông thông minh - Trực tuyến')

    # 关闭主窗口时清理资源
    def closeEvent(self, event):
        event.accept()
        if self.attachID:
            self.sdk.StopLoadPic(self.attachID)
            self.attachID = 0
        if self.playID:
            self.sdk.StopRealPlayEx(self.playID)
            self.playID = 0
        if self.loginID:
            self.sdk.Logout(self.loginID)
            self.loginID = 0
        self.sdk.Cleanup()
        self.Video_label.repaint()
        self.Attach_tableWidget.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    my_wnd = TrafficWnd()
    wnd = my_wnd
    my_wnd.show()
    sys.exit(app.exec_())
