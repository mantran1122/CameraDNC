#ifndef DEVICECONNECTIONINFO_H
#define DEVICECONNECTIONINFO_H

#include <QString>

struct DeviceConnectionInfo
{
    QString name;
    QString host;
    quint16 port = 37777;
    QString username;
    QString password;

    bool isValid() const
    {
        return !host.trimmed().isEmpty() && !username.trimmed().isEmpty();
    }
};

#endif // DEVICECONNECTIONINFO_H
