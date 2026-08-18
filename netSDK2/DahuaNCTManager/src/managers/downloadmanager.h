#ifndef DOWNLOADMANAGER_H
#define DOWNLOADMANAGER_H

#include "src/models/downloadtask.h"

#include <QObject>

class DownloadManager : public QObject
{
    Q_OBJECT

public:
    explicit DownloadManager(QObject *parent = nullptr);

    bool downloadByTime(const DownloadTask &task);
    void stopDownload();
    bool isDownloading() const;

signals:
    void downloadProgressChanged(int progress);
    void downloadStateChanged(bool active, const QString &message);
};

#endif // DOWNLOADMANAGER_H
