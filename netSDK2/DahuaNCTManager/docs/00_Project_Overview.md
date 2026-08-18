# DahuaManager
## Project Overview

**Project Name**

DahuaManager

**Version**

0.1.0 (Development)

**Author**

...

**Language**

C++17

**Framework**

Qt 6 (Qt Widgets)

**IDE**

Qt Creator

**Compiler**

MSVC x64

**Build System**

CMake

**SDK**

Dahua General NetSDK

---

# 1. Project Introduction

DahuaManager là phần mềm quản lý và khai thác dữ liệu từ đầu ghi hình Dahua (NVR/DVR) được phát triển bằng **Qt Creator + C++17 + Dahua General NetSDK**.

Mục tiêu của dự án là xây dựng một ứng dụng desktop hiện đại, có khả năng:

- Đăng nhập nhiều đầu ghi Dahua.
- Xem trực tiếp camera.
- Tải video theo thời gian.
- Snapshot hình ảnh.
- Playback video.
- Quản lý nhiều thiết bị.
- Ghi log.
- Quản lý cấu hình.
- Dễ mở rộng các tính năng AI trong tương lai.

Dự án được thiết kế theo hướng Enterprise Application để có thể phát triển lâu dài thay vì chỉ phục vụ một chức năng đơn lẻ.

---

# 2. Project Goals

## Version 1

- SDK Initialization
- Login / Logout
- Live View
- Download By Time
- Log Viewer

---

## Version 2

- Playback
- Snapshot
- Multi Camera
- Device Manager
- JSON Configuration

---

## Version 3

- SQLite Database
- Alarm Events
- Motion Detection
- Disk Information
- Export Log

---

## Version 4

- AI Metadata
- Face Detection
- IVS Events
- Multi NVR
- User Management

---

# 3. Technology Stack

| Category | Technology |
|-----------|------------|
| Language | C++17 |
| UI | Qt Widgets |
| IDE | Qt Creator |
| Build | CMake |
| Compiler | MSVC x64 |
| SDK | Dahua General NetSDK |
| Database | SQLite |
| Config | JSON |
| Logging | Qt Logging |
| Version Control | Git |

---

# 4. Supported Devices

Hiện tại ưu tiên hỗ trợ:

```
Dahua NVR
Dahua DVR
Dahua IPC
```

Thiết bị đang phát triển:

```
Model

DHI-NVR5832-EI2

IP

192.168.3.26

SDK Port

37777

HTTP

80

RTSP

554
```

---

# 5. Main Features

## Device

- Login
- Logout
- Auto Reconnect
- Device Information

---

## Video

- Live View
- Main Stream
- Sub Stream
- Multi Screen

---

## Playback

- Search Record
- Timeline
- Playback
- Pause
- Fast Forward

---

## Download

- Download By Time
- Queue Download
- Progress
- Cancel

---

## Snapshot

- JPG
- PNG
- Auto Naming

---

## Logs

- GUI Log
- File Log
- Debug Log

---

## Configuration

- Save Device
- Save User
- Save Folder
- Theme

---

# 6. Development Philosophy

Dự án tuân theo các nguyên tắc:

- Clean Architecture
- SOLID
- RAII
- Design Patterns
- Single Responsibility
- Separation of Concerns

Không viết toàn bộ logic trong MainWindow.

---

# 7. Software Architecture

```
Presentation Layer

↓

Application Layer

↓

Service Layer

↓

SDK Layer

↓

Dahua NetSDK

↓

Device
```

Chi tiết xem:

```
01_Architecture.md
```

---

# 8. Project Directory

```
DahuaManager/

apps/

src/

include/

resources/

config/

logs/

download/

snapshot/

docs/

tests/

third_party/

plugins/
```

Chi tiết xem:

```
02_Project_Structure.md
```

---

# 9. Documentation

| File | Description |
|------|-------------|
|00_Project_Overview.md|Project Overview|
|01_Architecture.md|Software Architecture|
|02_Project_Structure.md|Directory Structure|
|03_Build_Guide.md|Qt + CMake Setup|
|04_UI_Design.md|UI Design|
|05_SDK_Integration.md|Dahua SDK|
|06_Class_Design.md|Class Design|
|07_API_Reference.md|Internal API|
|08_Testing.md|Testing|
|09_Roadmap.md|Development Plan|

---

# 10. Coding Rules

- C++17
- Không dùng global variable.
- Không gọi trực tiếp SDK trong UI.
- Mọi thao tác SDK đi qua DahuaSdkManager.
- Mỗi class chỉ đảm nhiệm một nhiệm vụ.
- Tất cả tài nguyên phải được giải phóng đúng cách.

---

# 11. Naming Convention

## Class

```
MainWindow

DeviceManager

VideoWidget
```

---

## Variable

```
m_loginHandle

m_deviceList

m_sdkInitialized
```

---

## Function

```
initSdk()

login()

logout()

startPreview()

stopPreview()
```

---

# 12. Branch Strategy

```
main

develop

feature/login

feature/live

feature/download

feature/playback
```

---

# 13. Development Workflow

```
Requirement

↓

Design

↓

Implementation

↓

Testing

↓

Review

↓

Release
```

---

# 14. Current Progress

| Module | Status |
|----------|--------|
|Project|🟡|
|CMake|🟡|
|SDK|⬜|
|Login|⬜|
|Live View|⬜|
|Playback|⬜|
|Download|⬜|
|Snapshot|⬜|
|Database|⬜|

---

# 15. Long-term Vision

Mục tiêu cuối cùng của DahuaManager không chỉ là phần mềm tải video từ đầu ghi Dahua.

Đây sẽ là nền tảng (Platform) quản lý camera với kiến trúc mở, hỗ trợ nhiều loại thiết bị, nhiều đầu ghi và nhiều module mở rộng như AI, cảnh báo thông minh, quản lý người dùng, cơ sở dữ liệu và plugin.

Toàn bộ dự án được thiết kế để có thể mở rộng trong nhiều năm mà không cần thay đổi kiến trúc cốt lõi.

---

# 16. Next Document

Sau khi đọc xong tài liệu này, tiếp tục:

```
01_Architecture.md
```

Đây là tài liệu quan trọng nhất của toàn bộ dự án.