# coding=utf-8
import os
import sys

from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import Qt

from Demo.FaceRecognitionDemo.FaceRecognitionUI import Ui_MainWindow
from NetSDK.NetSDK import NetClient
from NetSDK.SDK_Callback import fDisConnect, fHaveReConnect
from NetSDK.SDK_Enum import *
from NetSDK.SDK_Struct import *
from connection_preferences import load_connection

global wnd

@WINFUNCTYPE(None, C_LLONG, C_DWORD, c_void_p, POINTER(c_ubyte), C_DWORD, C_LDWORD, c_int, c_void_p)
def AnalyzerDataCallBack(lAnalyzerHandle, dwAlarmType, pAlarmInfo, pBuffer, dwBufSize, dwUser, nSequence, reserved):
    if lAnalyzerHandle == wnd.realloadID:
        if dwAlarmType == EM_EVENT_IVS_TYPE.FACERECOGNITION:
            alarm_info = cast(pAlarmInfo, POINTER(DEV_EVENT_FACERECOGNITION_INFO)).contents
            wnd.show_recognition_info(alarm_info, pBuffer, dwBufSize)
            return
        if dwAlarmType == EM_EVENT_IVS_TYPE.FACEDETECT:
            alarm_info = cast(pAlarmInfo, POINTER(DEV_EVENT_FACEDETECT_INFO)).contents
            wnd.show_detect_info(alarm_info, pBuffer, dwBufSize)
            return

class MyMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        global wnd
        super(MyMainWindow, self).__init__(parent)
        wnd = self
        self.setupUi(self)

        # 界面初始化
        self._init_ui()

        # NetSDK用到的相关变量和回调
        self.loginID = C_LLONG()
        self.playID = C_LLONG()
        self.realloadID = C_LLONG()
        self.m_AnalyzerDataCallBack = AnalyzerDataCallBack
        self.detect_object_id = 0
        self.m_DisConnectCallBack = fDisConnect(self.DisConnectCallBack)
        self.m_ReConnectCallBack = fHaveReConnect(self.ReConnectCallBack)

        # 获取NetSDK对象并初始化
        self.sdk = NetClient()
        self.sdk.InitEx(self.m_DisConnectCallBack)
        self.sdk.SetAutoReconnect(self.m_ReConnectCallBack)

    # 初始化界面
    def _init_ui(self):
        self.Login_pushButton.setText('Đăng nhập')
        self.Play_pushButton.setText('Xem')
        self.Play_pushButton.setEnabled(False)

        connection = load_connection()
        self.IP_lineEdit.setText(connection['host'])
        self.Port_lineEdit.setText(connection['port'])
        self.Name_lineEdit.setText(connection['username'])
        self.Pwd_lineEdit.setText(connection['password'])

        self.setWindowFlag(Qt.WindowMinimizeButtonHint)
        self.setWindowFlag(Qt.WindowCloseButtonHint)
        self.setFixedSize(self.width(), self.height())

        self.Login_pushButton.clicked.connect(self.login_btn_onclick)
        self.Play_pushButton.clicked.connect(self.play_btn_onclick)
        self.ListenEvent_pushButton.clicked.connect(self.listenevent_btn_onclick)

        self.clear_img_ui()

    def login_btn_onclick(self):
        self.Play_pushButton.setText("Xem")
        self.ListenEvent_pushButton.setText("Đăng ký sự kiện")

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
                self.setWindowTitle('Nhận diện khuôn mặt - Trực tuyến')
                self.Login_pushButton.setText('Đăng xuất')
                self.Play_pushButton.setEnabled(True)
                self.ListenEvent_pushButton.setEnabled(True)
                for i in range(int(device_info.nChanNum)):
                    self.Channel_comboBox.addItem(str(i))
            else:
                QMessageBox.about(self, 'Thông báo', error_msg)
        else:
            if self.playID:
                self.sdk.StopRealPlayEx(self.playID)
                self.playID = 0
            if self.realloadID:
                self.sdk.StopLoadPic(self.realloadID)
                self.realloadID = 0
            result = self.sdk.Logout(self.loginID)
            if result:
                self.setWindowTitle("Nhận diện khuôn mặt - Ngoại tuyến")
                self.Login_pushButton.setText("Đăng nhập")
                self.loginID = 0
                self.Play_pushButton.setEnabled(False)
                self.ListenEvent_pushButton.setEnabled(False)
                self.Play_wnd.repaint()
                self.Channel_comboBox.clear()
                self.clear_img_ui()

    def play_btn_onclick(self):
        if not self.playID:
            channel = self.Channel_comboBox.currentIndex()
            self.playID = self.sdk.RealPlayEx(self.loginID, channel, self.Play_wnd.winId())
            if self.playID != 0:
                self.Play_pushButton.setText("Dừng")
                result = self.sdk.RenderPrivateData(self.playID, True)
                if not result:
                    QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
            else:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
        else:
            result = self.sdk.RenderPrivateData(self.playID, False)
            if not result:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
            result = self.sdk.StopRealPlayEx(self.playID)
            if result:
                self.Play_pushButton.setText("Xem trực tiếp")
                self.playID = 0
                self.Play_wnd.repaint()
            else:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())

    def listenevent_btn_onclick(self):
        if not self.realloadID:
            channel = self.Channel_comboBox.currentIndex()
            self.realloadID = self.sdk.RealLoadPictureEx(self.loginID, channel, EM_EVENT_IVS_TYPE.ALL, True, self.m_AnalyzerDataCallBack)
            if self.realloadID != 0:
                self.ListenEvent_pushButton.setText("Hủy đăng ký")
            else:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())
        else:
            result = self.sdk.StopLoadPic(self.realloadID)
            if result:
                self.ListenEvent_pushButton.setText("Đăng ký sự kiện")
                self.realloadID = 0
                self.clear_img_ui()
            else:
                QMessageBox.about(self, 'Thông báo', self.sdk.GetLastErrorMessage())

    def show_recognition_info(self, alarm_info, pBuffer, dwBufSize):
        self.clear_img_ui()
        if alarm_info.bGlobalScenePic:
            if pBuffer != 0 and dwBufSize > 0:
                if alarm_info.bGlobalScenePic:
                    if alarm_info.stuGlobalScenePicInfo.dwFileLenth > 0:
                        Global_buf = pBuffer[alarm_info.stuGlobalScenePicInfo.dwOffSet : alarm_info.stuGlobalScenePicInfo.dwOffSet + alarm_info.stuGlobalScenePicInfo.dwFileLenth]
                        with open('./Global_Img.jpg', 'wb+') as global_pic:
                            global_pic.write(bytes(Global_buf))
                        self.GlobalImg_groupBox.setTitle('Ảnh toàn cảnh - Nhận diện khuôn mặt')
                        image = QPixmap('./Global_Img.jpg').scaled(self.GlobalImg_wnd.width(), self.GlobalImg_wnd.height())
                        self.GlobalImg_wnd.setPixmap(image)
                        # self.GlobalImg_wnd.repaint()

        if alarm_info.stuObject.stPicInfo.dwFileLenth > 0:
            self.FaceImg_groupBox.setTitle('Ảnh khuôn mặt - Nhận diện khuôn mặt')
            Face_buf = pBuffer[
                       alarm_info.stuObject.stPicInfo.dwOffSet: alarm_info.stuObject.stPicInfo.dwOffSet + alarm_info.stuObject.stPicInfo.dwFileLenth]
            with open('./Face_Img.jpg', 'wb+') as face_pic:
                face_pic.write(bytes(Face_buf))
            image = QPixmap('./Face_Img.jpg').scaled(self.FaceImg_wnd.width(), self.FaceImg_wnd.height())
            self.FaceImg_wnd.setPixmap(image)
            # self.FaceImg_wnd.repaint()
            self.update_recognition_face_ui(alarm_info)

        if alarm_info.nCandidateNum > 0:
            maxSimilarityPersonInfo = CANDIDATE_INFO()
            for index in range(alarm_info.nCandidateNum):
                if maxSimilarityPersonInfo.bySimilarity < alarm_info.stuCandidates[index].bySimilarity:
                    maxSimilarityPersonInfo = alarm_info.stuCandidates[index]
            if maxSimilarityPersonInfo.stPersonInfo.szFacePicInfo[0].dwFileLenth > 0:
                self.CandidateImg_groupBox.setTitle('Ảnh ứng viên - Nhận diện khuôn mặt')
                Candidate_buf = pBuffer[maxSimilarityPersonInfo.stPersonInfo.szFacePicInfo[0].dwOffSet: maxSimilarityPersonInfo.stPersonInfo.szFacePicInfo[0].dwOffSet + maxSimilarityPersonInfo.stPersonInfo.szFacePicInfo[0].dwFileLenth]
                with open('./Candidate_Img.jpg', 'wb+') as  candidate_pic:
                    candidate_pic.write(bytes(Candidate_buf))
                image = QPixmap('./Candidate_Img.jpg').scaled(self.CandidateImg_wnd.width(), self.CandidateImg_wnd.height())
                self.CandidateImg_wnd.setPixmap(image)
                # self.CandidateImg_wnd.repaint()
                self.update_recognition_candidate_ui(maxSimilarityPersonInfo, False)
        else:
            self.update_recognition_candidate_ui(None, True)

    def show_detect_info(self, alarm_info, pBuffer, dwBufSize):
        if self.detect_object_id != alarm_info.stuObject.nRelativeID:
            self.detect_object_id = alarm_info.stuObject.nRelativeID
            self.clear_img_ui()
            Global_Img = cast(pBuffer, POINTER(c_ubyte * dwBufSize)).contents
            with open('./Global_Img.jpg', 'wb+') as global_pic:
                global_pic.write(Global_Img)
            self.GlobalImg_groupBox.setTitle('Ảnh toàn cảnh - Phát hiện khuôn mặt')
            image = QPixmap('./Global_Img.jpg').scaled(self.GlobalImg_wnd.width(), self.GlobalImg_wnd.height())
            self.GlobalImg_wnd.setPixmap(image)
            # self.GlobalImg_wnd.repaint()
        else:
            self.FaceImg_groupBox.setTitle('Ảnh khuôn mặt - Phát hiện khuôn mặt')
            Face_Img = cast(pBuffer, POINTER(c_ubyte * dwBufSize)).contents
            with open('./Face_Img.jpg', 'wb+') as face_pic:
                face_pic.write(Face_Img)
            image = QPixmap('./Face_Img.jpg').scaled(self.FaceImg_wnd.width(), self.FaceImg_wnd.height())
            self.FaceImg_wnd.setPixmap(image)
            # self.FaceImg_wnd.repaint()
            self.update_detect_ui(alarm_info)

    def clear_img_ui(self):
        self.GlobalImg_groupBox.setTitle('Ảnh toàn cảnh')
        self.FaceImg_groupBox.setTitle('Ảnh khuôn mặt')
        self.CandidateImg_groupBox.setTitle('Ảnh ứng viên')
        self.GlobalImg_wnd.clear()
        # self.GlobalImg_wnd.repaint()
        self.FaceImg_wnd.clear()
        # self.FaceImg_wnd.repaint()
        self.CandidateImg_wnd.clear()
        # self.CandidateImg_wnd.repaint()

        self.face_time_label.setText('')
        self.face_sex_label.setText('')
        self.face_age_label.setText('')
        self.face_race_label.setText('')
        self.face_eye_label.setText('')
        self.face_mouth_label.setText('')
        self.face_mask_label.setText('')
        self.face_beard_label.setText('')

        self.candidate_name_label.setText('')
        self.candidate_sex_label.setText('')
        self.candidate_birth_label.setText('')
        self.candidate_id_label.setText('')
        self.candidate_library_no_label.setText('')
        self.candidate_library_name_label.setText('')
        self.candidate_similarity_label.setText('')

    def update_detect_ui(self, alarm_info):
        time_str = '{}-{}-{} {}:{}:{}'.format(alarm_info.UTC.dwYear, alarm_info.UTC.dwMonth, alarm_info.UTC.dwDay, alarm_info.UTC.dwHour, alarm_info.UTC.dwMinute, alarm_info.UTC.dwSecond)
        self.face_time_label.setText(time_str)

        if alarm_info.emSex == int(EM_DEV_EVENT_FACEDETECT_SEX_TYPE.MAN):
            sex_str = 'Nam'
        elif alarm_info.emSex == int(EM_DEV_EVENT_FACEDETECT_SEX_TYPE.WOMAN):
            sex_str = 'Nữ'
        else:
            sex_str = 'Không xác định'
        self.face_sex_label.setText(sex_str)

        if alarm_info.nAge == 0xff:
            age_str = 'Không xác định'
        else:
            age_str = str(alarm_info.nAge)
        self.face_age_label.setText(age_str)

        if alarm_info.emRace == int(EM_RACE_TYPE.YELLOW):
            race_str = 'Da vàng'
        elif alarm_info.emRace == int(EM_RACE_TYPE.WHITE):
            race_str = 'Da trắng'
        elif alarm_info.emRace == int(EM_RACE_TYPE.BLACK):
            race_str = 'Da đen'
        else:
            race_str = 'Không xác định'
        self.face_race_label.setText(race_str)

        if alarm_info.emEye == int(EM_EYE_STATE_TYPE.OPEN):
            eye_str = 'Mở'
        elif alarm_info.emEye == int(EM_EYE_STATE_TYPE.CLOSE):
            eye_str = 'Nhắm'
        elif alarm_info.emEye == int(EM_EYE_STATE_TYPE.NODISTI):
            eye_str = 'Không rõ'
        else:
            eye_str = 'Không xác định'
        self.face_eye_label.setText(eye_str)

        if alarm_info.emMouth == int(EM_MOUTH_STATE_TYPE.OPEN):
            mouth_str = 'Mở'
        elif alarm_info.emMouth == int(EM_EYE_STATE_TYPE.CLOSE):
            mouth_str = 'Ngậm'
        elif alarm_info.emMouth == int(EM_EYE_STATE_TYPE.NODISTI):
            mouth_str = 'Không rõ'
        else:
            mouth_str = 'Không xác định'
        self.face_mouth_label.setText(mouth_str)

        if alarm_info.emMask == int(EM_MASK_STATE_TYPE.NOMASK):
            mask_str = 'Không đeo'
        elif alarm_info.emMask == int(EM_MASK_STATE_TYPE.WEAR):
            mask_str = 'Đang đeo'
        elif alarm_info.emMask == int(EM_MASK_STATE_TYPE.NODISTI):
            mask_str = 'Không rõ'
        else:
            mask_str = 'Không xác định'
        self.face_mask_label.setText(mask_str)

        if alarm_info.emBeard == int(EM_BEARD_STATE_TYPE.NOBEARD):
            beard_str = 'Không có râu'
        elif alarm_info.emBeard == int(EM_BEARD_STATE_TYPE.HAVEBEARD):
            beard_str = 'Có râu'
        elif alarm_info.emBeard == int(EM_BEARD_STATE_TYPE.NODISTI):
            beard_str = 'Không rõ'
        else:
            beard_str = 'Không xác định'
        self.face_beard_label.setText(beard_str)

        self.FaceImg_groupBox.update()
        QApplication.processEvents()

    def update_recognition_face_ui(self, alarm_info):
        time_str = '{}-{}-{} {}:{}:{}'.format(alarm_info.UTC.dwYear, alarm_info.UTC.dwMonth, alarm_info.UTC.dwDay, alarm_info.UTC.dwHour, alarm_info.UTC.dwMinute, alarm_info.UTC.dwSecond)
        self.face_time_label.setText(time_str)

        if alarm_info.stuFaceData.emSex == int(EM_DEV_EVENT_FACEDETECT_SEX_TYPE.MAN):
            sex_str = 'Nam'
        elif alarm_info.stuFaceData.emSex == int(EM_DEV_EVENT_FACEDETECT_SEX_TYPE.WOMAN):
            sex_str = 'Nữ'
        else:
            sex_str = 'Không rõ'
        self.face_sex_label.setText(sex_str)

        if alarm_info.stuFaceData.nAge == 0xff:
            age_str = 'Không xác định'
        else:
            age_str = str(alarm_info.stuFaceData.nAge)
        self.face_age_label.setText(age_str)

        if alarm_info.stuFaceData.emRace == int(EM_RACE_TYPE.YELLOW):
            race_str = 'Da vàng'
        elif alarm_info.stuFaceData.emRace == int(EM_RACE_TYPE.WHITE):
            race_str = 'Da trắng'
        elif alarm_info.stuFaceData.emRace == int(EM_RACE_TYPE.BLACK):
            race_str = 'Da đen'
        else:
            race_str = 'Không xác định'
        self.face_race_label.setText(race_str)

        if alarm_info.stuFaceData.emEye == int(EM_EYE_STATE_TYPE.OPEN):
            eye_str = 'Mở'
        elif alarm_info.stuFaceData.emEye == int(EM_EYE_STATE_TYPE.CLOSE):
            eye_str = 'Nhắm'
        elif alarm_info.stuFaceData.emEye == int(EM_EYE_STATE_TYPE.NODISTI):
            eye_str = 'Không rõ'
        else:
            eye_str = 'Không xác định'
        self.face_eye_label.setText(eye_str)

        if alarm_info.stuFaceData.emMouth == int(EM_MOUTH_STATE_TYPE.OPEN):
            mouth_str = 'Mở'
        elif alarm_info.stuFaceData.emMouth == int(EM_EYE_STATE_TYPE.CLOSE):
            mouth_str = 'Ngậm'
        elif alarm_info.stuFaceData.emMouth == int(EM_EYE_STATE_TYPE.NODISTI):
            mouth_str = 'Không rõ'
        else:
            mouth_str = 'Không xác định'
        self.face_mouth_label.setText(mouth_str)

        if alarm_info.stuFaceData.emMask == int(EM_MASK_STATE_TYPE.NOMASK):
            mask_str = 'Không đeo'
        elif alarm_info.stuFaceData.emMask == int(EM_MASK_STATE_TYPE.WEAR):
            mask_str = 'Đang đeo'
        elif alarm_info.stuFaceData.emMask == int(EM_MASK_STATE_TYPE.NODISTI):
            mask_str = 'Không rõ'
        else:
            mask_str = 'Không xác định'
        self.face_mask_label.setText(mask_str)

        if alarm_info.stuFaceData.emBeard == int(EM_BEARD_STATE_TYPE.NOBEARD):
            beard_str = 'Không có râu'
        elif alarm_info.stuFaceData.emBeard == int(EM_BEARD_STATE_TYPE.HAVEBEARD):
            beard_str = 'Có râu'
        elif alarm_info.stuFaceData.emBeard == int(EM_BEARD_STATE_TYPE.NODISTI):
            beard_str = 'Không rõ'
        else:
            beard_str = 'Không xác định'
        self.face_beard_label.setText(beard_str)
        self.FaceImg_groupBox.update()
        QApplication.processEvents()

    def update_recognition_candidate_ui(self, candidate_info, is_stranger):
        if not is_stranger:
            self.candidate_name_label.setText(str(candidate_info.stPersonInfo.szPersonNameEx, 'utf-8'))

            if candidate_info.stPersonInfo.bySex == int(EM_DEV_EVENT_FACEDETECT_SEX_TYPE.MAN):
                sex_str = 'Nam'
            elif candidate_info.stPersonInfo.bySex == int(EM_DEV_EVENT_FACEDETECT_SEX_TYPE.WOMAN):
                sex_str = 'Nữ'
            else:
                sex_str = 'Không rõ'
            self.candidate_sex_label.setText(sex_str)

            birth_str = '{}-{}-{}'.format(candidate_info.stPersonInfo.wYear, candidate_info.stPersonInfo.byMonth, candidate_info.stPersonInfo.byDay)
            self.candidate_birth_label.setText(birth_str)

            self.candidate_similarity_label.setText(str(candidate_info.bySimilarity))
            self.candidate_id_label.setText(str(candidate_info.stPersonInfo.szID, 'utf-8'))
            self.candidate_library_no_label.setText(str(candidate_info.stPersonInfo.pszGroupID, 'utf-8'))
            self.candidate_library_name_label.setText(str(candidate_info.stPersonInfo.pszGroupName, 'utf-8'))

        else:
            self.candidate_similarity_label.setText('Người lạ')

        self.CandidateImg_groupBox.update()
        QApplication.processEvents()

    # 实现断线回调函数功能
    def DisConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle("Nhận diện khuôn mặt - Ngoại tuyến")

    # 实现断线重连回调函数功能
    def ReConnectCallBack(self, lLoginID, pchDVRIP, nDVRPort, dwUser):
        self.setWindowTitle('Nhận diện khuôn mặt - Trực tuyến')

    # 关闭主窗口时清理资源
    def closeEvent(self, event):
        event.accept()
        if  self.loginID:
            self.sdk.Logout(self.loginID)
        self.sdk.Cleanup()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    my_wnd = MyMainWindow()
    wnd = my_wnd
    my_wnd.show()
    sys.exit(app.exec_())
