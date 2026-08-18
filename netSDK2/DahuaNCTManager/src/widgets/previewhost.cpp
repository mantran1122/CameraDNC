#include "src/widgets/previewhost.h"

#include "src/managers/loggermanager.h"

#include <QMouseEvent>
#include <QPalette>
#include <QTimer>

#include <qt_windows.h>

PreviewHost::PreviewHost(QWidget *parent)
    : QWidget(parent)
{
    setAttribute(Qt::WA_NativeWindow, true);
    setAttribute(Qt::WA_DontCreateNativeAncestors, true);
    setAutoFillBackground(true);

    QPalette surfacePalette = palette();
    surfacePalette.setColor(QPalette::Window, QColor(QStringLiteral("#050B14")));
    setPalette(surfacePalette);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
}

PreviewHost::~PreviewHost()
{
    const HWND previewWindow = reinterpret_cast<HWND>(m_previewWindowHandle);
    if (previewWindow != nullptr && IsWindow(previewWindow)) {
        DestroyWindow(previewWindow);
    }
}

quintptr PreviewHost::renderHandle()
{
    ensurePreviewWindow();
    return reinterpret_cast<quintptr>(m_previewWindowHandle);
}

void PreviewHost::setPreviewVisible(bool visible)
{
    m_previewVisible = visible;
    schedulePreviewSync();
    syncPreviewWindowVisibility();
}

void PreviewHost::setDisplayMode(DisplayMode mode)
{
    if (m_displayMode == mode) {
        return;
    }

    m_displayMode = mode;
    schedulePreviewSync();
}

PreviewHost::DisplayMode PreviewHost::displayMode() const
{
    return m_displayMode;
}

void PreviewHost::setContentAspectRatio(qreal aspectRatio)
{
    if (aspectRatio <= 0.0 || qFuzzyCompare(m_contentAspectRatio, aspectRatio)) {
        return;
    }

    m_contentAspectRatio = aspectRatio;
    schedulePreviewSync();
}

void PreviewHost::showEvent(QShowEvent *event)
{
    QWidget::showEvent(event);
    ensurePreviewWindow();
    syncPreviewWindowGeometry();
    syncPreviewWindowVisibility();
    schedulePreviewSync();
    emit hostGeometryChanged();
}

void PreviewHost::resizeEvent(QResizeEvent *event)
{
    QWidget::resizeEvent(event);
    syncPreviewWindowGeometry();
    schedulePreviewSync();
    emit hostGeometryChanged();
}

void PreviewHost::moveEvent(QMoveEvent *event)
{
    QWidget::moveEvent(event);
    schedulePreviewSync();
}

void PreviewHost::hideEvent(QHideEvent *event)
{
    QWidget::hideEvent(event);
    syncPreviewWindowVisibility();
}

void PreviewHost::mouseDoubleClickEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        emit doubleClicked();
        event->accept();
        return;
    }

    QWidget::mouseDoubleClickEvent(event);
}

LRESULT CALLBACK PreviewHost::previewWindowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam)
{
    if (message == WM_NCCREATE) {
        const auto *createStruct = reinterpret_cast<const CREATESTRUCTW *>(lParam);
        auto *host = static_cast<PreviewHost *>(createStruct->lpCreateParams);
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(host));
        return DefWindowProcW(hwnd, message, wParam, lParam);
    }

    auto *host = reinterpret_cast<PreviewHost *>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    if (host != nullptr && message == WM_LBUTTONDBLCLK) {
        emit host->doubleClicked();
        return 0;
    }

    return DefWindowProcW(hwnd, message, wParam, lParam);
}

void PreviewHost::schedulePreviewSync()
{
    if (m_syncPending) {
        return;
    }

    m_syncPending = true;
    QTimer::singleShot(0, this, [this]() {
        m_syncPending = false;
        ensurePreviewWindow();
        syncPreviewWindowGeometry();
        syncPreviewWindowVisibility();
    });
}

void PreviewHost::ensurePreviewWindow()
{
    const HWND previewWindow = reinterpret_cast<HWND>(m_previewWindowHandle);
    if (previewWindow != nullptr && IsWindow(previewWindow)) {
        return;
    }

    createWinId();
    const HWND parentWindow = reinterpret_cast<HWND>(winId());
    if (parentWindow == nullptr || !IsWindow(parentWindow)) {
        return;
    }

    static const wchar_t *kPreviewWindowClass = L"DahuaPreviewHostWindow";
    static bool classRegistered = false;
    if (!classRegistered) {
        WNDCLASSW windowClass = {};
        windowClass.lpfnWndProc = &PreviewHost::previewWindowProc;
        windowClass.hInstance = GetModuleHandleW(nullptr);
        windowClass.lpszClassName = kPreviewWindowClass;
        windowClass.hbrBackground = reinterpret_cast<HBRUSH>(GetStockObject(BLACK_BRUSH));
        windowClass.style = CS_DBLCLKS;
        classRegistered = RegisterClassW(&windowClass) != 0 || GetLastError() == ERROR_CLASS_ALREADY_EXISTS;
    }

    m_previewWindowHandle = CreateWindowExW(0,
                                            kPreviewWindowClass,
                                            nullptr,
                                            WS_CHILD | WS_CLIPCHILDREN | WS_CLIPSIBLINGS,
                                            0,
                                            0,
                                            qMax(1, width()),
                                            qMax(1, height()),
                                            parentWindow,
                                            nullptr,
                                            GetModuleHandleW(nullptr),
                                            this);

    const HWND childWindow = reinterpret_cast<HWND>(m_previewWindowHandle);
    if (childWindow != nullptr) {
        LoggerManager::instance().logInfo(
            QStringLiteral("Preview host created: parent=%1 child=%2 size=%3x%4")
                .arg(static_cast<qulonglong>(reinterpret_cast<quintptr>(parentWindow)))
                .arg(static_cast<qulonglong>(reinterpret_cast<quintptr>(childWindow)))
                .arg(width())
                .arg(height()));
    } else {
        LoggerManager::instance().logWarning(QStringLiteral("Failed to create native preview host window"));
    }
}

void PreviewHost::syncPreviewWindowGeometry()
{
    const HWND previewWindow = reinterpret_cast<HWND>(m_previewWindowHandle);
    if (previewWindow == nullptr || !IsWindow(previewWindow)) {
        return;
    }

    MoveWindow(previewWindow, 0, 0, qMax(1, width()), qMax(1, height()), TRUE);
    InvalidateRect(previewWindow, nullptr, TRUE);
}

void PreviewHost::syncPreviewWindowVisibility()
{
    const HWND previewWindow = reinterpret_cast<HWND>(m_previewWindowHandle);
    if (previewWindow == nullptr || !IsWindow(previewWindow)) {
        return;
    }

    const bool shouldShow = m_previewVisible && isVisible();
    ShowWindow(previewWindow, shouldShow ? SW_SHOWNA : SW_HIDE);
}
