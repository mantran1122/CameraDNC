# 02_Project_Structure.md

# Project Structure

Version: 1.0

------------------------------------------------------------------------

# 1. Design Objectives

Mục tiêu của cấu trúc project:

-   Dễ đọc
-   Dễ bảo trì
-   Dễ mở rộng
-   Tách biệt UI và SDK
-   Chuẩn Enterprise

------------------------------------------------------------------------

# 2. Final Directory Tree

``` text
DahuaManager/
│
├── CMakeLists.txt
├── README.md
├── LICENSE
│
├── docs/
├── config/
├── logs/
├── output/
│   ├── download/
│   ├── snapshot/
│   └── export/
│
├── resources/
│   ├── icons/
│   ├── images/
│   ├── fonts/
│   └── qss/
│
├── third_party/
│   └── DahuaSDK/
│
├── tests/
│
└── src/
    ├── app/
    ├── core/
    ├── sdk/
    ├── managers/
    ├── controllers/
    ├── widgets/
    ├── dialogs/
    ├── models/
    ├── services/
    ├── utils/
    ├── database/
    ├── network/
    ├── theme/
    └── main.cpp
```

------------------------------------------------------------------------

# 3. Folder Responsibilities

## app/

Khởi tạo ứng dụng.

Chứa:

-   Application
-   AppInitializer
-   Startup

------------------------------------------------------------------------

## core/

Logic lõi:

-   GlobalConfig
-   AppContext
-   EventBus
-   ErrorManager

------------------------------------------------------------------------

## sdk/

Wrapper duy nhất cho Dahua NetSDK.

Ví dụ:

``` text
DahuaSdkManager.h
DahuaSdkManager.cpp
SdkCallback.cpp
SdkError.cpp
```

**Quy tắc:** chỉ thư mục này được include `dhnetsdk.h`.

------------------------------------------------------------------------

## managers/

Các manager nghiệp vụ:

-   DeviceManager
-   VideoManager
-   PlaybackManager
-   DownloadManager
-   SnapshotManager
-   AlarmManager
-   LoggerManager
-   ConfigManager

------------------------------------------------------------------------

## controllers/

Điều phối giữa UI và Managers.

Ví dụ:

-   LoginController
-   LiveController
-   DownloadController

------------------------------------------------------------------------

## widgets/

Widget tái sử dụng:

-   VideoWidget
-   DeviceCard
-   LogView
-   StatusBar
-   DownloadProgress

------------------------------------------------------------------------

## dialogs/

Các hộp thoại:

-   LoginDialog
-   SettingsDialog
-   AboutDialog
-   DeviceDialog

------------------------------------------------------------------------

## models/

Đối tượng dữ liệu:

``` text
DeviceInfo
ChannelInfo
DownloadTask
UserConfig
```

Model không chứa logic SDK.

------------------------------------------------------------------------

## services/

Các dịch vụ nền:

-   FileService
-   JsonService
-   TimeService

------------------------------------------------------------------------

## utils/

Tiện ích:

-   FileUtils
-   StringUtils
-   DateTimeUtils
-   PathUtils

------------------------------------------------------------------------

## database/

SQLite:

-   DatabaseManager
-   Repository
-   Migration

------------------------------------------------------------------------

## network/

Nếu sau này hỗ trợ REST API hoặc HTTP.

------------------------------------------------------------------------

## theme/

Dark / Light theme.

``` text
dark.qss
light.qss
```

------------------------------------------------------------------------

# 4. Naming Rules

## File

``` text
DeviceManager.h
DeviceManager.cpp
```

## Class

``` cpp
class DeviceManager;
```

## Member

``` cpp
m_loginHandle
m_deviceList
```

## Constant

``` cpp
constexpr int MaxChannel = 64;
```

------------------------------------------------------------------------

# 5. Include Rule

``` text
Widget
 ↓
Controller
 ↓
Manager
 ↓
SDK
```

Không include ngược lên.

------------------------------------------------------------------------

# 6. Output Directory

``` text
output/
├── download/
├── snapshot/
├── export/
├── playback/
└── temp/
```

------------------------------------------------------------------------

# 7. Config Directory

``` text
config/
├── config.json
├── devices.json
├── user.json
└── theme.json
```

------------------------------------------------------------------------

# 8. Documentation Directory

``` text
docs/
00_Project_Overview.md
01_Architecture.md
02_Project_Structure.md
03_Build_Guide.md
04_UI_Design.md
05_SDK_Integration.md
06_Class_Design.md
07_API_Reference.md
08_Testing.md
09_Roadmap.md
```

------------------------------------------------------------------------

# 9. Third Party

``` text
third_party/
└── DahuaSDK/
    ├── Include/
    ├── Lib/
    └── Bin/
```

Không sửa mã nguồn SDK.

------------------------------------------------------------------------

# 10. Build Output

``` text
build/
├── Debug/
├── Release/
└── install/
```

Copy DLL Dahua vào Debug/Release sau khi build.

------------------------------------------------------------------------

# 11. Coding Checklist

-   Một class một nhiệm vụ.
-   Không viết logic lớn trong MainWindow.
-   Không dùng biến global.
-   Không gọi SDK ngoài sdk/.
-   Signal/Slot thay cho callback trực tiếp.

------------------------------------------------------------------------

# 12. Recommended Initial Classes

``` text
MainWindow
AppController
DahuaSdkManager
DeviceManager
VideoManager
DownloadManager
Logger
ConfigManager
VideoWidget
DownloadTask
```

------------------------------------------------------------------------

# 13. Development Order

1.  CMake
2.  SDK
3.  Logger
4.  Config
5.  Login
6.  Live
7.  Download
8.  Playback
9.  Snapshot
10. Alarm

------------------------------------------------------------------------

# 14. Next Document

Tiếp tục:

    03_Build_Guide.md

Tài liệu này sẽ hướng dẫn cấu hình Qt Creator, CMake, MSVC và Dahua
NetSDK từ đầu đến khi chạy được project.
