#ifndef LOGINDIALOG_H
#define LOGINDIALOG_H

#include "src/models/deviceconnectioninfo.h"

#include <QDialog>

class QLineEdit;
class QSpinBox;

class LoginDialog : public QDialog
{
    Q_OBJECT

public:
    explicit LoginDialog(const DeviceConnectionInfo &initialValue, QWidget *parent = nullptr);
    DeviceConnectionInfo connectionInfo() const;

private:
    QLineEdit *m_nameEdit = nullptr;
    QLineEdit *m_hostEdit = nullptr;
    QSpinBox *m_portSpinBox = nullptr;
    QLineEdit *m_usernameEdit = nullptr;
    QLineEdit *m_passwordEdit = nullptr;
};

#endif // LOGINDIALOG_H
