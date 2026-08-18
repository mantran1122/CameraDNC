# coding=utf-8
import sys
import time
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QTableWidgetItem, QDialog
from Demo.SearchDeviceDemo.SearchDeviceUI import Ui_MainWindow
from Demo.SearchDeviceDemo.InitDevAccountUI import Ui_InitDevAccount

from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Enum import *
from NetSDK.SDK_Struct import *
from NetSDK.SDK_Callback import fSearchDevicesCBEx, fSearchDevicesCB
from ctypes import *

import socket
import struct


global wnd
@WINFUNCTYPE(None, C_LLONG, POINTER(DEVICE_NET_INFO_EX2), c_void_p)
def search_device_callback(lSearchHandle, pDevNetInfo, pUserData):

    try:
        buf = cast(pDevNetInfo, POINTER(DEVICE_NET_INFO_EX2)).contents
        wnd.update_buf(lSearchHandle,buf)
        wnd.update_table()
        print("Enter in search_device_callback")
    except Exception as e:
        print(e)

@WINFUNCTYPE(None, POINTER(DEVICE_NET_INFO_EX), c_void_p)
def search_devie_byIp_callback(pDevNetInfo, pUserData):
    try:
        buf = cast(pDevNetInfo, POINTER(DEVICE_NET_INFO_EX2)).contents
        wnd.update_buf(0, buf)
        wnd.update_table()
        print("Enter in search_devie_byIp_callback")
    except Exception as e:
        print(e)

class MyMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MyMainWindow, self).__init__(parent)
        self.setupUi(self)
        self.init_ui()
        self.sdk = NetClient()
        self.sdk.InitEx(None, 0)



    # 初始化界面
    def init_ui(self):
        self.row = 0
        self.column = 0
        self.device_info_list = []
        self.device_mac_list = []
        self.localIP_SearchHandle_dict = {}
        self.localIP = None
        self.lSearchHandle_list = []
        self.SearchDeviceButton.setEnabled(True)
    # 获取多网卡ip
    def getIPAddrs(self):
        ip_list = socket.gethostbyname_ex(socket.gethostname())
        for ips in ip_list:
            if type(ips) == list and len(ips) != 0:
                IPlist = ips
        del ip_list
        return IPlist

    # 组播和广播搜索
    def start_search_device(self):
        # 获取本地IP，考虑到多网卡的情况下搜索
        # 有几张网卡，就得调用几次搜索接口
        hostname = socket.gethostname()
        localIp = socket.gethostbyname_ex(hostname)
        IPList = self.getIPAddrs()
        for i in range(IPList.__len__()):
            startsearch_in = NET_IN_STARTSERACH_DEVICE()
            startsearch_in.dwSize = sizeof(NET_IN_STARTSERACH_DEVICE)
            startsearch_in.emSendType = EM_SEND_SEARCH_TYPE.MULTICAST_AND_BROADCAST
            startsearch_in.cbSearchDevices = search_device_callback
            startsearch_in.szLocalIp = IPList[i].encode()
            startsearch_out = NET_OUT_STARTSERACH_DEVICE()
            startsearch_out.dwSize = sizeof(NET_OUT_STARTSERACH_DEVICE)
            lSearchHandle = self.sdk.StartSearchDevicesEx(startsearch_in, startsearch_out)
            if lSearchHandle != 0:
                self.localIP_SearchHandle_dict[lSearchHandle] = startsearch_in.szLocalIp
                self.lSearchHandle_list.append(lSearchHandle)
        if(IPList.__len__() > 0):
            del IPList
        if(self.localIP_SearchHandle_dict.__len__() > 0):
            return True
        else:
            return False

    # 单播搜索
    def start_search_device_byIP(self, start_IP, end_IP): #这里要注意每个ip的有效性
        self.localIP = None
        startsearchbyIp_in = DEVICE_IP_SEARCH_INFO()
        startsearchbyIp_in.dwSize = sizeof(DEVICE_IP_SEARCH_INFO)
        start = struct.unpack("!I", socket.inet_aton(start_IP))[0]  # 网络序转字节序
        end = struct.unpack("!I", socket.inet_aton(end_IP))[0]
        if (end - start > 255):
            QMessageBox.about(self, 'Thông báo', "Số lượng IP vượt quá giới hạn tối đa 256.")
            return False

        startsearchbyIp_in.nIpNum = end - start + 1

        for i in range(startsearchbyIp_in.nIpNum):
            ip = DEVICE_IP_SEARCH_INFO_IP()
            ip.IP = socket.inet_ntoa(struct.pack("!I", start + i)).encode()
            startsearchbyIp_in.szIP[i] = ip

        wait_time = int(wnd.Searchtime_lineEdit.text())
        result = self.sdk.SearchDevicesByIPs(startsearchbyIp_in, search_devie_byIp_callback, 0, None, wait_time)
        if not result:
            QMessageBox.about(self, 'Thông báo', "Tìm kiếm thiết bị thất bại.")
            return False
        return True

    # 停止搜索,配合start_search_device使用
    def stop_search_device(self):
        for i in range(self.lSearchHandle_list.__len__()):
            result = self.sdk.StopSearchDevices(self.lSearchHandle_list[i])
        self.lSearchHandle_list.clear()
        self.localIP_SearchHandle_dict.clear()
        self.row = 0
        self.column = 0
        self.device_info_list.clear()
        self.device_mac_list.clear()
        self.tableWidget.clear()
        self.tableWidget.setHorizontalHeaderLabels(['STT', 'Trạng thái', 'Phiên bản IP', 'Địa chỉ IP', 'Cổng', 'Subnet Mask', 'Gateway', 'Địa chỉ MAC', 'Loại thiết bị', 'Loại chi tiết', 'Http'])
        return

    # 检查是否输入正确的ip地址
    def check_ip(self, ipaddr):
        addr = ipaddr.split('.')  # 切割IP地址为一个列表
        if len(addr) != 4:  # 切割后列表必须有4个参数
            return False

        for i in range(4):
            try:
                addr[i] = int(addr[i])  # 每个参数必须为数字，否则校验失败
            except:
                return False

            if addr[i] <= 255 and addr[i] >= 0:  # 每个参数值必须在0-255之间
                pass
            else:
                return False
        return True

    # 初始化账号
    def init_device_accout(self, device_info:list):
        child = QDialog()
        child_ui = Ui_InitDevAccount()
        child_ui.setupUi(child)
        if (1 == (device_info[3] & 1)):
            # 手机
            child_ui.way_lineEdit.setText('Điện thoại')
        elif (1 == (device_info[3] >> 1 & 1)):
            # 邮箱
            child_ui.way_lineEdit.setText('Email')
        value = child.exec()
        if (value == 0):
            return False
        init_Account_In = NET_IN_INIT_DEVICE_ACCOUNT()
        init_Account_In.dwSize = sizeof(init_Account_In)
        init_Account_In.szMac = device_info[2]
        username = child_ui.username_lineEdit.text()
        password = child_ui.password_lineEdit.text()
        confirm_password = child_ui.confirm_password_lineEdit.text()
        if(password != confirm_password):
            QMessageBox.about(self, 'Thông báo', "Xác nhận mật khẩu không khớp, vui lòng nhập lại.")
            return
        init_Account_In.szUserName = username.encode()
        init_Account_In.szPwd = password.encode()
        init_Account_In.szCellPhone = child_ui.reset_way_lineEdit.text().encode()
        if (1 == (device_info[3] & 1)):
            # 手机
            init_Account_In.szCellPhone = child_ui.reset_way_lineEdit.text().encode()
        elif(1 == (device_info[3] >> 1 & 1)):
            # 邮箱
            init_Account_In.szMail = child_ui.reset_way_lineEdit.text().encode()
        init_Account_In.byPwdResetWay = device_info[3]
        init_Account_Out = NET_OUT_INIT_DEVICE_ACCOUNT()
        init_Account_Out.dwSize = sizeof(init_Account_Out)

        result = self.sdk.InitDevAccount(init_Account_In, init_Account_Out, 5000, self.localIP)
        if result:
            return True
        else:
            QMessageBox.about(self, 'Thông báo', 'Lỗi: ' + str(self.sdk.GetLastError()))
            return False



    def search_Device_Btn(self):
        self.localIP = None
        self.stop_search_device()
        result = self.start_search_device()
        if result == False:
            QMessageBox.about(self, 'Thông báo', "Không thể bắt đầu tìm kiếm thiết bị.")
            pass

    def search_Device_ByIp_Btn(self):
        self.localIP = None
        self.stop_search_device()
        self.tableWidget.setHorizontalHeaderLabels(['STT', 'Trạng thái', 'Phiên bản IP', 'Địa chỉ IP', 'Cổng', 'Subnet Mask', 'Gateway', 'Địa chỉ MAC', 'Loại thiết bị', 'Loại chi tiết', 'Http'])
        start_IP = self.StartIP_lineEdit.text()
        end_IP = self.EndIP_lineEdit.text()
        if(start_IP != '') and (end_IP != ''):
            if (self.check_ip(start_IP) == True)and (self.check_ip(end_IP)== True):
                result = self.start_search_device_byIP(start_IP, end_IP)
            else:
                QMessageBox.about(self, 'Thông báo', "Địa chỉ IP không hợp lệ.")
                pass
        else:
            QMessageBox.about(self, 'Thông báo', "IP không được để trống.")
            pass

    def Init_Btn(self):
        # 获取选中行的ip和初始化信息
        currentRow = self.tableWidget.currentRow()
        if((len(self.device_info_list) ==0)or((self.device_info_list[currentRow][0]&3) != 1)):
            QMessageBox.about(self, 'Thông báo', "Vui lòng chọn thiết bị chưa khởi tạo.")
        else:
            result = self.init_device_accout(self.device_info_list[currentRow])
            if result == True:
                QMessageBox.about(self, 'Thông báo', "Khởi tạo thiết bị thành công!")
                item = QTableWidgetItem("Đã khởi tạo")
                self.device_info_list[currentRow][0] = 2
                self.tableWidget.setItem(currentRow, 1, item)
                self.tableWidget.update()
                self.tableWidget.viewport().update()



    def update_buf(self, lSearchHandle, buf):
        self.buf = buf
        if(lSearchHandle != 0):
            self.localIP = self.localIP_SearchHandle_dict[lSearchHandle]
        pass

    def update_table(self):
            #将重复的设备进行过滤
            if self.buf.stuDevInfo.szMac in self.device_mac_list:
                return
            if self.buf.stuDevInfo.iIPVersion != 4:
                return
            self.device_mac_list.append(self.buf.stuDevInfo.szMac)
            self.device_info_list.append(list((self.buf.stuDevInfo.byInitStatus, self.buf.stuDevInfo.szIP, self.buf.stuDevInfo.szMac, self.buf.stuDevInfo.byPwdResetWay)))
            self.tableWidget.setRowCount(self.row + 1)
            item = QTableWidgetItem(str(self.row + 1))
            self.tableWidget.setItem(self.row, self.column, item)
            if ((self.buf.stuDevInfo.byInitStatus & 3) == 1):
                item1 = QTableWidgetItem("Chưa khởi tạo")
                self.tableWidget.setItem(self.row, self.column + 1, item1)
            else:
                item1 = QTableWidgetItem("Đã khởi tạo")
                self.tableWidget.setItem(self.row, self.column + 1, item1)
            item2 = QTableWidgetItem(str(self.buf.stuDevInfo.iIPVersion))
            self.tableWidget.setItem(self.row, self.column + 2, item2)
            item3 = QTableWidgetItem(str(self.buf.stuDevInfo.szIP.decode()))
            self.tableWidget.setItem(self.row, self.column + 3, item3)
            item4 = QTableWidgetItem(str(self.buf.stuDevInfo.nPort))
            self.tableWidget.setItem(self.row, self.column + 4, item4)
            item5 = QTableWidgetItem(str(self.buf.stuDevInfo.szSubmask.decode()))
            self.tableWidget.setItem(self.row, self.column + 5, item5)
            item6 = QTableWidgetItem(str(self.buf.stuDevInfo.szGateway.decode()))
            self.tableWidget.setItem(self.row, self.column + 6, item6)
            item7 = QTableWidgetItem(str(self.buf.stuDevInfo.szMac.decode()))
            self.tableWidget.setItem(self.row, self.column + 7, item7)
            item8 = QTableWidgetItem(str(self.buf.stuDevInfo.szDeviceType.decode()))
            self.tableWidget.setItem(self.row, self.column + 8, item8)
            item9 = QTableWidgetItem(str(self.buf.stuDevInfo.szDetailType.decode()))
            self.tableWidget.setItem(self.row, self.column + 9, item9)
            item10 = QTableWidgetItem(str(self.buf.stuDevInfo.nHttpPort))
            self.tableWidget.setItem(self.row, self.column + 10, item10)
            self.row += 1
            # 刷新table
            self.tableWidget.update()
            self.tableWidget.viewport().update()



    # 关闭主窗口时清理资源
    def closeEvent(self, event):
        event.accept()
        print('exit')
        self.stop_search_device()
        self.sdk.Cleanup()
        del self.lSearchHandle_list
        del self.localIP_SearchHandle_dict
        del self.device_info_list
        del self.device_mac_list


if __name__ == '__main__':
    app = QApplication(sys.argv)
    my_wnd = MyMainWindow()
    wnd = my_wnd
    my_wnd.show()
    sys.exit(app.exec_())

