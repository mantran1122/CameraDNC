#include "src/widgets/mainwindow.h"

#include <QApplication>
#include <QFont>

int main(int argc, char *argv[])
{
    QApplication application(argc, argv);
    QFont appFont(QStringLiteral("Segoe UI"), 11);
    appFont.setStyleStrategy(QFont::PreferAntialias);
    application.setFont(appFont);
    MainWindow window;
    window.show();
    return QApplication::exec();
}
