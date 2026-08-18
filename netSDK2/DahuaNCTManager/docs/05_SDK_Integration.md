# 05_SDK_Integration.md

# Dahua SDK Integration Plan

## Goal

Tich hop `Dahua NetSDK` vao phan mem `Qt/C++` cua rieng minh.

Muc tieu la:

- Dung lai SDK goc cua Dahua
- Khong viet lai SDK
- Boc SDK bang cac lop cua app de co UI dep, de mo rong, de bao tri
- Giu logic nghiep vu va giao dien tach khoi logic SDK

## Core Direction

Huong dung:

```text
Dahua NetSDK
    ->
DahuaSdkManager
    ->
DeviceManager / VideoManager / DownloadManager
    ->
AppController
    ->
Qt UI
```

Y nghia:

- `Dahua NetSDK` la engine goc
- `DahuaSdkManager` chi dong vai tro wrapper
- Cac manager cua app chi goi wrapper, khong goi truc tiep `CLIENT_*`
- UI khong duoc chua code SDK

## What We Keep

Nhung phan nen giu:

- `MainWindow` va bo khung UI Qt
- `AppController`
- `DeviceManager`
- `VideoManager`
- `DownloadManager`
- `ConfigManager`
- `LoggerManager`
- Cac model:
  - `DeviceConnectionInfo`
  - `PreviewChannelInfo`
  - `DownloadTask`

## What We Refactor

Nhung phan can don lai:

- `DahuaSdkManager`
- Cac logic preview native window
- Cac fallback preview qua nhieu nhanh
- Cac trang thai live dang bi tron lan giua:
  - SDK session
  - render host
  - tile UI

## Wrapper Rules

Chi `DahuaSdkManager` duoc phep include:

```cpp
#include "dhnetsdk.h"
```

Va neu can:

```cpp
#include "dhconfigsdk.h"
```

Tat ca module khac:

- Khong include header cua Dahua SDK
- Chi giao tiep qua method/signal cua wrapper

## Clean Architecture Rules

### 1. SDK layer

`DahuaSdkManager` chi lam:

- `initialize`
- `cleanup`
- `login`
- `logout`
- `queryPreviewChannels`
- `startLive`
- `stopLive`
- `downloadByTime`
- `stopDownload`
- chuyen ma loi SDK thanh `QString`

`DahuaSdkManager` khong nen:

- Dieu khien layout UI
- Dieu khien tile dang duoc chon
- Chua style, kich thuoc, margin, label

### 2. Application layer

`DeviceManager`, `VideoManager`, `DownloadManager`:

- Goi `DahuaSdkManager`
- Chuan hoa API cho app
- Giu state muc ung dung

### 3. UI layer

`MainWindow` va widget:

- Hien thi trang thai
- Xu ly thao tac nguoi dung
- Dieu khien tile nao dang chon
- Khong xu ly truc tiep `CLIENT_*`

## Integration Scope

Giai doan nay chi tap trung vao 4 nhom chuc nang:

1. SDK lifecycle
2. Device login/logout
3. Live preview
4. Download by time

Chua uu tien:

- PTZ
- Snapshot nang cao
- Playback nang cao
- Alarm/event
- Cau hinh thiet bi

## Standard SDK Flow

```text
CLIENT_Init
    ->
CLIENT_SetAutoReconnect
    ->
CLIENT_LoginWithHighLevelSecurity
    ->
Query channels
    ->
CLIENT_RealPlayByDataType / CLIENT_RealPlayEx
    ->
CLIENT_DownloadByTimeEx
    ->
CLIENT_Logout
    ->
CLIENT_Cleanup
```

## Refactor Phases

## Phase 1 - Stabilize Wrapper

Muc tieu:

- Co mot `DahuaSdkManager` gon
- Live preview chay on dinh
- Login va query channel ro rang

Viec can lam:

- [x] Gom lai cac API login/query/live/download
- [ ] Giam bot fallback khong can thiet
- [x] Chuan hoa log
- [x] Chuan hoa `lastError()`

Done khi:

- [x] Login on dinh
- [x] Lay duoc danh sach channel
- [x] Start/stop live khong gay vo UI

## Phase 2 - Separate Preview Rendering

Muc tieu:

- Tach render host khoi SDK wrapper

Viec can lam:

- [x] Tao lop rieng `PreviewHost`
- [x] Chuyen logic native preview window sang `PreviewHost`
- [x] `PreviewHost` xu ly native preview window
- [x] `PreviewHost` xu ly resize
- [x] `PreviewHost` xu ly visible/hidden
- [x] Bo sung fit/fill aspect ratio

Done khi:

- [x] Video khong de layout
- [x] Video co the full khung theo quy tac da chon
- [x] Moi tile co vung render rieng, doc lap

## Phase 3 - Multi Tile Preview

Muc tieu:

- Mo dong thoi nhieu camera

Viec can lam:

- [x] Moi tile co render host rieng
- [x] Quan ly map `tile index -> sdk channel`
- [x] Quan ly `live handle` theo session
- [x] Neu start lai tren cung tile thi chi stop session cua tile do
- [x] Stop tile nao thi chi anh huong tile do bang public API rieng

Done khi:

- [x] 1 / 4 / 9 / 16 tile mo dung
- [x] Mo camera moi tren tile dang chon khong dap layout UI
- [ ] Mo dong thoi nhieu camera tren nhieu tile can test them thuc te

## Phase 4 - Download Workflow

Muc tieu:

- Download by time chay dung va de theo doi

Viec can lam:

- [x] Chuan hoa input task
- [x] Hien thi progress
- [x] Hien thi output path
- [x] Xu ly cancel va error

Done khi:

- [ ] Download file thanh cong can test thuc te voi thiet bi
- [x] Progress va log ro rang

## Preview Strategy

Can chot 1 chien luoc ro:

- `Fit`: giu dung ti le, co vien den
- `Fill`: full khung, co the crop

Khuyen nghi:

- Ban dau dung `Fit` de on dinh
- Sau khi preview host on dinh moi bo sung tuy chon `Fill`

## State Model

Nen quan ly state theo huong sau:

### Device state

- Disconnected
- Connecting
- Connected
- Reconnecting

### Live tile state

- Empty
- Selected
- Starting
- Streaming
- Error

### Download state

- Idle
- Running
- Completed
- Failed

## Logging Rules

Log phai de debug duoc theo tung lop:

- SDK init/cleanup
- Login/logout
- Channel query
- Start live / stop live
- Download start / progress / stop
- Preview host create / resize / hide / show

Khong log qua nhieu noi dung UI vuon vat khi khong can.

## Current Problems To Avoid

Nhung sai lam can tranh lap lai:

- Dung qua nhieu fallback preview trong mot method khong kiem soat
- Tron code SDK voi code layout UI
- De mot `live handle` dung chung cho nhieu tile
- Sua giao dien truoc khi chot duong di cua wrapper
- Them fix tam thoi lien tuc ma khong co ke hoach refactor

## Implementation Checklist

## Step 1

- [x] Don lai `DahuaSdkManager` o muc wrapper trung tam
- [x] Chot API wrapper cong khai
  - `initialize`
  - `cleanup`
  - `login`
  - `logout`
  - `previewChannels`
  - `startLive`
  - `stopLive`
  - `downloadByTime`
  - `stopDownload`

## Step 2

- [x] Tao lop `PreviewHost`
- [x] Chuyen logic native render ra khoi `MainWindow`

## Step 3

- [x] Noi `PreviewHost` vao tile UI
- [x] Test build + luong 1 tile o muc code path
- [ ] Xac nhan streaming 1 tile tren thiet bi that

## Step 4

- [x] Nang cap UI len 1 / 4 / 9 / 16 tile
- [x] Hoan thien public API de stop tung tile rieng
- [ ] Xac nhan 4 tile preview dong thoi tren thiet bi that

## Step 5

- [x] Hoan thien khung download by time
- [ ] Xac nhan download file that thanh cong tren thiet bi

## Step 6

- [x] Polish UI va UX

## Definition Of Done

Tai lieu nay duoc xem la dat muc tieu khi:

- App la wrapper cua Dahua SDK, khong phai ban sao SDK
- UI dep va de dung
- Preview on dinh
- Mo duoc nhieu camera
- Download chay duoc
- Code de doc, de test, de bao tri

## Next

`06_Class_Design.md`

## Update 2026-07-08

Da hoan thanh trong code:

- Public API stop live theo tung tile da duoc noi tu `DahuaSdkManager` -> `VideoManager` -> `AppController` -> `MainWindow`
- Khi doi layout 1 / 4 / 9 / 16, app chi dung nhung tile bi an thay vi dung toan bo preview
- Moi tile da co nut `Stop Tile` rieng
- `PreviewHost` da ho tro `Fit` va `Fill` de quy dinh cach video lap day khung render
- UI da bo sung dieu khien chuyen `Preview mode`

Van can xac nhan voi thiet bi that:

- Streaming 1 tile tren thiet bi that
- Streaming nhieu tile dong thoi tren thiet bi that
- Download file that thanh cong tren thiet bi that

Phan con lai o muc refactor noi bo:

- Giam bot fallback khong can thiet trong `DahuaSdkManager::startLive`
