#include "mainwindow.h"

#include <QApplication>
#include <QDateTime>
#include <QDesktopServices>
#include <QDir>
#include <QDirIterator>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QProcess>
#include <QPushButton>
#include <QSplitter>
#include <QUrl>
#include <QVBoxLayout>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , m_demoRoot(QStringLiteral("D:/dnc/netSDK2/Demo/MfcDemo"))
{
    // Cac demo chi co file .exe, con DLL cua SDK (dhnetsdk.dll, play.dll...)
    // nam o D:\dnc\netSDK2\Bin. Them Bin vao PATH cua launcher de moi demo
    // duoc khoi chay (ke thua PATH nay) tim thay DLL.
    const QString sdkBin = QStringLiteral("D:\\dnc\\netSDK2\\Bin");
    qputenv("PATH", (sdkBin + QLatin1Char(';')
                     + QString::fromLocal8Bit(qgetenv("PATH"))).toLocal8Bit());

    setWindowTitle(QStringLiteral("NetSDK Demo Launcher"));
    resize(720, 640);

    auto *central = new QWidget(this);
    auto *mainLayout = new QVBoxLayout(central);

    // Thanh tim kiem
    auto *searchLayout = new QHBoxLayout;
    searchLayout->addWidget(new QLabel(QStringLiteral("Tìm kiếm:")));
    m_searchEdit = new QLineEdit;
    m_searchEdit->setPlaceholderText(QStringLiteral("Nhập tên demo, ví dụ: alarm, playback, ptz..."));
    m_searchEdit->setClearButtonEnabled(true);
    searchLayout->addWidget(m_searchEdit);
    mainLayout->addLayout(searchLayout);

    // Danh sach demo + log
    auto *splitter = new QSplitter(Qt::Vertical);
    m_listWidget = new QListWidget;
    m_listWidget->setAlternatingRowColors(true);
    splitter->addWidget(m_listWidget);

    m_logView = new QPlainTextEdit;
    m_logView->setReadOnly(true);
    m_logView->setMaximumBlockCount(500);
    m_logView->setPlaceholderText(QStringLiteral("Nhật ký chạy demo sẽ hiển thị ở đây..."));
    splitter->addWidget(m_logView);
    splitter->setStretchFactor(0, 3);
    splitter->setStretchFactor(1, 1);
    mainLayout->addWidget(splitter);

    // Cac nut chuc nang
    auto *buttonLayout = new QHBoxLayout;
    m_runButton = new QPushButton(QStringLiteral("▶ Chạy demo"));
    m_openFolderButton = new QPushButton(QStringLiteral("📂 Mở thư mục"));
    m_rescanButton = new QPushButton(QStringLiteral("🔄 Quét lại"));
    buttonLayout->addWidget(m_runButton);
    buttonLayout->addWidget(m_openFolderButton);
    buttonLayout->addWidget(m_rescanButton);
    buttonLayout->addStretch();
    mainLayout->addLayout(buttonLayout);

    m_statusLabel = new QLabel;
    mainLayout->addWidget(m_statusLabel);

    setCentralWidget(central);

    connect(m_searchEdit, &QLineEdit::textChanged, this, &MainWindow::filterList);
    connect(m_runButton, &QPushButton::clicked, this, &MainWindow::launchSelected);
    connect(m_openFolderButton, &QPushButton::clicked, this, &MainWindow::openDemoFolder);
    connect(m_rescanButton, &QPushButton::clicked, this, &MainWindow::rescan);
    connect(m_listWidget, &QListWidget::itemDoubleClicked, this, &MainWindow::launchItem);

    scanDemos();
    populateList();
}

void MainWindow::scanDemos()
{
    m_demos.clear();

    QDir root(m_demoRoot);
    if (!root.exists()) {
        QMessageBox::warning(this, QStringLiteral("Lỗi"),
            QStringLiteral("Không tìm thấy thư mục demo:\n%1").arg(m_demoRoot));
        return;
    }

    const QStringList demoDirs = root.entryList(QDir::Dirs | QDir::NoDotAndDotDot, QDir::Name);
    for (const QString &dirName : demoDirs) {
        // Moi demo co exe nam trong <demo>/bin/x64release/
        const QString binDir = root.filePath(dirName + QStringLiteral("/bin/x64release"));
        QDir bin(binDir);
        if (!bin.exists())
            continue;

        const QStringList exes = bin.entryList({QStringLiteral("*.exe")}, QDir::Files);
        if (exes.isEmpty())
            continue;

        DemoInfo info;
        info.name = dirName;
        info.exePath = bin.filePath(exes.first());
        info.workDir = binDir;
        m_demos.append(info);
    }

    m_statusLabel->setText(QStringLiteral("Đã tìm thấy %1 demo trong %2")
                               .arg(m_demos.size())
                               .arg(QDir::toNativeSeparators(m_demoRoot)));
}

void MainWindow::populateList()
{
    m_listWidget->clear();
    for (int i = 0; i < m_demos.size(); ++i) {
        const DemoInfo &d = m_demos.at(i);
        auto *item = new QListWidgetItem(d.name, m_listWidget);
        item->setData(Qt::UserRole, i);
        item->setToolTip(QDir::toNativeSeparators(d.exePath));
    }
    filterList(m_searchEdit->text());
}

void MainWindow::filterList(const QString &text)
{
    const QString needle = text.trimmed();
    for (int i = 0; i < m_listWidget->count(); ++i) {
        QListWidgetItem *item = m_listWidget->item(i);
        item->setHidden(!needle.isEmpty()
                        && !item->text().contains(needle, Qt::CaseInsensitive));
    }
}

void MainWindow::launchSelected()
{
    QListWidgetItem *item = m_listWidget->currentItem();
    if (!item) {
        QMessageBox::information(this, QStringLiteral("Chưa chọn demo"),
            QStringLiteral("Hãy chọn một demo trong danh sách trước."));
        return;
    }
    launchItem(item);
}

void MainWindow::launchItem(QListWidgetItem *item)
{
    const int index = item->data(Qt::UserRole).toInt();
    if (index < 0 || index >= m_demos.size())
        return;
    launchDemo(m_demos.at(index));
}

void MainWindow::launchDemo(const DemoInfo &demo)
{
    // Dat working directory la thu muc chua exe de demo nap duoc
    // cac DLL cua NetSDK (dhnetsdk.dll, play.dll, ...) nam canh no.
    const bool ok = QProcess::startDetached(demo.exePath, {}, demo.workDir);
    if (ok) {
        log(QStringLiteral("Đã khởi chạy: %1").arg(demo.name));
    } else {
        log(QStringLiteral("LỖI: không chạy được %1 (%2)")
                .arg(demo.name, QDir::toNativeSeparators(demo.exePath)));
        QMessageBox::warning(this, QStringLiteral("Lỗi"),
            QStringLiteral("Không khởi chạy được:\n%1")
                .arg(QDir::toNativeSeparators(demo.exePath)));
    }
}

void MainWindow::openDemoFolder()
{
    QListWidgetItem *item = m_listWidget->currentItem();
    QString path = m_demoRoot;
    if (item) {
        const int index = item->data(Qt::UserRole).toInt();
        if (index >= 0 && index < m_demos.size())
            path = m_demos.at(index).workDir;
    }
    QDesktopServices::openUrl(QUrl::fromLocalFile(path));
}

void MainWindow::rescan()
{
    scanDemos();
    populateList();
    log(QStringLiteral("Đã quét lại danh sách demo."));
}

void MainWindow::log(const QString &message)
{
    m_logView->appendPlainText(QStringLiteral("[%1] %2")
        .arg(QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss")), message));
}
