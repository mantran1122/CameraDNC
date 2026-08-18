#include "src/dialogs/logindialog.h"

#include <QDialogButtonBox>
#include <QFormLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSpinBox>
#include <QVBoxLayout>

LoginDialog::LoginDialog(const DeviceConnectionInfo &initialValue, QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(QStringLiteral("Device Login"));
    setModal(true);
    resize(420, 320);
    setMinimumWidth(420);
    setStyleSheet(QStringLiteral(
        "QDialog { background: #0C1626; color: #E6EEF8; }"
        "QLabel { color: #D8E4F2; }"
        "QLabel[class='title'] { color: #F8FBFF; font-size: 22px; font-weight: 700; }"
        "QLabel[class='subtitle'] { color: #8FA6C2; font-size: 13px; }"
        "QLineEdit, QSpinBox {"
        " background: #091321; color: #F8FBFF; border: 1px solid #27405F; border-radius: 10px; padding: 10px 12px; min-height: 22px; }"
        "QLineEdit:focus, QSpinBox:focus { border: 1px solid #60A5FA; }"
        "QLineEdit::placeholder { color: #6F86A3; }"
        "QSpinBox::up-button, QSpinBox::down-button { width: 18px; border: none; }"
        "QPushButton { background: #173153; color: #F8FBFF; border: 1px solid #2E537E; border-radius: 12px; padding: 10px 18px; min-width: 96px; }"
        "QPushButton:hover { background: #1F426E; }"
        "QPushButton:pressed { background: #123050; }"
        "QPushButton[text='Cancel'] { background: #101C2E; border-color: #31415A; color: #D7E2EF; }"));

    m_nameEdit = new QLineEdit(initialValue.name, this);
    m_nameEdit->setPlaceholderText(QStringLiteral("Default Device"));
    m_hostEdit = new QLineEdit(initialValue.host, this);
    m_hostEdit->setPlaceholderText(QStringLiteral("192.168.x.x"));
    m_portSpinBox = new QSpinBox(this);
    m_portSpinBox->setRange(1, 65535);
    m_portSpinBox->setValue(initialValue.port);
    m_usernameEdit = new QLineEdit(initialValue.username, this);
    m_usernameEdit->setPlaceholderText(QStringLiteral("admin"));
    m_passwordEdit = new QLineEdit(initialValue.password, this);
    m_passwordEdit->setEchoMode(QLineEdit::Password);
    m_passwordEdit->setPlaceholderText(QStringLiteral("Enter device password"));

    auto *titleLabel = new QLabel(QStringLiteral("Connect To Device"), this);
    titleLabel->setProperty("class", "title");
    auto *subtitleLabel = new QLabel(QStringLiteral("Enter Dahua device credentials to start live view and download playback."), this);
    subtitleLabel->setProperty("class", "subtitle");
    subtitleLabel->setWordWrap(true);

    auto *formLayout = new QFormLayout;
    formLayout->setLabelAlignment(Qt::AlignLeft | Qt::AlignVCenter);
    formLayout->setFormAlignment(Qt::AlignTop);
    formLayout->setHorizontalSpacing(14);
    formLayout->setVerticalSpacing(12);
    formLayout->addRow(QStringLiteral("Name"), m_nameEdit);
    formLayout->addRow(QStringLiteral("Host"), m_hostEdit);
    formLayout->addRow(QStringLiteral("Port"), m_portSpinBox);
    formLayout->addRow(QStringLiteral("Username"), m_usernameEdit);
    formLayout->addRow(QStringLiteral("Password"), m_passwordEdit);

    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, this);
    buttons->button(QDialogButtonBox::Ok)->setText(QStringLiteral("Connect"));
    buttons->button(QDialogButtonBox::Cancel)->setText(QStringLiteral("Cancel"));
    connect(buttons, &QDialogButtonBox::accepted, this, &LoginDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &LoginDialog::reject);

    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(22, 22, 22, 18);
    layout->setSpacing(16);
    layout->addWidget(titleLabel);
    layout->addWidget(subtitleLabel);
    layout->addLayout(formLayout);
    layout->addWidget(buttons);
}

DeviceConnectionInfo LoginDialog::connectionInfo() const
{
    DeviceConnectionInfo info;
    info.name = m_nameEdit->text().trimmed();
    info.host = m_hostEdit->text().trimmed();
    info.port = static_cast<quint16>(m_portSpinBox->value());
    info.username = m_usernameEdit->text().trimmed();
    info.password = m_passwordEdit->text();
    return info;
}
