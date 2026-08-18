# 04_UI_Design.md

# UI Design

## Design Goals

-   Dark Theme mặc định
-   Responsive với nhiều độ phân giải
-   Thao tác nhanh
-   Ít cửa sổ popup

## Main Layout

``` text
+---------------------------------------------------------------+
| Toolbar                                                       |
+----------------------+----------------------------------------+
| Device Panel         | Live View (1/4/9/16 cameras)          |
| - Device Tree        |                                        |
| - Channel List       |                                        |
+----------------------+----------------------------------------+
| Download / Playback  | Log Window                             |
+---------------------------------------------------------------+
| Status Bar                                                FPS |
+---------------------------------------------------------------+
```

## Main Widgets

-   QMainWindow
-   QDockWidget (Device)
-   QSplitter
-   QTreeWidget
-   QTabWidget
-   QGridLayout
-   QTextEdit(Log)
-   QStatusBar

## Toolbar

-   Login
-   Logout
-   Live
-   Playback
-   Snapshot
-   Download
-   Settings

## Status Colors

-   Green: Connected
-   Red: Disconnected
-   Orange: Reconnecting

## Theme

resources/qss/dark.qss resources/qss/light.qss

## UX Rules

-   Double click channel để mở Live
-   Drag & Drop đổi vị trí camera
-   Right click mở menu nhanh
-   Không popup khi không cần

## Next

05_SDK_Integration.md
