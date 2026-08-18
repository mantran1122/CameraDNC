# 07_API_Reference

## Public API

### bool initSdk()

Khởi tạo Dahua NetSDK.

### void cleanupSdk()

Giải phóng SDK.

### bool login(ip, port, user, password)

Đăng nhập đầu ghi.

### void logout()

Đăng xuất.

### bool startLive(channel, QWidget\*)

Mở live view.

### void stopLive(channel)

Dừng live.

### bool downloadByTime(channel,start,end,file)

Tải video theo thời gian.

### void stopDownload()

### QString lastErrorText()

## Signals

-   loginStateChanged(bool)
-   logMessage(QString)
-   downloadProgress(int)
-   downloadFinished(bool, QString)

## Return Convention

-   true: Success
-   false: Failed

## Error

Không ném exception, trả về bool + log.

## Next

08_Testing.md
