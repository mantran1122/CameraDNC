#include "src/utils/pathutils.h"

#include <QCoreApplication>
#include <QDir>

namespace
{
QString resolveRootPath()
{
    QDir dir(QCoreApplication::applicationDirPath());
    while (dir.exists() && !dir.exists(QStringLiteral("CMakeLists.txt"))) {
        if (!dir.cdUp()) {
            break;
        }
    }
    return dir.absolutePath();
}
}

QString PathUtils::appRootPath()
{
    return resolveRootPath();
}

QString PathUtils::configDirPath()
{
    return QDir(appRootPath()).filePath(QStringLiteral("config"));
}

QString PathUtils::logsDirPath()
{
    return QDir(appRootPath()).filePath(QStringLiteral("logs"));
}

QString PathUtils::outputDirPath()
{
    return QDir(appRootPath()).filePath(QStringLiteral("output"));
}

QString PathUtils::downloadDirPath()
{
    return QDir(outputDirPath()).filePath(QStringLiteral("download"));
}

QString PathUtils::snapshotDirPath()
{
    return QDir(outputDirPath()).filePath(QStringLiteral("snapshot"));
}

QString PathUtils::exportDirPath()
{
    return QDir(outputDirPath()).filePath(QStringLiteral("export"));
}

void PathUtils::ensureRuntimeDirectories()
{
    QDir().mkpath(configDirPath());
    QDir().mkpath(logsDirPath());
    QDir().mkpath(downloadDirPath());
    QDir().mkpath(snapshotDirPath());
    QDir().mkpath(exportDirPath());
}
