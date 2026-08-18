#ifndef DOWNLOADTASK_H
#define DOWNLOADTASK_H

#include <QDateTime>
#include <QString>

struct DownloadTask
{
    int channel = 0;
    QDateTime startTime;
    QDateTime endTime;
    QString filePath;

    bool isValid() const
    {
        return !filePath.trimmed().isEmpty()
            && startTime.isValid()
            && endTime.isValid()
            && startTime < endTime;
    }
};

#endif // DOWNLOADTASK_H
