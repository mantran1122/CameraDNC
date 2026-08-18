# 03_Build_Guide.md

# DahuaManager Build Guide

Version: 1.1

------------------------------------------------------------------------

# 1. Purpose

Tai lieu nay huong dan cau hinh moi truong de build va chay DahuaManager
bang CMake + Qt + Dahua General NetSDK trong workspace hien tai.

------------------------------------------------------------------------

# 2. Development Environment

  Component    Current Workspace
  ------------ ----------------------------
  Windows      Windows 10/11 x64
  Qt           Qt 6.11.1 MinGW 64-bit
  Compiler     MinGW 13.1.0
  CMake        Qt Tools CMake 3.30+
  Generator    Ninja
  SDK          Dahua General NetSDK Win64

MSVC x64 van la huong khuyen nghi neu sau nay cai them Qt kit tuong ung.

------------------------------------------------------------------------

# 3. Required Software

-   Qt 6.11.1 MinGW 64-bit
-   Qt Tools CMake
-   Ninja
-   PowerShell
-   Dahua General NetSDK

------------------------------------------------------------------------

# 4. SDK Directory

Recommended:

``` text
D:/
└── dnc/
    └── netSDK2/
        ├── Include/
        ├── Lib/
        │   └── Win64/
        └── Bin/
```

------------------------------------------------------------------------

# 5. Project Directory

``` text
DahuaManager/
├── CMakeLists.txt
├── CMakePresets.json
├── run.ps1
├── src/
├── docs/
├── config/
├── resources/
└── build/
```

------------------------------------------------------------------------

# 6. Configure Qt Kit

Qt Creator -> Preferences -> Kits

Use:

-   Desktop Qt 6.11.1 MinGW 64-bit
-   Ninja Generator
-   MinGW x64 Compiler

------------------------------------------------------------------------

# 7. Configure CMake

Project da ho tro:

-   `DAHUA_SDK_ROOT` qua CMake cache
-   `QT_DEPLOY_EXECUTABLE` qua CMake cache
-   `CMakePresets.json` cho workspace hien tai

Preset hien co:

``` text
mingw-debug
build-mingw-debug
```

------------------------------------------------------------------------

# 8. Link Libraries

Project link:

``` text
Qt6::Widgets
dhnetsdk.lib
dhconfigsdk.lib
```

------------------------------------------------------------------------

# 9. DLL Deployment

SDK DLL duoc copy tu dong sau khi build.

Qt runtime duoc deploy bang `windeployqt` qua:

-   CMake cache `QT_DEPLOY_EXECUTABLE`
-   hoac script `run.ps1`

------------------------------------------------------------------------

# 10. Automatic Deployment

Repo hien co san:

-   post-build copy SDK DLL trong `CMakeLists.txt`
-   preset configure/build trong `CMakePresets.json`
-   script chay nhanh `run.ps1`

------------------------------------------------------------------------

# 11. Build Steps

## Quick Run

``` powershell
cd D:\dnc\netSDK2\DahuaNCTManager
.\run.ps1
```

## Build by Preset

``` powershell
cmake --preset mingw-debug
cmake --build --preset build-mingw-debug
.\build\codex-check\DahuaManager.exe
```

## Run Without Rebuild

``` powershell
.\run.ps1 -NoBuild
```

------------------------------------------------------------------------

# 12. Verification Checklist

-   [ ] Qt kit dung
-   [ ] Compiler va Qt kit khop nhau
-   [ ] SDK include OK
-   [ ] SDK lib OK
-   [ ] SDK DLL copied
-   [ ] Qt runtime deployed
-   [ ] Build successful
-   [ ] App launches

------------------------------------------------------------------------

# 13. Common Errors

## Missing Qt DLL

App mo roi tat ngay.

Solution:

``` text
Chay .\run.ps1
```

## Missing SDK DLL

`dhnetsdk.dll not found`

Check:

-   `DAHUA_SDK_ROOT`
-   thu muc `Bin`
-   post-build copy

## Link Error

Check:

-   wrong compiler / wrong Qt kit
-   wrong SDK path
-   32/64-bit mismatch

------------------------------------------------------------------------

# 14. First Successful Run

Expected result:

-   application opens
-   no missing DLL dialog
-   log file is created
-   Qt window displayed

------------------------------------------------------------------------

# 15. Development Workflow

``` text
Environment
    ->
Configure
    ->
Build
    ->
Deploy
    ->
Run
    ->
SDK Init
    ->
Login
```

------------------------------------------------------------------------

# 16. Script Notes

-   `.\run.ps1` build + deploy + close old app + open new app
-   `.\run.ps1 -NoBuild` chi open lai app
-   `.\run.ps1 -NoDeploy` bo qua `windeployqt`
-   `.\run.ps1 -KeepExisting` khong dong process cu

------------------------------------------------------------------------

# 17. Next Document

Continue with:

    04_UI_Design.md
