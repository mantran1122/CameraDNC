#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QVector>

#include <windows.h>
#include "dhnetsdk.h"

class QLineEdit;
class QSpinBox;
class QPushButton;
class QLabel;
class QTableWidget;
class QComboBox;
class QCheckBox;

class VideoCell;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow() override;

signals:
    // Phat tu thread callback cua SDK -> queued sang UI thread
    void sdkEvent(int channel, uint code, QByteArray picData);
    void sdkDisconnected(QString ip);
    void sdkReconnected(QString ip);

private slots:
    void doLogin();
    void doLogout();
    void onSdkEvent(int channel, uint code, QByteArray picData);
    void onDisconnected(const QString &ip);
    void onReconnected(const QString &ip);
    void applyEventFilter();
    void clearEvents();
    void onEventRowClicked(int row, int column);

private:
    void attachAllChannels();
    void detachAllChannels();
    void startVideos();
    void stopVideos();
    void logToCsv(const QString &time, int channel, uint code, const QString &name);
    void showPicture(const QByteArray &picData);
    static QString eventName(uint code);

    // Callback tinh cua SDK (chay tren thread cua SDK)
    static int  CALLBACK AnalyzerDataCB(LLONG lAnalyzerHandle, DWORD dwAlarmType,
                                        void *pAlarmInfo, BYTE *pBuffer, DWORD dwBufSize,
                                        LDWORD dwUser, int nSequence, void *reserved);
    static void CALLBACK DisconnectCB(LLONG lLoginID, char *ip, LONG port, LDWORD dwUser);
    static void CALLBACK ReconnectCB(LLONG lLoginID, char *ip, LONG port, LDWORD dwUser);

    LLONG m_loginID = 0;
    int m_channelCount = 0;

    struct AttachInfo { LLONG handle; int channel; };
    QVector<AttachInfo> m_attaches;
    QVector<LLONG> m_playHandles;

    // UI
    QLineEdit *m_ipEdit;
    QSpinBox *m_portSpin;
    QLineEdit *m_userEdit;
    QLineEdit *m_passEdit;
    QPushButton *m_loginBtn;
    QPushButton *m_logoutBtn;
    QLabel *m_statusLabel;

    QVector<VideoCell*> m_videoCells;   // luoi 2x2, kenh 0..3
    QLabel *m_eventPic;
    QTableWidget *m_eventTable;
    QComboBox *m_filterChannel;
    QCheckBox *m_csvCheck;
};

#endif // MAINWINDOW_H
