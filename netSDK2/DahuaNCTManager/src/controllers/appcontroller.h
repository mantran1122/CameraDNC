#ifndef APPCONTROLLER_H
#define APPCONTROLLER_H

#include "src/models/deviceconnectioninfo.h"
#include "src/models/downloadtask.h"
#include "src/models/previewchannelinfo.h"

#include <QObject>
#include <QVector>

class DeviceManager;
class DownloadManager;
class VideoManager;

class AppController : public QObject
{
    Q_OBJECT

public:
    explicit AppController(QObject *parent = nullptr);
    ~AppController() override;

    void initialize();
    DeviceConnectionInfo defaultDevice() const;
    QString downloadPath() const;
    bool login(const DeviceConnectionInfo &deviceInfo);
    void logout();
    bool startLive(quintptr renderHandle, int channel = 0, int renderWidth = 0, int renderHeight = 0);
    void stopLive();
    void stopLive(quintptr renderHandle);
    void setPreviewFillMode(bool enabled);
    bool downloadByTime(const DownloadTask &task);
    void stopDownload();
    bool isLoggedIn() const;
    bool isPreviewing() const;
    bool isDownloading() const;
    int channelCount() const;
    QVector<PreviewChannelInfo> previewChannels() const;

signals:
    void statusChanged(bool connected, const QString &message);
    void liveStateChanged(bool active, const QString &message);
    void downloadStateChanged(bool active, const QString &message);
    void downloadProgressChanged(int progress);

private:
    DeviceManager *m_deviceManager = nullptr;
    VideoManager *m_videoManager = nullptr;
    DownloadManager *m_downloadManager = nullptr;
};

#endif // APPCONTROLLER_H
