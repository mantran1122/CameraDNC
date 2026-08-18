#ifndef PATHUTILS_H
#define PATHUTILS_H

#include <QString>

namespace PathUtils
{
QString appRootPath();
QString configDirPath();
QString logsDirPath();
QString outputDirPath();
QString downloadDirPath();
QString snapshotDirPath();
QString exportDirPath();
void ensureRuntimeDirectories();
}

#endif // PATHUTILS_H
