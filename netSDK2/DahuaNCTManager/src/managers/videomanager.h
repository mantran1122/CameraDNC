#ifndef VIDEOMANAGER_H
#define VIDEOMANAGER_H

#include <QObject>

class VideoManager : public QObject
{
    Q_OBJECT

public:
    explicit VideoManager(QObject *parent = nullptr);

    bool startLive(quintptr renderHandle, int channel = 0, int renderWidth = 0, int renderHeight = 0);
    void stopLive();
    void stopLive(quintptr renderHandle);
    void setPreviewFillMode(bool enabled);
    bool isPreviewing() const;

signals:
    void liveStateChanged(bool active, const QString &message);
};

#endif // VIDEOMANAGER_H
