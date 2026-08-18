#ifndef DAHUASDKMANAGER_H
#define DAHUASDKMANAGER_H

#include "src/models/deviceconnectioninfo.h"
#include "src/models/downloadtask.h"
#include "src/models/previewchannelinfo.h"

#include <QObject>
#include <QtGlobal>
#include <QVector>

class DahuaSdkManager : public QObject
{
    Q_OBJECT

public:
    static DahuaSdkManager &instance();

    bool initialize();
    void cleanup();
    bool login(const DeviceConnectionInfo &deviceInfo);
    void logout();
    bool startLive(int channel, quintptr renderHandle, int renderWidth = 0, int renderHeight = 0);
    void stopLive();
    void stopLive(quintptr renderHandle);
    void setPreviewFillMode(bool enabled);
    bool downloadByTime(const DownloadTask &task);
    void stopDownload();
    bool isInitialized() const;
    bool isLoggedIn() const;
    bool isPreviewing() const;
    bool isDownloading() const;
    int channelCount() const;
    QVector<PreviewChannelInfo> previewChannels() const;
    QString lastError() const;
    void feedPlaySdkData(qint64 liveHandle, unsigned char *buffer, unsigned long bufferSize);

signals:
    void sdkLogMessage(const QString &message);
    void connectionStateChanged(bool connected, const QString &message);
    void liveStateChanged(bool active, const QString &message);
    void downloadStateChanged(bool active, const QString &message);
    void downloadProgressChanged(int progress);
    void deviceDisconnected(const QString &host, int port);
    void deviceReconnected(const QString &host, int port);

private:
    explicit DahuaSdkManager(QObject *parent = nullptr);
    void emitConnectionEvent(bool connected, const QString &message);
    QString formatLastError() const;
    bool ensurePreviewLogin();
    void releasePreviewLogin();
    void stopLiveSession(int index);
    int findLiveSessionIndex(qint64 liveHandle) const;

    struct LivePreviewSession
    {
        qint64 handle = 0;
        quintptr renderHandle = 0;
        int channel = -1;
        bool callbackMode = false;
        long playPort = -1;
    };

    bool m_initialized = false;
    qint64 m_loginHandle = 0;
    qint64 m_previewLoginHandle = 0;
    qint64 m_downloadHandle = 0;
    int m_channelCount = 0;
    QVector<PreviewChannelInfo> m_previewChannels;
    QVector<LivePreviewSession> m_liveSessions;
    DeviceConnectionInfo m_lastConnectionInfo;
    QString m_lastError;
    bool m_previewFillMode = false;
};

#endif // DAHUASDKMANAGER_H
