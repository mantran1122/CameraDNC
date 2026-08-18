#ifndef LOGGERMANAGER_H
#define LOGGERMANAGER_H

#include <QObject>

class LoggerManager : public QObject
{
    Q_OBJECT

public:
    static LoggerManager &instance();

    void initialize();
    void logInfo(const QString &message);
    void logWarning(const QString &message);
    void logError(const QString &message);

signals:
    void messageLogged(const QString &level, const QString &message);

private:
    explicit LoggerManager(QObject *parent = nullptr);
    void write(const QString &level, const QString &message);

    bool m_initialized = false;
};

#endif // LOGGERMANAGER_H
