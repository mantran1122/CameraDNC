#include "src/managers/videomanager.h"

#include "src/sdk/dahuasdkmanager.h"

VideoManager::VideoManager(QObject *parent)
    : QObject(parent)
{
    connect(&DahuaSdkManager::instance(), &DahuaSdkManager::liveStateChanged,
            this, &VideoManager::liveStateChanged);
}

bool VideoManager::startLive(quintptr renderHandle, int channel, int renderWidth, int renderHeight)
{
    return DahuaSdkManager::instance().startLive(channel, renderHandle, renderWidth, renderHeight);
}

void VideoManager::stopLive()
{
    DahuaSdkManager::instance().stopLive();
}

void VideoManager::stopLive(quintptr renderHandle)
{
    DahuaSdkManager::instance().stopLive(renderHandle);
}

void VideoManager::setPreviewFillMode(bool enabled)
{
    DahuaSdkManager::instance().setPreviewFillMode(enabled);
}

bool VideoManager::isPreviewing() const
{
    return DahuaSdkManager::instance().isPreviewing();
}
