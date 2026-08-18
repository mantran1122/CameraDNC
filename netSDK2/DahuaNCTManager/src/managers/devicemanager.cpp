#include "src/managers/devicemanager.h"

#include "src/sdk/dahuasdkmanager.h"

DeviceManager::DeviceManager(QObject *parent)
    : QObject(parent)
{
    connect(&DahuaSdkManager::instance(), &DahuaSdkManager::connectionStateChanged,
            this, &DeviceManager::deviceStateChanged);
}

bool DeviceManager::login(const DeviceConnectionInfo &deviceInfo)
{
    if (!deviceInfo.isValid()) {
        emit deviceStateChanged(false, QStringLiteral("Missing device connection settings"));
        return false;
    }

    const bool success = DahuaSdkManager::instance().login(deviceInfo);
    if (success) {
        m_currentDevice = deviceInfo;
    }
    return success;
}

void DeviceManager::logout()
{
    DahuaSdkManager::instance().logout();
}

bool DeviceManager::isLoggedIn() const
{
    return DahuaSdkManager::instance().isLoggedIn();
}

int DeviceManager::channelCount() const
{
    return DahuaSdkManager::instance().channelCount();
}

QVector<PreviewChannelInfo> DeviceManager::previewChannels() const
{
    return DahuaSdkManager::instance().previewChannels();
}

DeviceConnectionInfo DeviceManager::currentDevice() const
{
    return m_currentDevice;
}
