#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QString>
#include <QVector>

class QListWidget;
class QListWidgetItem;
class QLineEdit;
class QPushButton;
class QLabel;
class QPlainTextEdit;

struct DemoInfo {
    QString name;     // ten hien thi, vi du "01. RealPlayAndPTZControl"
    QString exePath;  // duong dan day du toi file .exe
    QString workDir;  // thu muc chua exe (de nap DLL cua SDK)
};

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);

private slots:
    void filterList(const QString &text);
    void launchSelected();
    void launchItem(QListWidgetItem *item);
    void openDemoFolder();
    void rescan();

private:
    void scanDemos();
    void populateList();
    void launchDemo(const DemoInfo &demo);
    void log(const QString &message);

    QString m_demoRoot;
    QVector<DemoInfo> m_demos;

    QLineEdit *m_searchEdit;
    QListWidget *m_listWidget;
    QPushButton *m_runButton;
    QPushButton *m_openFolderButton;
    QPushButton *m_rescanButton;
    QLabel *m_statusLabel;
    QPlainTextEdit *m_logView;
};

#endif // MAINWINDOW_H
