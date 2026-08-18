#include "src/widgets/mainwindow.h"

#include "src/controllers/appcontroller.h"
#include "src/dialogs/logindialog.h"
#include "src/managers/loggermanager.h"
#include "src/models/downloadtask.h"
#include "src/widgets/previewhost.h"

#include <QAction>
#include <QAbstractButton>
#include <QButtonGroup>
#include <QDateTime>
#include <QDateTimeEdit>
#include <QDockWidget>
#include <QFrame>
#include <QGridLayout>
#include <QHeaderView>
#include <QHBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QListWidgetItem>
#include <QMenu>
#include <QMessageBox>
#include <QMouseEvent>
#include <QPlainTextEdit>
#include <QProgressBar>
#include <QPushButton>
#include <QScrollArea>
#include <QSplitter>
#include <QStatusBar>
#include <QTabWidget>
#include <QTextEdit>
#include <QTimer>
#include <QToolBar>
#include <QToolButton>
#include <QTreeWidget>
#include <QTreeWidgetItem>
#include <QVBoxLayout>
#include <QWidget>

#include <functional>
#include <utility>

namespace {

class LiveTileFrame : public QFrame
{
public:
    explicit LiveTileFrame(QWidget *parent = nullptr)
        : QFrame(parent)
    {
    }

    std::function<void()> onClick;
    std::function<void()> onDoubleClick;

protected:
    void mousePressEvent(QMouseEvent *event) override
    {
        if (event->button() == Qt::LeftButton && onClick) {
            onClick();
        }
        QFrame::mousePressEvent(event);
    }

    void mouseDoubleClickEvent(QMouseEvent *event) override
    {
        if (event->button() == Qt::LeftButton && onDoubleClick) {
            onDoubleClick();
            event->accept();
            return;
        }

        QFrame::mouseDoubleClickEvent(event);
    }
};

QString tileTextForChannel(int channelIndex)
{
    return QStringLiteral("TILE %1\nWaiting for channel assignment")
        .arg(channelIndex + 1);
}

QString buildDownloadFilePath(const QString &basePath, int channel)
{
    const QString stamp = QDateTime::currentDateTime().toString(QStringLiteral("yyyyMMdd_HHmmss"));
    return QStringLiteral("%1/channel_%2_%3.dav")
        .arg(basePath)
        .arg(channel + 1)
        .arg(stamp);
}

} // namespace

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , m_appController(new AppController(this))
{
    buildUi();

    connect(&LoggerManager::instance(), &LoggerManager::messageLogged,
            this, &MainWindow::appendLog);
    connect(m_appController, &AppController::statusChanged,
            this, &MainWindow::updateConnectionState);
    connect(m_appController, &AppController::liveStateChanged,
            this, &MainWindow::updateLiveState);
    connect(m_appController, &AppController::downloadStateChanged,
            this, &MainWindow::updateDownloadState);
    connect(m_appController, &AppController::downloadProgressChanged,
            this, &MainWindow::updateDownloadProgress);

    m_appController->initialize();
    refreshDeviceTree();
    refreshChannelList();
    updateConnectionState(false, QStringLiteral("Ready"));
}

MainWindow::~MainWindow() = default;

void MainWindow::openLoginDialog()
{
    LoginDialog dialog(m_appController->defaultDevice(), this);
    if (dialog.exec() != QDialog::Accepted) {
        return;
    }

    const DeviceConnectionInfo info = dialog.connectionInfo();
    if (!info.isValid()) {
        appendLog(QStringLiteral("warning"), QStringLiteral("Host and username are required before login."));
        statusBar()->showMessage(QStringLiteral("Missing device connection settings"), 5000);
        return;
    }

    const bool success = m_appController->login(info);
    refreshDeviceTree();
    refreshChannelList();
    if (!success) {
        QMessageBox::warning(this, QStringLiteral("Login failed"),
                             QStringLiteral("Unable to connect to the Dahua device. Check the log panel for details."));
    }
}

void MainWindow::handleLogout()
{
    m_appController->stopLive();
    std::fill(m_liveTileChannels.begin(), m_liveTileChannels.end(), -1);
    m_currentLiveChannel = -1;
    m_appController->logout();
    refreshDeviceTree();
    refreshChannelList();
    refreshPreviewSurfaceVisibility();
}

void MainWindow::toggleLive()
{
    if (m_appController->isPreviewing()) {
        m_appController->stopLive();
        std::fill(m_liveTileChannels.begin(), m_liveTileChannels.end(), -1);
        m_currentLiveChannel = -1;
        refreshPreviewSurfaceVisibility();
        return;
    }

    if (!m_appController->isLoggedIn()) {
        statusBar()->showMessage(QStringLiteral("Please login to a device before starting live view."), 5000);
        appendLog(QStringLiteral("info"), QStringLiteral("Live view request ignored because no device is logged in."));
        return;
    }

    if (m_liveTiles.isEmpty()) {
        return;
    }

    m_currentLiveChannel = currentSelectedChannel();
    PreviewHost *renderSurface = m_liveRenderSurfaces.at(m_activeLiveTileIndex);
    if (m_appController->startLive(renderSurface->renderHandle(),
                                   m_currentLiveChannel,
                                   renderSurface->width(),
                                   renderSurface->height())) {
        m_liveTileChannels[m_activeLiveTileIndex] = m_currentLiveChannel;
    }
    refreshPreviewSurfaceVisibility();
}

void MainWindow::handleChannelActivated(QListWidgetItem *item)
{
    if (item == nullptr) {
        return;
    }

    if (!m_appController->isLoggedIn()) {
        statusBar()->showMessage(QStringLiteral("Select a device and login before opening a channel."), 5000);
        return;
    }

    const int channel = item->data(Qt::UserRole).toInt();
    m_currentLiveChannel = channel;
    PreviewHost *renderSurface = m_liveRenderSurfaces.at(m_activeLiveTileIndex);
    if (m_appController->startLive(renderSurface->renderHandle(),
                                   channel,
                                   renderSurface->width(),
                                   renderSurface->height())) {
        m_liveTileChannels[m_activeLiveTileIndex] = channel;
    }
    refreshPreviewSurfaceVisibility();
    appendLog(QStringLiteral("info"),
              QStringLiteral("Opening live channel %1 on tile %2.")
                  .arg(channel + 1)
                  .arg(m_activeLiveTileIndex + 1));
}

void MainWindow::handleDeviceContextMenu(const QPoint &position)
{
    QMenu menu(this);
    menu.addAction(m_loginAction);
    menu.addAction(m_liveAction);
    menu.addSeparator();
    menu.addAction(m_logoutAction);
    menu.exec(m_deviceTree->viewport()->mapToGlobal(position));
}

void MainWindow::handleLiveLayoutChanged()
{
    if (m_liveLayoutGroup == nullptr) {
        return;
    }

    if (m_tileFullscreenActive) {
        exitTileFullscreen();
    }

    const int tileCount = m_liveLayoutGroup->checkedId();
    for (int index = 0; index < m_liveTiles.size(); ++index) {
        m_liveTiles.at(index)->setVisible(index < tileCount);
    }

    bool hiddenTileWasStreaming = false;
    for (int index = tileCount; index < m_liveTileChannels.size(); ++index) {
        if (m_liveTileChannels.at(index) >= 0) {
            hiddenTileWasStreaming = true;
            stopLiveTile(index);
        }
    }

    if (m_modeLabel != nullptr) {
        m_modeLabel->setText(QStringLiteral("%1-up layout").arg(tileCount));
    }
    if (hiddenTileWasStreaming) {
        appendLog(QStringLiteral("info"), QStringLiteral("Stopped hidden live tiles after layout change."));
    }
    statusBar()->showMessage(QStringLiteral("Switched live layout to %1 view(s).").arg(tileCount), 3000);
    selectLiveTarget(qMin(m_activeLiveTileIndex, tileCount - 1));
    refreshPreviewSurfaceVisibility();
}

void MainWindow::appendLog(const QString &level, const QString &message)
{
    const QString prefix = level.trimmed().isEmpty()
                               ? QStringLiteral("[INFO]")
                               : QStringLiteral("[%1]").arg(level.trimmed().toUpper());
    m_logView->appendPlainText(QStringLiteral("%1 %2").arg(prefix, message));
}

void MainWindow::startDownload()
{
    if (!m_appController->isLoggedIn()) {
        statusBar()->showMessage(QStringLiteral("Login to a device before starting a download."), 4000);
        return;
    }

    DownloadTask task;
    task.channel = currentSelectedChannel();
    task.startTime = m_downloadStartEdit->dateTime();
    task.endTime = m_downloadEndEdit->dateTime();
    task.filePath = buildDownloadFilePath(m_appController->downloadPath(), task.channel);

    if (!task.isValid()) {
        appendLog(QStringLiteral("warning"), QStringLiteral("Invalid download range. End time must be later than start time."));
        statusBar()->showMessage(QStringLiteral("Invalid download range."), 4000);
        return;
    }

    if (m_appController->downloadByTime(task)) {
        m_downloadPathLabel->setText(QStringLiteral("Output: %1").arg(task.filePath));
        m_downloadProgressBar->setValue(0);
    }
}

void MainWindow::stopDownload()
{
    m_appController->stopDownload();
}

void MainWindow::cyclePreviewDisplayMode()
{
    m_previewDisplayMode = m_previewDisplayMode == PreviewDisplayMode::Fit
        ? PreviewDisplayMode::Fill
        : PreviewDisplayMode::Fit;
    applyPreviewDisplayMode();

    for (int index = 0; index < m_liveTileChannels.size() && index < m_liveRenderSurfaces.size(); ++index) {
        const int channel = m_liveTileChannels.at(index);
        if (channel < 0) {
            continue;
        }

        m_appController->stopLive(m_liveRenderSurfaces.at(index)->renderHandle());
        PreviewHost *renderSurface = m_liveRenderSurfaces.at(index);
        if (m_appController->startLive(renderSurface->renderHandle(),
                                       channel,
                                       renderSurface->width(),
                                       renderSurface->height())) {
            m_liveTileChannels[index] = channel;
        } else {
            m_liveTileChannels[index] = -1;
        }
    }

    refreshLiveTileLabels();
    refreshPreviewSurfaceVisibility();
}

void MainWindow::toggleBottomPanel()
{
    if (m_contentSplitter == nullptr || m_bottomTabs == nullptr || m_bottomPanelToggleButton == nullptr) {
        return;
    }

    QList<int> sizes = m_contentSplitter->sizes();
    if (sizes.size() < 2) {
        return;
    }

    if (m_bottomPanelCollapsed) {
        sizes[1] = qMax(220, m_expandedBottomPanelHeight);
        sizes[0] = qMax(200, m_contentSplitter->height() - sizes[1]);
        m_bottomTabs->show();
        m_bottomPanelToggleButton->setArrowType(Qt::DownArrow);
        m_bottomPanelToggleButton->setToolTip(QStringLiteral("Collapse workspace"));
        m_bottomPanelCollapsed = false;
    } else {
        m_expandedBottomPanelHeight = qMax(180, sizes[1]);
        sizes[1] = 48;
        sizes[0] = qMax(200, m_contentSplitter->height() - sizes[1]);
        m_bottomTabs->hide();
        m_bottomPanelToggleButton->setArrowType(Qt::UpArrow);
        m_bottomPanelToggleButton->setToolTip(QStringLiteral("Expand workspace"));
        m_bottomPanelCollapsed = true;
    }

    m_contentSplitter->setSizes(sizes);
}

void MainWindow::updateConnectionState(bool connected, const QString &message)
{
    setStatusIndicator(m_connectionLabel,
                       connected ? QStringLiteral("Connected") : QStringLiteral("Disconnected"),
                       connected ? QStringLiteral("#22C55E") : QStringLiteral("#EF4444"));
    statusBar()->showMessage(message, 5000);
    m_logoutAction->setEnabled(connected);
    m_liveAction->setEnabled(connected);
    m_playbackAction->setEnabled(connected);
    m_snapshotAction->setEnabled(connected);
    m_downloadAction->setEnabled(connected);
    refreshDeviceTree();
    refreshChannelList();
}

void MainWindow::updateLiveState(bool active, const QString &message)
{
    const bool anyPreviewRunning = active || m_appController->isPreviewing();
    m_liveAction->setText(anyPreviewRunning ? QStringLiteral("Stop Live") : QStringLiteral("Live"));
    m_modeLabel->setText(anyPreviewRunning ? QStringLiteral("Live running") : QStringLiteral("Standby"));
    m_fpsLabel->setText(anyPreviewRunning ? QStringLiteral("FPS 25") : QStringLiteral("FPS --"));

    if (!active && !m_appController->isPreviewing()) {
        std::fill(m_liveTileChannels.begin(), m_liveTileChannels.end(), -1);
        m_currentLiveChannel = -1;
    }
    refreshLiveTileLabels();
    refreshPreviewSurfaceVisibility();

    statusBar()->showMessage(message, 5000);
}

void MainWindow::updateDownloadState(bool active, const QString &message)
{
    if (m_downloadStateLabel != nullptr) {
        m_downloadStateLabel->setText(active ? QStringLiteral("Download active") : QStringLiteral("Download idle"));
    }
    if (m_startDownloadButton != nullptr) {
        m_startDownloadButton->setEnabled(!active);
    }
    if (m_stopDownloadButton != nullptr) {
        m_stopDownloadButton->setEnabled(active);
    }
    if (!active && m_downloadProgressBar != nullptr && m_downloadProgressBar->value() < 100) {
        m_downloadProgressBar->setValue(0);
    }
    statusBar()->showMessage(message, 5000);
}

void MainWindow::updateDownloadProgress(int progress)
{
    if (m_downloadProgressBar != nullptr) {
        m_downloadProgressBar->setValue(progress);
    }
}

void MainWindow::buildUi()
{
    resize(1440, 900);
    setMinimumSize(1180, 760);
    setWindowTitle(QStringLiteral("DahuaManager"));
    setDockOptions(QMainWindow::AnimatedDocks | QMainWindow::AllowTabbedDocks);
    setStyleSheet(QStringLiteral(
        "QMainWindow { background: #07111F; color: #E6EEF8; }"
        "QWidget { color: #EAF2FF; font-size: 14px; selection-background-color: #2563EB; selection-color: white; }"
        "QWidget#centralSurface { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #081221, stop:0.55 #0B1527, stop:1 #0F1B31); }"
        "QToolBar { background: rgba(7, 17, 31, 0.92); border: 1px solid #14233B; border-radius: 14px; spacing: 8px; padding: 10px 12px; }"
        "QToolButton { background: #132238; color: #F8FBFF; border: 1px solid #2B4770; border-radius: 10px; padding: 8px 14px; font-weight: 600; }"
        "QToolButton:hover { background: #1A2F4B; border-color: #345887; }"
        "QToolButton:pressed { background: #102136; }"
        "QDockWidget { color: #E6EEF8; }"
        "QDockWidget::title { background: #0E1A2B; color: #F4F8FF; padding: 12px; border: 1px solid #16263E; border-bottom: none; font-weight: 600; }"
        "QWidget#dockBody, QFrame#panelFrame { background: rgba(12, 22, 38, 0.96); border: 1px solid #1A2C46; border-radius: 18px; }"
        "QWidget#layoutSelector { background: rgba(8, 18, 33, 0.88); border: 1px solid #1B2F4B; border-radius: 18px; }"
        "QFrame#liveInfoBar { background: rgba(9, 19, 34, 0.92); border: 1px solid #183150; border-radius: 16px; }"
        "QLabel[class='sectionTitle'] { color: #F8FBFF; font-size: 21px; font-weight: 750; }"
        "QLabel[class='eyebrow'] { color: #7DD3FC; font-size: 12px; font-weight: 800; letter-spacing: 1px; }"
        "QLabel[class='muted'] { color: #BED0E6; font-size: 14px; }"
        "QLabel[class='infoChip'] { background: #10243E; border: 1px solid #2A527C; border-radius: 12px; color: #F1F7FF; padding: 8px 12px; font-weight: 600; }"
        "QTreeWidget, QListWidget, QPlainTextEdit, QTextEdit, QTabWidget::pane, QDateTimeEdit, QAbstractSpinBox { background: #091321; border: 1px solid #244264; border-radius: 14px; color: #F7FBFF; }"
        "QTreeWidget::item, QListWidget::item { padding: 8px; }"
        "QTreeWidget::item:hover, QListWidget::item:hover { background: rgba(37, 99, 235, 0.16); }"
        "QTreeWidget::item:selected, QListWidget::item:selected { background: #16365C; color: white; border-radius: 8px; }"
        "QHeaderView::section { background: #101D31; color: #E5EFFC; border: none; border-bottom: 1px solid #1D314D; padding: 9px; font-weight: 600; }"
        "QTabBar::tab { background: #101D31; color: #C5D6EA; padding: 10px 16px; margin-right: 4px; border-top-left-radius: 10px; border-top-right-radius: 10px; font-weight: 600; }"
        "QTabBar::tab:selected { background: #16365C; color: #F8FBFF; }"
        "QToolButton#panelToggleButton { background: #132238; border: 1px solid #284368; border-radius: 12px; padding: 8px; }"
        "QToolButton#panelToggleButton:hover { background: #19314D; }"
        "QPushButton { background: #132238; border: 1px solid #2D4C74; border-radius: 14px; padding: 7px 13px; color: #F7FBFF; font-weight: 600; }"
        "QPushButton:hover { background: #19314D; }"
        "QPushButton:checked { background: #1D4ED8; border-color: #60A5FA; color: white; }"
        "QFrame#liveTile { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #08111D, stop:1 #0E1B2E); border: 1px solid #28415F; border-radius: 18px; }"
        "QDateTimeEdit { min-height: 40px; padding: 6px 12px; color: #F8FBFF; font-weight: 600; selection-background-color: #2563EB; }"
        "QDateTimeEdit::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 30px; border-left: 1px solid #2B4770; }"
        "QDateTimeEdit::down-arrow { image: none; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #EAF2FF; margin-right: 8px; }"
        "QAbstractItemView { background: #0C1626; color: #F8FBFF; selection-background-color: #2563EB; selection-color: white; }"
        "QCalendarWidget QWidget { alternate-background-color: #0C1626; }"
        "QCalendarWidget QToolButton { color: #F8FBFF; background: #132238; border: 1px solid #2B4770; border-radius: 10px; padding: 8px 10px; font-weight: 700; }"
        "QCalendarWidget QMenu { background: #0C1626; color: #F8FBFF; }"
        "QCalendarWidget QSpinBox { background: #091321; color: #F8FBFF; selection-background-color: #2563EB; }"
        "QCalendarWidget QAbstractItemView:enabled { background: #0C1626; color: #EAF2FF; selection-background-color: #2563EB; selection-color: white; }"
        "QCalendarWidget QAbstractItemView:disabled { color: #7188A5; }"
        "QProgressBar { min-height: 24px; border: 1px solid #32547F; border-radius: 10px; background: #091321; color: #F8FBFF; text-align: center; font-weight: 700; }"
        "QProgressBar::chunk { background: #2563EB; border-radius: 8px; }"
        "QScrollBar:vertical { background: #0B1525; width: 12px; margin: 2px; }"
        "QScrollBar::handle:vertical { background: #284368; min-height: 30px; border-radius: 6px; }"
        "QStatusBar { background: #091321; color: #D8E6F7; border-top: 1px solid #142640; }"));

    buildToolbar();
    buildStatusBar();
    buildCentralLayout();
    buildDeviceDock();
}

void MainWindow::buildToolbar()
{
    auto *toolBar = addToolBar(QStringLiteral("Main"));
    toolBar->setMovable(false);

    m_loginAction = toolBar->addAction(QStringLiteral("Login"));
    m_logoutAction = toolBar->addAction(QStringLiteral("Logout"));
    toolBar->addSeparator();
    m_liveAction = toolBar->addAction(QStringLiteral("Live"));
    m_playbackAction = toolBar->addAction(QStringLiteral("Playback"));
    m_snapshotAction = toolBar->addAction(QStringLiteral("Snapshot"));
    m_downloadAction = toolBar->addAction(QStringLiteral("Download"));
    m_settingsAction = toolBar->addAction(QStringLiteral("Settings"));

    m_logoutAction->setEnabled(false);
    m_liveAction->setEnabled(false);
    m_playbackAction->setEnabled(false);
    m_snapshotAction->setEnabled(false);
    m_downloadAction->setEnabled(false);

    connect(m_loginAction, &QAction::triggered, this, &MainWindow::openLoginDialog);
    connect(m_logoutAction, &QAction::triggered, this, &MainWindow::handleLogout);
    connect(m_liveAction, &QAction::triggered, this, &MainWindow::toggleLive);
    connect(m_playbackAction, &QAction::triggered, this, [this]() {
        m_bottomTabs->setCurrentIndex(0);
        statusBar()->showMessage(QStringLiteral("Playback workspace ready."), 3000);
    });
    connect(m_downloadAction, &QAction::triggered, this, [this]() {
        m_bottomTabs->setCurrentIndex(0);
        statusBar()->showMessage(QStringLiteral("Download workspace ready."), 3000);
    });
    connect(m_snapshotAction, &QAction::triggered, this, [this]() {
        appendLog(QStringLiteral("info"), QStringLiteral("Snapshot action is reserved for the next SDK integration step."));
        statusBar()->showMessage(QStringLiteral("Snapshot will be wired in SDK integration."), 4000);
    });
    connect(m_settingsAction, &QAction::triggered, this, [this]() {
        appendLog(QStringLiteral("info"), QStringLiteral("Settings panel is not implemented yet."));
        statusBar()->showMessage(QStringLiteral("Settings panel is coming next."), 4000);
    });
}

void MainWindow::buildCentralLayout()
{
    auto *centralWidget = new QWidget(this);
    centralWidget->setObjectName(QStringLiteral("centralSurface"));
    auto *rootLayout = new QVBoxLayout(centralWidget);
    rootLayout->setContentsMargins(10, 10, 10, 10);
    rootLayout->setSpacing(10);

    m_contentSplitter = new QSplitter(Qt::Vertical, centralWidget);
    m_contentSplitter->setChildrenCollapsible(false);
    m_contentSplitter->setHandleWidth(10);

    auto *livePanel = new QFrame(m_contentSplitter);
    livePanel->setObjectName(QStringLiteral("panelFrame"));
    auto *liveLayout = new QVBoxLayout(livePanel);
    liveLayout->setContentsMargins(14, 14, 14, 14);
    liveLayout->setSpacing(12);
    buildLivePanel(livePanel);

    auto *bottomPanel = new QWidget(m_contentSplitter);
    buildBottomPanels(bottomPanel);

    m_contentSplitter->addWidget(livePanel);
    m_contentSplitter->addWidget(bottomPanel);
    m_contentSplitter->setStretchFactor(0, 3);
    m_contentSplitter->setStretchFactor(1, 2);
    m_contentSplitter->setSizes({560, 260});

    rootLayout->addWidget(m_contentSplitter);
    setCentralWidget(centralWidget);
}

void MainWindow::buildDeviceDock()
{
    m_deviceDock = new QDockWidget(QStringLiteral("Devices"), this);
    m_deviceDock->setAllowedAreas(Qt::LeftDockWidgetArea | Qt::RightDockWidgetArea);
    m_deviceDock->setFeatures(QDockWidget::DockWidgetClosable | QDockWidget::DockWidgetMovable);

    auto *dockBody = new QWidget(m_deviceDock);
    dockBody->setObjectName(QStringLiteral("dockBody"));
    auto *dockLayout = new QVBoxLayout(dockBody);
    dockLayout->setContentsMargins(14, 14, 14, 14);
    dockLayout->setSpacing(12);

    auto *eyebrowLabel = new QLabel(QStringLiteral("DEVICE HUB"), dockBody);
    eyebrowLabel->setProperty("class", "eyebrow");
    auto *deviceLabel = new QLabel(QStringLiteral("Device Tree"), dockBody);
    deviceLabel->setProperty("class", "sectionTitle");

    m_deviceTree = new QTreeWidget(dockBody);
    m_deviceTree->setColumnCount(2);
    m_deviceTree->setHeaderLabels({QStringLiteral("Item"), QStringLiteral("Value")});
    m_deviceTree->header()->setSectionResizeMode(0, QHeaderView::ResizeToContents);
    m_deviceTree->header()->setSectionResizeMode(1, QHeaderView::Stretch);
    m_deviceTree->setTextElideMode(Qt::ElideNone);
    m_deviceTree->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    m_deviceTree->setContextMenuPolicy(Qt::CustomContextMenu);

    auto *channelLabel = new QLabel(QStringLiteral("Channels"), dockBody);
    channelLabel->setProperty("class", "sectionTitle");

    m_channelList = new QListWidget(dockBody);
    m_channelList->setSelectionMode(QAbstractItemView::SingleSelection);
    m_channelList->setAlternatingRowColors(true);

    auto *hintLabel = new QLabel(QStringLiteral("Double click a channel to open live view on the selected tile."), dockBody);
    hintLabel->setWordWrap(true);
    hintLabel->setProperty("class", "muted");

    dockLayout->addWidget(eyebrowLabel);
    dockLayout->addWidget(deviceLabel);
    dockLayout->addWidget(m_deviceTree, 3);
    dockLayout->addWidget(channelLabel);
    dockLayout->addWidget(m_channelList, 2);
    dockLayout->addWidget(hintLabel);

    connect(m_channelList, &QListWidget::itemDoubleClicked,
            this, &MainWindow::handleChannelActivated);
    connect(m_deviceTree, &QTreeWidget::customContextMenuRequested,
            this, &MainWindow::handleDeviceContextMenu);

    m_deviceDock->setWidget(dockBody);
    addDockWidget(Qt::LeftDockWidgetArea, m_deviceDock);
    resizeDocks({m_deviceDock}, {300}, Qt::Horizontal);
}

void MainWindow::buildStatusBar()
{
    m_modeLabel = new QLabel(QStringLiteral("Standby"), this);
    m_fpsLabel = new QLabel(QStringLiteral("FPS --"), this);
    m_connectionLabel = new QLabel(QStringLiteral("Disconnected"), this);
    m_modeLabel->setProperty("class", "infoChip");
    m_fpsLabel->setProperty("class", "infoChip");

    setStatusIndicator(m_connectionLabel, QStringLiteral("Disconnected"), QStringLiteral("#EF4444"));
    statusBar()->addWidget(m_modeLabel);
    statusBar()->addPermanentWidget(m_connectionLabel);
    statusBar()->addPermanentWidget(m_fpsLabel);
}

void MainWindow::buildLivePanel(QWidget *parent)
{
    auto *panelLayout = qobject_cast<QVBoxLayout *>(parent->layout());
    if (panelLayout == nullptr) {
        return;
    }

    auto *headerLayout = new QHBoxLayout();

    auto *titleBlock = new QVBoxLayout();
    auto *eyebrowLabel = new QLabel(QStringLiteral("LIVE CONTROL"), parent);
    eyebrowLabel->setProperty("class", "eyebrow");
    auto *titleLabel = new QLabel(QStringLiteral("Live View"), parent);
    titleLabel->setProperty("class", "sectionTitle");
    auto *subtitleLabel = new QLabel(QStringLiteral("Focused, low-noise monitoring layout with quick switching between 1 / 4 / 9 / 16 cameras."), parent);
    subtitleLabel->setProperty("class", "muted");
    titleBlock->addWidget(eyebrowLabel);
    titleBlock->addWidget(titleLabel);
    titleBlock->addWidget(subtitleLabel);

    auto *layoutButtons = new QHBoxLayout();
    layoutButtons->setSpacing(8);
    m_liveLayoutGroup = new QButtonGroup(this);
    const QList<int> tileOptions = {1, 4, 9, 16};
    for (const int tileOption : tileOptions) {
        auto *button = new QPushButton(QString::number(tileOption), parent);
        button->setCheckable(true);
        button->setMinimumWidth(40);
        m_liveLayoutGroup->addButton(button, tileOption);
        layoutButtons->addWidget(button);
    }
    if (auto *defaultButton = m_liveLayoutGroup->button(4)) {
        defaultButton->setChecked(true);
    }

    auto *layoutButtonsWidget = new QWidget(parent);
    layoutButtonsWidget->setObjectName(QStringLiteral("layoutSelector"));
    layoutButtonsWidget->setLayout(layoutButtons);

    headerLayout->addLayout(titleBlock, 1);
    headerLayout->addWidget(layoutButtonsWidget, 0, Qt::AlignRight | Qt::AlignTop);

    auto *infoBar = new QFrame(parent);
    infoBar->setObjectName(QStringLiteral("liveInfoBar"));
    auto *infoBarLayout = new QHBoxLayout(infoBar);
    infoBarLayout->setContentsMargins(14, 12, 14, 12);
    infoBarLayout->setSpacing(10);

    m_liveSelectionLabel = new QLabel(QStringLiteral("Selected tile: 1"), infoBar);
    m_liveSelectionLabel->setProperty("class", "infoChip");
    m_liveHintLabel = new QLabel(QStringLiteral("Tip: double click a channel on the left to send it into the selected tile."), infoBar);
    m_liveHintLabel->setProperty("class", "infoChip");
    m_previewModeLabel = new QLabel(QStringLiteral("Preview mode: Fill"), infoBar);
    m_previewModeLabel->setProperty("class", "infoChip");
    m_previewModeButton = new QPushButton(QStringLiteral("Switch to Fit"), infoBar);
    m_previewModeButton->setMinimumHeight(36);

    infoBarLayout->addWidget(m_liveSelectionLabel);
    infoBarLayout->addWidget(m_liveHintLabel, 1);
    infoBarLayout->addWidget(m_previewModeLabel);
    infoBarLayout->addWidget(m_previewModeButton);

    auto *gridHost = new QWidget(parent);
    m_liveGridLayout = new QGridLayout(gridHost);
    m_liveGridLayout->setContentsMargins(0, 0, 0, 0);
    m_liveGridLayout->setHorizontalSpacing(12);
    m_liveGridLayout->setVerticalSpacing(12);

    createLiveTiles();

    panelLayout->addLayout(headerLayout);
    panelLayout->addWidget(infoBar);
    panelLayout->addWidget(gridHost, 1);

    connect(m_liveLayoutGroup, &QButtonGroup::idClicked,
            this, &MainWindow::handleLiveLayoutChanged);
    connect(m_previewModeButton, &QPushButton::clicked,
            this, &MainWindow::cyclePreviewDisplayMode);
    applyPreviewDisplayMode();
    handleLiveLayoutChanged();
}

void MainWindow::buildBottomPanels(QWidget *parent)
{
    auto *rootLayout = new QVBoxLayout(parent);
    rootLayout->setContentsMargins(0, 0, 0, 0);
    rootLayout->setSpacing(8);

    auto *headerLayout = new QHBoxLayout();
    auto *headerLabel = new QLabel(QStringLiteral("Workspace"), parent);
    headerLabel->setProperty("class", "sectionTitle");
    m_bottomPanelToggleButton = new QToolButton(parent);
    m_bottomPanelToggleButton->setObjectName(QStringLiteral("panelToggleButton"));
    m_bottomPanelToggleButton->setArrowType(Qt::DownArrow);
    m_bottomPanelToggleButton->setToolTip(QStringLiteral("Collapse workspace"));
    m_bottomPanelToggleButton->setAutoRaise(false);

    headerLayout->addWidget(headerLabel);
    headerLayout->addStretch(1);
    headerLayout->addWidget(m_bottomPanelToggleButton);

    auto *playbackPanel = new QFrame(parent);
    playbackPanel->setObjectName(QStringLiteral("panelFrame"));
    auto *playbackLayout = new QVBoxLayout(playbackPanel);
    playbackLayout->setContentsMargins(14, 14, 14, 14);
    playbackLayout->setSpacing(12);

    auto *playbackTitle = new QLabel(QStringLiteral("Download / Playback"), playbackPanel);
    playbackTitle->setProperty("class", "sectionTitle");
    auto *playbackEyebrow = new QLabel(QStringLiteral("REVIEW"), playbackPanel);
    playbackEyebrow->setProperty("class", "eyebrow");

    auto *playbackDescription = new QLabel(
        QStringLiteral("SDK download integration is active here.\n\n"
                       "Use the selected channel from the left panel, choose a time range, then start download."),
        playbackPanel);
    playbackDescription->setWordWrap(true);
    playbackDescription->setProperty("class", "muted");

    auto *downloadControls = new QGridLayout();
    downloadControls->setHorizontalSpacing(12);
    downloadControls->setVerticalSpacing(12);
    downloadControls->setColumnStretch(1, 1);
    downloadControls->setColumnStretch(3, 1);

    auto *startLabel = new QLabel(QStringLiteral("Start"), playbackPanel);
    auto *endLabel = new QLabel(QStringLiteral("End"), playbackPanel);
    m_downloadStartEdit = new QDateTimeEdit(QDateTime::currentDateTime().addSecs(-3600), playbackPanel);
    m_downloadEndEdit = new QDateTimeEdit(QDateTime::currentDateTime(), playbackPanel);
    m_downloadStartEdit->setDisplayFormat(QStringLiteral("yyyy-MM-dd HH:mm:ss"));
    m_downloadEndEdit->setDisplayFormat(QStringLiteral("yyyy-MM-dd HH:mm:ss"));
    m_downloadStartEdit->setCalendarPopup(true);
    m_downloadEndEdit->setCalendarPopup(true);

    m_startDownloadButton = new QPushButton(QStringLiteral("Start Download"), playbackPanel);
    m_stopDownloadButton = new QPushButton(QStringLiteral("Stop"), playbackPanel);
    m_startDownloadButton->setMinimumHeight(40);
    m_stopDownloadButton->setMinimumHeight(40);
    m_stopDownloadButton->setEnabled(false);
    m_downloadProgressBar = new QProgressBar(playbackPanel);
    m_downloadProgressBar->setRange(0, 100);
    m_downloadProgressBar->setValue(0);
    m_downloadProgressBar->setFormat(QStringLiteral("%p%"));

    m_downloadStateLabel = new QLabel(QStringLiteral("Download idle"), playbackPanel);
    m_downloadStateLabel->setProperty("class", "infoChip");
    m_downloadPathLabel = new QLabel(QStringLiteral("Output: %1").arg(m_appController->downloadPath()), playbackPanel);
    m_downloadPathLabel->setWordWrap(true);
    m_downloadPathLabel->setProperty("class", "muted");

    downloadControls->addWidget(startLabel, 0, 0);
    downloadControls->addWidget(m_downloadStartEdit, 0, 1);
    downloadControls->addWidget(endLabel, 0, 2);
    downloadControls->addWidget(m_downloadEndEdit, 0, 3);
    downloadControls->addWidget(m_startDownloadButton, 1, 0, 1, 2);
    downloadControls->addWidget(m_stopDownloadButton, 1, 2, 1, 2);
    downloadControls->addWidget(m_downloadProgressBar, 2, 0, 1, 4);
    downloadControls->addWidget(m_downloadStateLabel, 3, 0, 1, 2);
    downloadControls->addWidget(m_downloadPathLabel, 4, 0, 1, 4);

    playbackLayout->addWidget(playbackEyebrow);
    playbackLayout->addWidget(playbackTitle);
    playbackLayout->addWidget(playbackDescription);
    playbackLayout->addLayout(downloadControls);
    playbackLayout->addStretch(1);

    auto *playbackScrollArea = new QScrollArea(parent);
    playbackScrollArea->setWidgetResizable(true);
    playbackScrollArea->setFrameShape(QFrame::NoFrame);
    playbackScrollArea->setWidget(playbackPanel);

    auto *logPanel = new QFrame(parent);
    logPanel->setObjectName(QStringLiteral("panelFrame"));
    auto *logLayout = new QVBoxLayout(logPanel);
    logLayout->setContentsMargins(14, 14, 14, 14);
    logLayout->setSpacing(10);

    auto *logTitle = new QLabel(QStringLiteral("Log Window"), logPanel);
    logTitle->setProperty("class", "sectionTitle");
    auto *logEyebrow = new QLabel(QStringLiteral("SYSTEM"), logPanel);
    logEyebrow->setProperty("class", "eyebrow");

    m_logView = new QPlainTextEdit(logPanel);
    m_logView->setReadOnly(true);
    m_logView->setPlaceholderText(QStringLiteral("System events, connection states, and SDK messages appear here."));

    logLayout->addWidget(logEyebrow);
    logLayout->addWidget(logTitle);
    logLayout->addWidget(m_logView, 1);

    auto *logScrollArea = new QScrollArea(parent);
    logScrollArea->setWidgetResizable(true);
    logScrollArea->setFrameShape(QFrame::NoFrame);
    logScrollArea->setWidget(logPanel);

    m_bottomTabs = new QTabWidget(parent);
    m_bottomTabs->addTab(playbackScrollArea, QStringLiteral("Playback"));
    m_bottomTabs->addTab(logScrollArea, QStringLiteral("Logs"));

    rootLayout->addLayout(headerLayout);
    rootLayout->addWidget(m_bottomTabs, 1);

    connect(m_startDownloadButton, &QPushButton::clicked, this, &MainWindow::startDownload);
    connect(m_stopDownloadButton, &QPushButton::clicked, this, &MainWindow::stopDownload);
    connect(m_bottomPanelToggleButton, &QToolButton::clicked, this, &MainWindow::toggleBottomPanel);
}

void MainWindow::createLiveTiles()
{
    for (int index = 0; index < 16; ++index) {
        auto *tile = new LiveTileFrame(this);
        tile->setObjectName(QStringLiteral("liveTile"));
        tile->setMinimumSize(170, 110);
        tile->setProperty("tileIndex", index);
        tile->setMinimumHeight(126);
        tile->setFrameShape(QFrame::StyledPanel);

        auto *tileLayout = new QVBoxLayout(tile);
        tileLayout->setContentsMargins(16, 16, 16, 16);
        tileLayout->setSpacing(10);

        auto *titleLabel = new QLabel(QStringLiteral("TILE %1").arg(index + 1), tile);
        titleLabel->setStyleSheet(QStringLiteral("color: #EAF2FF; font-size: 15px; font-weight: 700;"));

        auto *previewFrame = new QFrame(tile);
        previewFrame->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
        previewFrame->setStyleSheet(QStringLiteral(
            "background: #050B14; border: 1px solid #20324A; border-radius: 10px;"));
        auto *previewLayout = new QVBoxLayout(previewFrame);
        previewLayout->setContentsMargins(0, 0, 0, 0);
        previewLayout->setSpacing(0);

        auto *renderSurface = new PreviewHost(previewFrame);
        renderSurface->setMinimumSize(0, 0);
        renderSurface->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
        previewLayout->addWidget(renderSurface);

        auto *statusLabel = new QLabel(tileTextForChannel(index), tile);
        statusLabel->setWordWrap(true);
        statusLabel->setStyleSheet(QStringLiteral("color: #D8E6F7; font-size: 14px; font-weight: 600;"));
        auto *stopButton = new QPushButton(QStringLiteral("Stop Tile"), tile);
        stopButton->setMinimumHeight(34);
        stopButton->setEnabled(false);

        tileLayout->addWidget(titleLabel);
        tileLayout->addWidget(previewFrame, 1);
        tileLayout->addWidget(statusLabel);
        tileLayout->addWidget(stopButton);
        tileLayout->setStretch(0, 0);
        tileLayout->setStretch(1, 1);
        tileLayout->setStretch(2, 0);

        m_liveGridLayout->addWidget(tile, index / 4, index % 4);
        m_liveTiles.append(tile);
        m_liveRenderSurfaces.append(renderSurface);
        m_liveTileLabels.append(statusLabel);
        m_liveTileStopButtons.append(stopButton);
        auto *restartTimer = new QTimer(this);
        restartTimer->setSingleShot(true);
        restartTimer->setInterval(180);
        m_liveTileRestartTimers.append(restartTimer);
        m_liveTileChannels.append(-1);
        tile->onClick = [this, index]() {
            selectLiveTarget(index);
            statusBar()->showMessage(QStringLiteral("Selected live tile %1.").arg(index + 1), 2000);
        };
        tile->onDoubleClick = [this, index]() {
            toggleTileFullscreen(index);
        };
        connect(renderSurface, &PreviewHost::doubleClicked, this, [this, index]() {
            toggleTileFullscreen(index);
        });
        connect(renderSurface, &PreviewHost::hostGeometryChanged, this, [this, index]() {
            if (index < 0 || index >= m_liveTileChannels.size() || index >= m_liveTileRestartTimers.size()) {
                return;
            }

            if (m_liveTileChannels.at(index) < 0 || !m_appController->isPreviewing()) {
                return;
            }

            m_liveTileRestartTimers.at(index)->start();
        });
        connect(restartTimer, &QTimer::timeout, this, [this, index]() {
            restartLiveTile(index);
        });
        connect(stopButton, &QPushButton::clicked, this, [this, index]() {
            stopLiveTile(index);
        });
    }

    selectLiveTarget(0);
}

void MainWindow::refreshDeviceTree()
{
    if (m_deviceTree == nullptr) {
        return;
    }

    m_deviceTree->clear();

    const DeviceConnectionInfo info = m_appController->defaultDevice();
    auto *deviceItem = new QTreeWidgetItem(
        m_deviceTree,
        {info.name.isEmpty() ? QStringLiteral("Default Device") : info.name,
         info.host.isEmpty() ? QStringLiteral("Not configured") : info.host});
    new QTreeWidgetItem(deviceItem, {QStringLiteral("Port"), QString::number(info.port)});
    new QTreeWidgetItem(deviceItem, {QStringLiteral("Username"), info.username.isEmpty() ? QStringLiteral("--") : info.username});
    new QTreeWidgetItem(deviceItem, {QStringLiteral("State"), m_appController->isLoggedIn() ? QStringLiteral("Connected") : QStringLiteral("Idle")});
    deviceItem->setExpanded(true);
    m_deviceTree->resizeColumnToContents(0);
}

void MainWindow::refreshChannelList()
{
    if (m_channelList == nullptr) {
        return;
    }

    m_channelList->clear();
    const QVector<PreviewChannelInfo> previewChannels = m_appController->previewChannels();
    const int channelCount = m_appController->channelCount();

    for (const PreviewChannelInfo &channel : previewChannels) {
        auto *item = new QListWidgetItem(channel.displayName, m_channelList);
        item->setData(Qt::UserRole, channel.sdkChannel);
        item->setToolTip(QStringLiteral("Double click to open SDK channel %1 in the selected tile").arg(channel.sdkChannel));
    }

    if (previewChannels.isEmpty() && channelCount <= 0) {
        auto *hintItem = new QListWidgetItem(QStringLiteral("Preview channel count not reported by device"), m_channelList);
        hintItem->setFlags(Qt::NoItemFlags);
        hintItem->setForeground(QColor(QStringLiteral("#9FB6D4")));
    }

    if (m_channelList->count() > 0) {
        m_channelList->setCurrentRow(0);
    }
}

void MainWindow::refreshLiveTileLabels()
{
    for (int index = 0; index < m_liveTiles.size(); ++index) {
        QString text = tileTextForChannel(index);
        const bool tileStreaming = index < m_liveTileChannels.size()
            && m_liveTileChannels.at(index) >= 0
            && m_appController->isPreviewing();
        if (tileStreaming) {
            text = QStringLiteral("TILE %1\nChannel %2 streaming")
                       .arg(index + 1)
                       .arg(m_liveTileChannels.at(index) + 1);
        } else if (index == m_activeLiveTileIndex) {
            text = QStringLiteral("TILE %1\nReady for selected channel").arg(index + 1);
        }
        m_liveTileLabels.at(index)->setText(text);
        if (index < m_liveTileStopButtons.size()) {
            m_liveTileStopButtons.at(index)->setEnabled(tileStreaming);
        }
    }
}

void MainWindow::refreshPreviewSurfaceVisibility()
{
    const bool previewActive = m_appController->isPreviewing();
    for (int index = 0; index < m_liveRenderSurfaces.size(); ++index) {
        const bool shouldShow = previewActive
            && index < m_liveTileChannels.size()
            && m_liveTileChannels.at(index) >= 0
            && index < m_liveTiles.size()
            && m_liveTiles.at(index)->isVisible();
        m_liveRenderSurfaces.at(index)->setPreviewVisible(shouldShow);
    }
}

void MainWindow::stopLiveTile(int index)
{
    if (index < 0 || index >= m_liveRenderSurfaces.size() || index >= m_liveTileChannels.size()) {
        return;
    }

    if (m_liveTileChannels.at(index) < 0) {
        return;
    }

    m_appController->stopLive(m_liveRenderSurfaces.at(index)->renderHandle());
    m_liveTileChannels[index] = -1;
    if (index == m_activeLiveTileIndex) {
        m_currentLiveChannel = -1;
    }

    refreshLiveTileLabels();
    refreshPreviewSurfaceVisibility();
    statusBar()->showMessage(QStringLiteral("Stopped live tile %1.").arg(index + 1), 3000);
}

void MainWindow::restartLiveTile(int index)
{
    if (index < 0 || index >= m_liveTileChannels.size() || index >= m_liveRenderSurfaces.size()) {
        return;
    }

    const int channel = m_liveTileChannels.at(index);
    if (channel < 0) {
        return;
    }

    PreviewHost *renderSurface = m_liveRenderSurfaces.at(index);
    if (renderSurface == nullptr || !renderSurface->isVisible()) {
        return;
    }

    if (renderSurface->width() <= 1 || renderSurface->height() <= 1) {
        return;
    }

    m_appController->stopLive(renderSurface->renderHandle());
    if (!m_appController->startLive(renderSurface->renderHandle(),
                                    channel,
                                    renderSurface->width(),
                                    renderSurface->height())) {
        m_liveTileChannels[index] = -1;
    }

    refreshLiveTileLabels();
    refreshPreviewSurfaceVisibility();
}

void MainWindow::applyPreviewDisplayMode()
{
    const QString modeText = m_previewDisplayMode == PreviewDisplayMode::Fit
        ? QStringLiteral("Fit")
        : QStringLiteral("Fill");
    const QString buttonText = m_previewDisplayMode == PreviewDisplayMode::Fit
        ? QStringLiteral("Switch to Fill")
        : QStringLiteral("Switch to Fit");
    const PreviewHost::DisplayMode hostMode = m_previewDisplayMode == PreviewDisplayMode::Fit
        ? PreviewHost::DisplayMode::Fit
        : PreviewHost::DisplayMode::Fill;
    m_appController->setPreviewFillMode(m_previewDisplayMode == PreviewDisplayMode::Fill);

    for (PreviewHost *renderSurface : std::as_const(m_liveRenderSurfaces)) {
        if (renderSurface != nullptr) {
            renderSurface->setDisplayMode(hostMode);
        }
    }

    if (m_previewModeLabel != nullptr) {
        m_previewModeLabel->setText(QStringLiteral("Preview mode: %1").arg(modeText));
    }
    if (m_previewModeButton != nullptr) {
        m_previewModeButton->setText(buttonText);
    }
}

void MainWindow::toggleTileFullscreen(int index)
{
    if (m_tileFullscreenActive) {
        if (m_fullscreenTileIndex == index) {
            exitTileFullscreen();
            return;
        }

        exitTileFullscreen();
    }

    enterTileFullscreen(index);
}

void MainWindow::enterTileFullscreen(int index)
{
    if (index < 0 || index >= m_liveTiles.size()) {
        return;
    }

    m_fullscreenRestoreLayout = m_liveLayoutGroup != nullptr ? qMax(1, m_liveLayoutGroup->checkedId()) : 4;
    m_windowWasMaximized = isMaximized();
    m_fullscreenTileIndex = index;
    m_tileFullscreenActive = true;

    for (int tileIndex = 0; tileIndex < m_liveTiles.size(); ++tileIndex) {
        QFrame *tile = m_liveTiles.at(tileIndex);
        m_liveGridLayout->removeWidget(tile);
        if (tileIndex == index) {
            tile->show();
            m_liveGridLayout->addWidget(tile, 0, 0, 4, 4);
        } else {
            tile->hide();
        }
    }

    selectLiveTarget(index);
    showFullScreen();
    statusBar()->showMessage(QStringLiteral("Tile %1 entered full screen. Double click again to exit.").arg(index + 1), 4000);
}

void MainWindow::exitTileFullscreen()
{
    if (!m_tileFullscreenActive) {
        return;
    }

    m_tileFullscreenActive = false;
    m_fullscreenTileIndex = -1;

    for (int tileIndex = 0; tileIndex < m_liveTiles.size(); ++tileIndex) {
        QFrame *tile = m_liveTiles.at(tileIndex);
        m_liveGridLayout->removeWidget(tile);
        m_liveGridLayout->addWidget(tile, tileIndex / 4, tileIndex % 4);
    }

    if (m_liveLayoutGroup != nullptr) {
        if (QAbstractButton *button = m_liveLayoutGroup->button(m_fullscreenRestoreLayout)) {
            button->setChecked(true);
        }
    }

    if (isFullScreen()) {
        if (m_windowWasMaximized) {
            showMaximized();
        } else {
            showNormal();
        }
    }

    handleLiveLayoutChanged();
    statusBar()->showMessage(QStringLiteral("Exited full screen live view."), 3000);
}

int MainWindow::currentSelectedChannel() const
{
    if (m_channelList == nullptr) {
        return 0;
    }

    QListWidgetItem *currentItem = m_channelList->currentItem();
    if (currentItem == nullptr) {
        return 0;
    }

    return qMax(0, currentItem->data(Qt::UserRole).toInt());
}

void MainWindow::selectLiveTarget(int index)
{
    if (m_liveTiles.isEmpty()) {
        return;
    }

    const int safeIndex = qBound(0, index, m_liveTiles.size() - 1);
    m_activeLiveTileIndex = safeIndex;

    for (int tileIndex = 0; tileIndex < m_liveTiles.size(); ++tileIndex) {
        m_liveTiles.at(tileIndex)->setStyleSheet(QStringLiteral(
            "QFrame#liveTile { background: %1; border: 1px solid %2; border-radius: 18px; }")
                                                     .arg(tileIndex == safeIndex ? QStringLiteral("#1B365A") : QStringLiteral("rgba(12, 22, 38, 0.96)"),
                                                          tileIndex == safeIndex ? QStringLiteral("#60A5FA") : QStringLiteral("#28415F")));
    }

    if (m_liveSelectionLabel != nullptr) {
        m_liveSelectionLabel->setText(QStringLiteral("Selected tile: %1").arg(safeIndex + 1));
    }
    refreshLiveTileLabels();
    refreshPreviewSurfaceVisibility();
}

void MainWindow::setStatusIndicator(QLabel *label, const QString &text, const QString &color)
{
    if (label == nullptr) {
        return;
    }

    label->setText(text);
    label->setStyleSheet(QStringLiteral(
        "QLabel { color: white; background: %1; border-radius: 10px; padding: 4px 10px; font-weight: 600; }")
                             .arg(color));
}
