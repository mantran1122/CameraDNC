#include "src/controllers/appcontroller.h"

#include "src/managers/configmanager.h"
#include "src/managers/devicemanager.h"
#include "src/managers/downloadmanager.h"
#include "src/managers/loggermanager.h"
#include "src/managers/videomanager.h"
#include "src/sdk/dahuasdkmanager.h"
#include "src/utils/pathutils.h"

AppController::AppController(QObject *parent)
    : QObject(parent)
    , m_deviceManager(new DeviceManager(this))
    , m_videoManager(new VideoManager(this))
    , m_downloadManager(new DownloadManager(this))
{
    connect(m_deviceManager, &DeviceManager::deviceStateChanged,
            this, &AppController::statusChanged);
    connect(m_videoManager, &VideoManager::liveStateChanged,
            this, &AppController::liveStateChanged);
    connect(m_downloadManager, &DownloadManager::downloadStateChanged,
            this, &AppController::downloadStateChanged);
    connect(m_downloadManager, &DownloadManager::downloadProgressChanged,
            this, &AppController::downloadProgressChanged);
}

AppController::~AppController()
{
    DahuaSdkManager::instance().cleanup();
}

void AppController::initialize()
{
    PathUtils::ensureRuntimeDirectories();
    LoggerManager::instance().initialize();
    ConfigManager::instance().initialize();

    DahuaSdkManager::instance().initialize();
}

DeviceConnectionInfo AppController::defaultDevice() const
{
    return ConfigManager::instance().defaultDevice();
}

QString AppController::downloadPath() const
{
    return ConfigManager::instance().downloadPath();
}

bool AppController::login(const DeviceConnectionInfo &deviceInfo)
{
    const bool success = m_deviceManager->login(deviceInfo);
    if (success) {
        ConfigManager::instance().setDefaultDevice(deviceInfo);
    }
    return success;
}

void AppController::logout()
{
    m_videoManager->stopLive();
    m_deviceManager->logout();
}

bool AppController::startLive(quintptr renderHandle, int channel, int renderWidth, int renderHeight)
{
    return m_videoManager->startLive(renderHandle, channel, renderWidth, renderHeight);
}

void AppController::stopLive()
{
    m_videoManager->stopLive();
}

void AppController::stopLive(quintptr renderHandle)
{
    m_videoManager->stopLive(renderHandle);
}

void AppController::setPreviewFillMode(bool enabled)
{
    m_videoManager->setPreviewFillMode(enabled);
}

bool AppController::downloadByTime(const DownloadTask &task)
{
    return m_downloadManager->downloadByTime(task);
}

void AppController::stopDownload()
{
    m_downloadManager->stopDownload();
}

bool AppController::isLoggedIn() const
{
    return m_deviceManager->isLoggedIn();
}

bool AppController::isPreviewing() const
{
    return m_videoManager->isPreviewing();
}

bool AppController::isDownloading() const
{
    return m_downloadManager->isDownloading();
}

int AppController::channelCount() const
{
    return m_deviceManager->channelCount();
}

QVector<PreviewChannelInfo> AppController::previewChannels() const
{
    return m_deviceManager->previewChannels();
}
