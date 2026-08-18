#ifndef CONFIGMANAGER_H
#define CONFIGMANAGER_H

#include "src/models/deviceconnectioninfo.h"

#include <QObject>
#include <QJsonObject>

class ConfigManager : public QObject
{
    Q_OBJECT

public:
    static ConfigManager &instance();

    void initialize();
    DeviceConnectionInfo defaultDevice() const;
    void setDefaultDevice(const DeviceConnectionInfo &deviceInfo);
    QString downloadPath() const;
    QString snapshotPath() const;

private:
    explicit ConfigManager(QObject *parent = nullptr);
    void load();
    void save() const;
    QJsonObject defaultConfig() const;

    QJsonObject m_rootObject;
    bool m_initialized = false;
};

#endif // CONFIGMANAGER_H
