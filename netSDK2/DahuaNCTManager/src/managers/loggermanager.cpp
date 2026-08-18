#include "src/managers/loggermanager.h"

#include "src/utils/pathutils.h"

#include <QDateTime>
#include <QFile>
#include <QTextStream>

LoggerManager::LoggerManager(QObject *parent)
    : QObject(parent)
{
}

LoggerManager &LoggerManager::instance()
{
    static LoggerManager instance;
    return instance;
}

void LoggerManager::initialize()
{
    if (m_initialized) {
        return;
    }

    PathUtils::ensureRuntimeDirectories();
    m_initialized = true;
    logInfo(QStringLiteral("Logger initialized"));
}

void LoggerManager::logInfo(const QString &message)
{
    write(QStringLiteral("INFO"), message);
}

void LoggerManager::logWarning(const QString &message)
{
    write(QStringLiteral("WARN"), message);
}

void LoggerManager::logError(const QString &message)
{
    write(QStringLiteral("ERROR"), message);
}

void LoggerManager::write(const QString &level, const QString &message)
{
    const QString timestamp = QDateTime::currentDateTime().toString(Qt::ISODate);
    const QString line = QStringLiteral("[%1] [%2] %3").arg(timestamp, level, message);

    QFile file(PathUtils::logsDirPath() + QStringLiteral("/DahuaManager.log"));
    if (file.open(QIODevice::Append | QIODevice::Text)) {
        QTextStream stream(&file);
        stream << line << Qt::endl;
    }

    emit messageLogged(level, line);
}
