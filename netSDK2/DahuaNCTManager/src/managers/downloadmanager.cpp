#include "src/managers/downloadmanager.h"

#include "src/sdk/dahuasdkmanager.h"

DownloadManager::DownloadManager(QObject *parent)
    : QObject(parent)
{
    connect(&DahuaSdkManager::instance(), &DahuaSdkManager::downloadProgressChanged,
            this, &DownloadManager::downloadProgressChanged);
    connect(&DahuaSdkManager::instance(), &DahuaSdkManager::downloadStateChanged,
            this, &DownloadManager::downloadStateChanged);
}

bool DownloadManager::downloadByTime(const DownloadTask &task)
{
    return DahuaSdkManager::instance().downloadByTime(task);
}

void DownloadManager::stopDownload()
{
    DahuaSdkManager::instance().stopDownload();
}

bool DownloadManager::isDownloading() const
{
    return DahuaSdkManager::instance().isDownloading();
}
