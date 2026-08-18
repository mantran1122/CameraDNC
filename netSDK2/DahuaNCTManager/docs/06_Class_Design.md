# 06_Class_Design.md

# Class Design

## Core Classes

``` text
MainWindow
│
├── AppController
│
├── DeviceManager
├── VideoManager
├── DownloadManager
├── PlaybackManager
├── ConfigManager
├── Logger
│
└── DahuaSdkManager
```

## Responsibilities

### MainWindow

-   UI
-   Signal/Slot
-   Không gọi SDK

### AppController

-   Điều phối nghiệp vụ

### DahuaSdkManager

-   Wrapper NetSDK
-   Singleton
-   Quản lý Handle

### DeviceManager

-   Danh sách thiết bị
-   Login/Logout

### VideoManager

-   Live View
-   Stream
-   Preview Handle

### DownloadManager

-   Queue
-   Progress
-   Export

### ConfigManager

-   JSON
-   Đọc/Ghi cấu hình

### Logger

-   GUI
-   File
-   Console

## Relationships

``` text
UI
 ↓
Controller
 ↓
Managers
 ↓
SDK Wrapper
 ↓
NetSDK
```

## Coding Rules

-   Một class một nhiệm vụ
-   Không biến global
-   Ưu tiên RAII
-   Signal/Slot thay callback trực tiếp

## Initial Build Order

1.  MainWindow
2.  Logger
3.  ConfigManager
4.  DahuaSdkManager
5.  DeviceManager
6.  VideoManager
7.  DownloadManager
