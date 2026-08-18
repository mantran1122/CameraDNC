#include "src/managers/configmanager.h"

#include "src/managers/loggermanager.h"
#include "src/utils/pathutils.h"

#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>

namespace
{
QString configFilePath()
{
    return PathUtils::configDirPath() + QStringLiteral("/config.json");
}
}

ConfigManager::ConfigManager(QObject *parent)
    : QObject(parent)
{
}

ConfigManager &ConfigManager::instance()
{
    static ConfigManager instance;
    return instance;
}

void ConfigManager::initialize()
{
    if (m_initialized) {
        return;
    }

    PathUtils::ensureRuntimeDirectories();
    load();
    m_initialized = true;
    LoggerManager::instance().logInfo(QStringLiteral("Configuration initialized"));
}

DeviceConnectionInfo ConfigManager::defaultDevice() const
{
    const QJsonObject deviceObject = m_rootObject.value(QStringLiteral("device")).toObject();

    DeviceConnectionInfo info;
    info.name = deviceObject.value(QStringLiteral("name")).toString(QStringLiteral("Default Device"));
    info.host = deviceObject.value(QStringLiteral("host")).toString(QStringLiteral("192.168.3.26"));
    info.port = static_cast<quint16>(deviceObject.value(QStringLiteral("port")).toInt(37777));
    info.username = deviceObject.value(QStringLiteral("username")).toString(QStringLiteral("admin"));
    info.password = deviceObject.value(QStringLiteral("password")).toString();
    return info;
}

void ConfigManager::setDefaultDevice(const DeviceConnectionInfo &deviceInfo)
{
    QJsonObject deviceObject;
    deviceObject.insert(QStringLiteral("name"), deviceInfo.name);
    deviceObject.insert(QStringLiteral("host"), deviceInfo.host);
    deviceObject.insert(QStringLiteral("port"), static_cast<int>(deviceInfo.port));
    deviceObject.insert(QStringLiteral("username"), deviceInfo.username);
    deviceObject.insert(QStringLiteral("password"), deviceInfo.password);

    m_rootObject.insert(QStringLiteral("device"), deviceObject);
    save();
}

QString ConfigManager::downloadPath() const
{
    return m_rootObject.value(QStringLiteral("paths")).toObject()
        .value(QStringLiteral("download")).toString(PathUtils::downloadDirPath());
}

QString ConfigManager::snapshotPath() const
{
    return m_rootObject.value(QStringLiteral("paths")).toObject()
        .value(QStringLiteral("snapshot")).toString(PathUtils::snapshotDirPath());
}

void ConfigManager::load()
{
    QFile file(configFilePath());
    if (!file.exists()) {
        m_rootObject = defaultConfig();
        save();
        return;
    }

    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        m_rootObject = defaultConfig();
        return;
    }

    const QJsonDocument document = QJsonDocument::fromJson(file.readAll());
    m_rootObject = document.object();
    if (m_rootObject.isEmpty()) {
        m_rootObject = defaultConfig();
        save();
    }
}

void ConfigManager::save() const
{
    QFile file(configFilePath());
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text | QIODevice::Truncate)) {
        LoggerManager::instance().logError(QStringLiteral("Unable to write config.json"));
        return;
    }

    file.write(QJsonDocument(m_rootObject).toJson(QJsonDocument::Indented));
}

QJsonObject ConfigManager::defaultConfig() const
{
    QJsonObject pathsObject;
    pathsObject.insert(QStringLiteral("download"), PathUtils::downloadDirPath());
    pathsObject.insert(QStringLiteral("snapshot"), PathUtils::snapshotDirPath());
    pathsObject.insert(QStringLiteral("export"), PathUtils::exportDirPath());

    QJsonObject deviceObject;
    deviceObject.insert(QStringLiteral("name"), QStringLiteral("Default Device"));
    deviceObject.insert(QStringLiteral("host"), QStringLiteral("192.168.3.26"));
    deviceObject.insert(QStringLiteral("port"), 37777);
    deviceObject.insert(QStringLiteral("username"), QStringLiteral("admin"));
    deviceObject.insert(QStringLiteral("password"), QStringLiteral(""));

    QJsonObject rootObject;
    rootObject.insert(QStringLiteral("device"), deviceObject);
    rootObject.insert(QStringLiteral("paths"), pathsObject);
    return rootObject;
}
