#include "mainwindow.h"

#include <QApplication>
#include <QCheckBox>
#include <QComboBox>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QGridLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QHeaderView>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPushButton>
#include <QSpinBox>
#include <QSplitter>
#include <QTableWidget>
#include <QTextStream>
#include <QVBoxLayout>

// O video: widget native de SDK ve truc tiep len HWND
class VideoCell : public QWidget
{
public:
    explicit VideoCell(int channel, QWidget *parent = nullptr)
        : QWidget(parent)
    {
        setAttribute(Qt::WA_NativeWindow);
        setAttribute(Qt::WA_PaintOnScreen);
        setAutoFillBackground(true);
        QPalette pal = palette();
        pal.setColor(QPalette::Window, Qt::black);
        setPalette(pal);
        setMinimumSize(240, 180);

        auto *label = new QLabel(QStringLiteral("Kênh %1").arg(channel + 1), this);
        label->setStyleSheet(QStringLiteral("color:#888; background:transparent;"));
        label->move(6, 4);
    }
    QPaintEngine *paintEngine() const override { return nullptr; }
};

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
{
    setWindowTitle(QStringLiteral("NetSDK Monitor - Xem camera & sự kiện AI"));
    resize(1200, 760);

    CLIENT_Init(&MainWindow::DisconnectCB, (LDWORD)this);
    CLIENT_SetAutoReconnect(&MainWindow::ReconnectCB, (LDWORD)this);

    auto *central = new QWidget(this);
    auto *mainLayout = new QVBoxLayout(central);

    // ---- Thanh dang nhap ----
    auto *loginBox = new QGroupBox(QStringLiteral("Đăng nhập đầu ghi / camera"));
    auto *loginLayout = new QHBoxLayout(loginBox);
    m_ipEdit = new QLineEdit(QStringLiteral("192.168.3.26"));
    m_ipEdit->setMaximumWidth(130);
    m_portSpin = new QSpinBox;
    m_portSpin->setRange(1, 65535);
    m_portSpin->setValue(37777);
    m_userEdit = new QLineEdit(QStringLiteral("admin"));
    m_userEdit->setMaximumWidth(100);
    m_passEdit = new QLineEdit;
    m_passEdit->setEchoMode(QLineEdit::Password);
    m_passEdit->setMaximumWidth(140);
    m_loginBtn = new QPushButton(QStringLiteral("Kết nối"));
    m_logoutBtn = new QPushButton(QStringLiteral("Ngắt kết nối"));
    m_logoutBtn->setEnabled(false);
    m_statusLabel = new QLabel(QStringLiteral("Chưa kết nối"));

    loginLayout->addWidget(new QLabel(QStringLiteral("IP:")));
    loginLayout->addWidget(m_ipEdit);
    loginLayout->addWidget(new QLabel(QStringLiteral("Port:")));
    loginLayout->addWidget(m_portSpin);
    loginLayout->addWidget(new QLabel(QStringLiteral("User:")));
    loginLayout->addWidget(m_userEdit);
    loginLayout->addWidget(new QLabel(QStringLiteral("Mật khẩu:")));
    loginLayout->addWidget(m_passEdit);
    loginLayout->addWidget(m_loginBtn);
    loginLayout->addWidget(m_logoutBtn);
    loginLayout->addWidget(m_statusLabel, 1);
    mainLayout->addWidget(loginBox);

    // ---- Video 2x2 + anh su kien ----
    auto *midSplitter = new QSplitter(Qt::Horizontal);

    auto *videoWidget = new QWidget;
    auto *videoGrid = new QGridLayout(videoWidget);
    videoGrid->setSpacing(4);
    for (int i = 0; i < 4; ++i) {
        auto *cell = new VideoCell(i);
        m_videoCells.append(cell);
        videoGrid->addWidget(cell, i / 2, i % 2);
    }
    midSplitter->addWidget(videoWidget);

    auto *picBox = new QGroupBox(QStringLiteral("Ảnh sự kiện gần nhất"));
    auto *picLayout = new QVBoxLayout(picBox);
    m_eventPic = new QLabel(QStringLiteral("(chưa có)"));
    m_eventPic->setAlignment(Qt::AlignCenter);
    m_eventPic->setMinimumSize(320, 240);
    m_eventPic->setScaledContents(false);
    picLayout->addWidget(m_eventPic, 1);
    midSplitter->addWidget(picBox);
    midSplitter->setStretchFactor(0, 3);
    midSplitter->setStretchFactor(1, 2);
    mainLayout->addWidget(midSplitter, 3);

    // ---- Bang su kien ----
    auto *eventBox = new QGroupBox(QStringLiteral("Sự kiện thời gian thực"));
    auto *eventLayout = new QVBoxLayout(eventBox);

    auto *filterLayout = new QHBoxLayout;
    filterLayout->addWidget(new QLabel(QStringLiteral("Lọc theo kênh:")));
    m_filterChannel = new QComboBox;
    m_filterChannel->addItem(QStringLiteral("Tất cả"), -1);
    filterLayout->addWidget(m_filterChannel);
    m_csvCheck = new QCheckBox(QStringLiteral("Ghi log ra events_log.csv"));
    m_csvCheck->setChecked(true);
    filterLayout->addWidget(m_csvCheck);
    auto *clearBtn = new QPushButton(QStringLiteral("Xóa danh sách"));
    filterLayout->addWidget(clearBtn);
    filterLayout->addStretch();
    eventLayout->addLayout(filterLayout);

    m_eventTable = new QTableWidget(0, 4);
    m_eventTable->setHorizontalHeaderLabels(
        {QStringLiteral("Thời gian"), QStringLiteral("Kênh"),
         QStringLiteral("Mã"), QStringLiteral("Tên sự kiện")});
    m_eventTable->horizontalHeader()->setStretchLastSection(true);
    m_eventTable->verticalHeader()->setVisible(false);
    m_eventTable->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_eventTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    eventLayout->addWidget(m_eventTable);
    mainLayout->addWidget(eventBox, 2);

    setCentralWidget(central);

    connect(m_loginBtn, &QPushButton::clicked, this, &MainWindow::doLogin);
    connect(m_logoutBtn, &QPushButton::clicked, this, &MainWindow::doLogout);
    connect(m_passEdit, &QLineEdit::returnPressed, this, &MainWindow::doLogin);
    connect(clearBtn, &QPushButton::clicked, this, &MainWindow::clearEvents);
    connect(m_filterChannel, &QComboBox::currentIndexChanged, this, &MainWindow::applyEventFilter);
    connect(m_eventTable, &QTableWidget::cellClicked, this, &MainWindow::onEventRowClicked);

    // Tin hieu tu thread SDK -> UI thread (queued tu dong vi khac thread)
    connect(this, &MainWindow::sdkEvent, this, &MainWindow::onSdkEvent);
    connect(this, &MainWindow::sdkDisconnected, this, &MainWindow::onDisconnected);
    connect(this, &MainWindow::sdkReconnected, this, &MainWindow::onReconnected);
}

MainWindow::~MainWindow()
{
    doLogout();
    CLIENT_Cleanup();
}

// ================= Dang nhap / dang xuat =================

void MainWindow::doLogin()
{
    if (m_loginID != 0)
        return;
    if (m_passEdit->text().isEmpty()) {
        QMessageBox::information(this, QStringLiteral("Thiếu mật khẩu"),
                                 QStringLiteral("Hãy nhập mật khẩu thiết bị."));
        return;
    }

    NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY inLogin;
    NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY outLogin;
    memset(&inLogin, 0, sizeof(inLogin));
    memset(&outLogin, 0, sizeof(outLogin));
    inLogin.dwSize = sizeof(inLogin);
    outLogin.dwSize = sizeof(outLogin);
    QByteArray ip = m_ipEdit->text().trimmed().toLatin1();
    QByteArray user = m_userEdit->text().trimmed().toLatin1();
    QByteArray pass = m_passEdit->text().toLatin1();
    strncpy_s(inLogin.szIP, ip.constData(), _TRUNCATE);
    inLogin.nPort = m_portSpin->value();
    strncpy_s(inLogin.szUserName, user.constData(), _TRUNCATE);
    strncpy_s(inLogin.szPassword, pass.constData(), _TRUNCATE);

    m_loginID = CLIENT_LoginWithHighLevelSecurity(&inLogin, &outLogin);
    if (m_loginID == 0) {
        QMessageBox::warning(this, QStringLiteral("Lỗi đăng nhập"),
            QStringLiteral("Đăng nhập thất bại, mã lỗi: %1")
                .arg(CLIENT_GetLastError() & 0x7fffffff));
        return;
    }

    m_channelCount = outLogin.stuDeviceInfo.nChanNum;
    m_statusLabel->setText(QStringLiteral("✅ Đã kết nối %1 — thiết bị có %2 kênh")
                               .arg(m_ipEdit->text()).arg(m_channelCount));
    m_loginBtn->setEnabled(false);
    m_logoutBtn->setEnabled(true);

    m_filterChannel->clear();
    m_filterChannel->addItem(QStringLiteral("Tất cả"), -1);
    for (int i = 0; i < m_channelCount && i < 32; ++i)
        m_filterChannel->addItem(QStringLiteral("Kênh %1 (D%1)").arg(i + 1), i);

    startVideos();
    attachAllChannels();
}

void MainWindow::doLogout()
{
    if (m_loginID == 0)
        return;
    detachAllChannels();
    stopVideos();
    CLIENT_Logout(m_loginID);
    m_loginID = 0;
    m_channelCount = 0;
    m_statusLabel->setText(QStringLiteral("Chưa kết nối"));
    m_loginBtn->setEnabled(true);
    m_logoutBtn->setEnabled(false);
}

// ================= Video =================

void MainWindow::startVideos()
{
    int n = qMin(m_channelCount, m_videoCells.size());
    for (int ch = 0; ch < n; ++ch) {
        HWND hwnd = (HWND)m_videoCells[ch]->winId();
        LLONG h = CLIENT_RealPlayEx(m_loginID, ch, hwnd, DH_RType_Realplay_0);
        if (h != 0)
            m_playHandles.append(h);
    }
}

void MainWindow::stopVideos()
{
    for (LLONG h : m_playHandles)
        CLIENT_StopRealPlayEx(h);
    m_playHandles.clear();
    for (VideoCell *cell : m_videoCells)
        cell->update();
}

// ================= Su kien =================

void MainWindow::attachAllChannels()
{
    int n = qMin(m_channelCount, 16); // gioi han 16 kenh cho nhe
    for (int ch = 0; ch < n; ++ch) {
        LLONG h = CLIENT_RealLoadPictureEx(m_loginID, ch, EVENT_IVS_ALL, TRUE,
                                           &MainWindow::AnalyzerDataCB, (LDWORD)this, NULL);
        if (h != 0)
            m_attaches.append({h, ch});
    }
}

void MainWindow::detachAllChannels()
{
    for (const AttachInfo &a : m_attaches)
        CLIENT_StopLoadPic(a.handle);
    m_attaches.clear();
}

QString MainWindow::eventName(uint code)
{
    switch (code) {
    case EVENT_IVS_CROSSLINEDETECTION:      return QStringLiteral("IVS: Vượt rào ảo (Tripwire)");
    case EVENT_IVS_CROSSREGIONDETECTION:    return QStringLiteral("IVS: Xâm nhập vùng (Intrusion)");
    case EVENT_IVS_LEFTDETECTION:           return QStringLiteral("IVS: Vật bỏ lại");
    case EVENT_IVS_WANDERDETECTION:         return QStringLiteral("IVS: Đi lảng vảng");
    case EVENT_IVS_TAKENAWAYDETECTION:      return QStringLiteral("IVS: Vật bị lấy đi");
    case EVENT_IVS_PARKINGDETECTION:        return QStringLiteral("IVS: Đỗ xe trái phép");
    case EVENT_IVS_FACEDETECT:              return QStringLiteral("Phát hiện khuôn mặt");
    case EVENT_IVS_FACERECOGNITION:         return QStringLiteral("Nhận diện khuôn mặt");
    case EVENT_ALARM_MOTIONDETECT:          return QStringLiteral("Chuyển động (Motion)");
    case EVENT_ALARM_LOCALALARM:            return QStringLiteral("Báo động cục bộ");
    case EVENT_ALARM_SMARTMOTION_HUMAN:     return QStringLiteral("SMD: Người");
    case EVENT_ALARM_SMARTMOTION_VEHICLE:   return QStringLiteral("SMD: Xe");
    default:
        return QStringLiteral("Sự kiện 0x%1").arg(code, 0, 16);
    }
}

void MainWindow::onSdkEvent(int channel, uint code, QByteArray picData)
{
    const QString timeStr = QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss"));
    const QString name = eventName(code);

    const bool hasPic = !picData.isEmpty();

    m_eventTable->insertRow(0);
    auto mkItem = [](const QString &text) { return new QTableWidgetItem(text); };
    m_eventTable->setItem(0, 0, mkItem(hasPic ? QStringLiteral("📷 %1").arg(timeStr) : timeStr));
    m_eventTable->setItem(0, 1, mkItem(QStringLiteral("D%1").arg(channel + 1)));
    m_eventTable->setItem(0, 2, mkItem(QStringLiteral("0x%1").arg(code, 0, 16)));
    m_eventTable->setItem(0, 3, mkItem(name));
    m_eventTable->item(0, 1)->setData(Qt::UserRole, channel);
    // Luu anh kem theo dong de bam vao xem lai
    if (hasPic)
        m_eventTable->item(0, 0)->setData(Qt::UserRole, picData);
    if (m_eventTable->rowCount() > 300)
        m_eventTable->removeRow(m_eventTable->rowCount() - 1);

    // Ap dung bo loc cho dong moi
    int filterCh = m_filterChannel->currentData().toInt();
    m_eventTable->setRowHidden(0, filterCh >= 0 && filterCh != channel);

    // Neu nguoi dung khong dang xem mot dong cu thi hien anh moi nhat
    if (hasPic && m_eventTable->currentRow() <= 0)
        showPicture(picData);

    if (m_csvCheck->isChecked())
        logToCsv(QDateTime::currentDateTime().toString(Qt::ISODate), channel, code, name);
}

void MainWindow::showPicture(const QByteArray &picData)
{
    QPixmap pm;
    if (pm.loadFromData(picData)) {
        m_eventPic->setPixmap(pm.scaled(m_eventPic->size(), Qt::KeepAspectRatio,
                                        Qt::SmoothTransformation));
    }
}

void MainWindow::onEventRowClicked(int row, int /*column*/)
{
    QTableWidgetItem *timeItem = m_eventTable->item(row, 0);
    if (!timeItem)
        return;
    const QByteArray pic = timeItem->data(Qt::UserRole).toByteArray();
    if (!pic.isEmpty()) {
        showPicture(pic);
    } else {
        m_eventPic->setPixmap(QPixmap());
        m_eventPic->setText(QStringLiteral("(sự kiện này không kèm ảnh)"));
    }
}

void MainWindow::applyEventFilter()
{
    int filterCh = m_filterChannel->currentData().toInt();
    for (int r = 0; r < m_eventTable->rowCount(); ++r) {
        int ch = m_eventTable->item(r, 1)->data(Qt::UserRole).toInt();
        m_eventTable->setRowHidden(r, filterCh >= 0 && filterCh != ch);
    }
}

void MainWindow::clearEvents()
{
    m_eventTable->setRowCount(0);
}

void MainWindow::logToCsv(const QString &time, int channel, uint code, const QString &name)
{
    QFile f(QCoreApplication::applicationDirPath() + QStringLiteral("/events_log.csv"));
    if (!f.open(QIODevice::Append | QIODevice::Text))
        return;
    QTextStream out(&f);
    out << time << ',' << (channel + 1) << ",0x" << QString::number(code, 16)
        << ",\"" << name << "\"\n";
}

void MainWindow::onDisconnected(const QString &ip)
{
    m_statusLabel->setText(QStringLiteral("⚠️ Mất kết nối tới %1 — đang tự kết nối lại...").arg(ip));
}

void MainWindow::onReconnected(const QString &ip)
{
    m_statusLabel->setText(QStringLiteral("✅ Đã kết nối lại %1").arg(ip));
}

// ================= Callback SDK (thread khac) =================

int CALLBACK MainWindow::AnalyzerDataCB(LLONG lAnalyzerHandle, DWORD dwAlarmType,
                                        void * /*pAlarmInfo*/, BYTE *pBuffer, DWORD dwBufSize,
                                        LDWORD dwUser, int /*nSequence*/, void * /*reserved*/)
{
    auto *self = reinterpret_cast<MainWindow*>(dwUser);
    if (!self)
        return 0;

    int channel = -1;
    for (const AttachInfo &a : self->m_attaches) {
        if (a.handle == lAnalyzerHandle) { channel = a.channel; break; }
    }

    QByteArray pic;
    if (pBuffer && dwBufSize > 0 && dwBufSize < 4 * 1024 * 1024)
        pic = QByteArray(reinterpret_cast<const char*>(pBuffer), dwBufSize);

    emit self->sdkEvent(channel, dwAlarmType, pic);
    return 0;
}

void CALLBACK MainWindow::DisconnectCB(LLONG, char *ip, LONG, LDWORD dwUser)
{
    auto *self = reinterpret_cast<MainWindow*>(dwUser);
    if (self)
        emit self->sdkDisconnected(QString::fromLatin1(ip ? ip : "?"));
}

void CALLBACK MainWindow::ReconnectCB(LLONG, char *ip, LONG, LDWORD dwUser)
{
    auto *self = reinterpret_cast<MainWindow*>(dwUser);
    if (self)
        emit self->sdkReconnected(QString::fromLatin1(ip ? ip : "?"));
}
