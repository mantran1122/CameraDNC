#ifndef DAHUAMANAGER_MAINWINDOW_H
#define DAHUAMANAGER_MAINWINDOW_H

#include <QMainWindow>
#include <QVector>

class QAction;
class AppController;
class QButtonGroup;
class QDockWidget;
class QFrame;
class QGridLayout;
class QLabel;
class QListWidget;
class QListWidgetItem;
class QPlainTextEdit;
class QDateTimeEdit;
class QProgressBar;
class QPushButton;
class QSplitter;
class QTabWidget;
class QTimer;
class QToolButton;
class QTreeWidget;
class QWidget;
class PreviewHost;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);
    ~MainWindow() override;

private slots:
    void openLoginDialog();
    void handleLogout();
    void toggleLive();
    void handleChannelActivated(QListWidgetItem *item);
    void handleDeviceContextMenu(const QPoint &position);
    void handleLiveLayoutChanged();
    void startDownload();
    void stopDownload();
    void toggleBottomPanel();
    void cyclePreviewDisplayMode();
    void appendLog(const QString &level, const QString &message);
    void updateConnectionState(bool connected, const QString &message);
    void updateLiveState(bool active, const QString &message);
    void updateDownloadState(bool active, const QString &message);
    void updateDownloadProgress(int progress);

private:
    enum class PreviewDisplayMode
    {
        Fit,
        Fill
    };

    void buildUi();
    void buildToolbar();
    void buildCentralLayout();
    void buildDeviceDock();
    void buildStatusBar();
    void buildLivePanel(QWidget *parent);
    void buildBottomPanels(QWidget *parent);
    void createLiveTiles();
    void refreshDeviceTree();
    void refreshChannelList();
    void refreshLiveTileLabels();
    void refreshPreviewSurfaceVisibility();
    void stopLiveTile(int index);
    void restartLiveTile(int index);
    void applyPreviewDisplayMode();
    void toggleTileFullscreen(int index);
    void enterTileFullscreen(int index);
    void exitTileFullscreen();
    int currentSelectedChannel() const;
    void selectLiveTarget(int index);
    void setStatusIndicator(QLabel *label, const QString &text, const QString &color);

    AppController *m_appController = nullptr;
    QDockWidget *m_deviceDock = nullptr;
    QSplitter *m_contentSplitter = nullptr;
    QTreeWidget *m_deviceTree = nullptr;
    QListWidget *m_channelList = nullptr;
    QTabWidget *m_bottomTabs = nullptr;
    QPlainTextEdit *m_logView = nullptr;
    QDateTimeEdit *m_downloadStartEdit = nullptr;
    QDateTimeEdit *m_downloadEndEdit = nullptr;
    QProgressBar *m_downloadProgressBar = nullptr;
    QLabel *m_connectionLabel = nullptr;
    QLabel *m_modeLabel = nullptr;
    QLabel *m_fpsLabel = nullptr;
    QLabel *m_liveSelectionLabel = nullptr;
    QLabel *m_liveHintLabel = nullptr;
    QLabel *m_previewModeLabel = nullptr;
    QLabel *m_downloadPathLabel = nullptr;
    QLabel *m_downloadStateLabel = nullptr;
    QToolButton *m_bottomPanelToggleButton = nullptr;
    QPushButton *m_previewModeButton = nullptr;
    QButtonGroup *m_liveLayoutGroup = nullptr;
    QGridLayout *m_liveGridLayout = nullptr;
    QVector<QFrame *> m_liveTiles;
    QVector<PreviewHost *> m_liveRenderSurfaces;
    QVector<QLabel *> m_liveTileLabels;
    QVector<QPushButton *> m_liveTileStopButtons;
    QVector<QTimer *> m_liveTileRestartTimers;
    QVector<int> m_liveTileChannels;
    int m_activeLiveTileIndex = 0;
    int m_currentLiveChannel = -1;
    int m_expandedBottomPanelHeight = 260;
    bool m_bottomPanelCollapsed = false;
    bool m_tileFullscreenActive = false;
    bool m_windowWasMaximized = false;
    int m_fullscreenTileIndex = -1;
    int m_fullscreenRestoreLayout = 4;
    PreviewDisplayMode m_previewDisplayMode = PreviewDisplayMode::Fill;
    QAction *m_loginAction = nullptr;
    QAction *m_logoutAction = nullptr;
    QAction *m_liveAction = nullptr;
    QAction *m_playbackAction = nullptr;
    QAction *m_snapshotAction = nullptr;
    QAction *m_downloadAction = nullptr;
    QAction *m_settingsAction = nullptr;
    QPushButton *m_startDownloadButton = nullptr;
    QPushButton *m_stopDownloadButton = nullptr;
};

#endif // DAHUAMANAGER_MAINWINDOW_H
