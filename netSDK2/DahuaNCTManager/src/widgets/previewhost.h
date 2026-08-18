#ifndef PREVIEWHOST_H
#define PREVIEWHOST_H

#include <QWidget>

#ifdef Q_OS_WIN
#include <qt_windows.h>
#endif

class PreviewHost : public QWidget
{
    Q_OBJECT

public:
    enum class DisplayMode
    {
        Fit,
        Fill
    };

    explicit PreviewHost(QWidget *parent = nullptr);
    ~PreviewHost() override;

    quintptr renderHandle();
    void setPreviewVisible(bool visible);
    void setDisplayMode(DisplayMode mode);
    DisplayMode displayMode() const;
    void setContentAspectRatio(qreal aspectRatio);

signals:
    void doubleClicked();
    void hostGeometryChanged();

protected:
    void showEvent(QShowEvent *event) override;
    void resizeEvent(QResizeEvent *event) override;
    void moveEvent(QMoveEvent *event) override;
    void hideEvent(QHideEvent *event) override;
    void mouseDoubleClickEvent(QMouseEvent *event) override;

private:
    static LRESULT CALLBACK previewWindowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam);
    void schedulePreviewSync();
    void ensurePreviewWindow();
    void syncPreviewWindowGeometry();
    void syncPreviewWindowVisibility();

    void *m_previewWindowHandle = nullptr;
    bool m_previewVisible = false;
    bool m_syncPending = false;
    DisplayMode m_displayMode = DisplayMode::Fit;
    qreal m_contentAspectRatio = 16.0 / 9.0;
};

#endif // PREVIEWHOST_H
