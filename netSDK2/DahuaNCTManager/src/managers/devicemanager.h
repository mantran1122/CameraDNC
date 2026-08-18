#ifndef DEVICEMANAGER_H
#define DEVICEMANAGER_H

#include "src/models/deviceconnectioninfo.h"
#include "src/models/previewchannelinfo.h"

#include <QObject>
#include <QVector>

class DeviceManager : public QObject
{
    Q_OBJECT

public:
    explicit DeviceManager(QObject *parent = nullptr);

    bool login(const DeviceConnectionInfo &deviceInfo);
    void logout();
    bool isLoggedIn() const;
    int channelCount() const;
    QVector<PreviewChannelInfo> previewChannels() const;
    DeviceConnectionInfo currentDevice() const;

signals:
    void deviceStateChanged(bool connected, const QString &message);

private:
    DeviceConnectionInfo m_currentDevice;
};

#endif // DEVICEMANAGER_H
