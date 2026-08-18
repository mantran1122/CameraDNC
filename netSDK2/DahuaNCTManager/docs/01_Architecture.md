# 01_Architecture.md

# DahuaManager Software Architecture

Version: 1.0

------------------------------------------------------------------------

# 1. Architecture Goals

-   Clean Architecture
-   Modular Design
-   Easy Maintenance
-   Enterprise Scalability
-   Qt + C++17 Best Practices

------------------------------------------------------------------------

# 2. Overall Architecture

``` text
                    +----------------------+
                    |      MainWindow      |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    |    AppController     |
                    +----------+-----------+
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
 +----------------+   +----------------+   +----------------+
 | DeviceManager  |   | VideoManager   |   |DownloadManager |
 +-------+--------+   +-------+--------+   +--------+-------+
         |                    |                    |
         +--------------------+--------------------+
                              |
                              v
                    +----------------------+
                    |  DahuaSdkManager     |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Dahua General NetSDK |
                    +----------+-----------+
                               |
                               v
                    +----------------------+
                    | Dahua NVR / IPC      |
                    +----------------------+
```

------------------------------------------------------------------------

# 3. Layered Architecture

## Presentation Layer

Thành phần:

-   MainWindow
-   LoginWidget
-   LiveViewWidget
-   DownloadWidget
-   LogWidget

Nhiệm vụ:

-   Hiển thị giao diện
-   Nhận thao tác người dùng
-   Không gọi NetSDK trực tiếp

------------------------------------------------------------------------

## Application Layer

Điều phối toàn bộ luồng nghiệp vụ.

Các Controller:

-   AppController
-   DeviceController
-   VideoController

Chỉ đạo các Manager làm việc.

------------------------------------------------------------------------

## Service Layer

Bao gồm:

-   DeviceManager
-   VideoManager
-   DownloadManager
-   PlaybackManager
-   SnapshotManager
-   ConfigManager
-   Logger

Đây là tầng chứa toàn bộ business logic.

------------------------------------------------------------------------

## SDK Layer

Chỉ có một lớp duy nhất:

    DahuaSdkManager

Mọi lời gọi NetSDK phải đi qua lớp này.

Không lớp nào khác được include `dhnetsdk.h`.

------------------------------------------------------------------------

# 4. Data Flow

``` text
User Click Login
        |
        v
MainWindow
        |
        v
AppController
        |
        v
DeviceManager
        |
        v
DahuaSdkManager
        |
        v
CLIENT_LoginWithHighLevelSecurity()
        |
        v
Dahua Device
        |
        v
Result
        |
        v
Signal
        |
        v
MainWindow
```

------------------------------------------------------------------------

# 5. Module Responsibilities

  Module            Responsibility
  ----------------- ----------------
  MainWindow        UI
  AppController     Điều phối
  DeviceManager     Thiết bị
  VideoManager      Live View
  DownloadManager   Download
  PlaybackManager   Playback
  SnapshotManager   Snapshot
  Logger            Logging
  ConfigManager     JSON Config
  DahuaSdkManager   NetSDK Wrapper

------------------------------------------------------------------------

# 6. Design Principles

-   Single Responsibility Principle
-   Open/Closed Principle
-   Dependency Inversion
-   RAII
-   Composition over Inheritance

------------------------------------------------------------------------

# 7. Design Patterns

## Singleton

-   DahuaSdkManager
-   Logger
-   ConfigManager

## Factory

-   Device Factory
-   Task Factory

## Observer

Qt Signal / Slot

## Strategy

-   Main Stream
-   Sub Stream

## Command

-   Download
-   Snapshot

------------------------------------------------------------------------

# 8. Thread Architecture

``` text
Main Thread
 |
 +-- UI
 |
 +-- SDK Callback
 |
 +-- Worker Threads
      |
      +-- Download
      +-- Playback
      +-- Snapshot
```

Không thực hiện download hoặc playback trên UI Thread.

------------------------------------------------------------------------

# 9. Error Handling

-   SDK Error
-   Network Error
-   File Error
-   User Error

Tất cả lỗi được chuyển thành thông điệp dễ hiểu qua ErrorManager.

------------------------------------------------------------------------

# 10. Configuration

Dùng JSON:

-   config.json
-   devices.json
-   user.json

Không hard-code IP hoặc mật khẩu.

------------------------------------------------------------------------

# 11. Logging

Logger hỗ trợ:

-   GUI Log
-   File Log
-   Debug Console

Level:

-   INFO
-   DEBUG
-   WARNING
-   ERROR
-   FATAL

------------------------------------------------------------------------

# 12. Directory Dependency

``` text
UI
 |
Controller
 |
Manager
 |
SDK
 |
NetSDK
```

Không được gọi ngược chiều.

------------------------------------------------------------------------

# 13. Future Expansion

Kiến trúc hỗ trợ bổ sung:

-   PTZ
-   AI Metadata
-   Face Recognition
-   IVS
-   Alarm Center
-   Plugin System
-   Multi NVR
-   REST API

Không cần thay đổi kiến trúc lõi.

------------------------------------------------------------------------

# 14. Architecture Checklist

-   [ ] UI tách khỏi SDK
-   [ ] Một SDK Wrapper duy nhất
-   [ ] Không gọi NetSDK trong Widget
-   [ ] Hỗ trợ đa luồng
-   [ ] Có Logger
-   [ ] Có Config
-   [ ] Có Database
-   [ ] Dễ mở rộng

------------------------------------------------------------------------

# 15. Next Document

Tiếp tục đọc:

    02_Project_Structure.md

Tài liệu này mô tả chi tiết cấu trúc thư mục và vai trò của từng file
trong dự án.
