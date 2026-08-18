# 12. Sequence Diagrams

## Login

```text
User
 |
MainWindow
 |
AppController
 |
DeviceManager
 |
DahuaSdkManager
 |
CLIENT_LoginWithHighLevelSecurity
 |
NVR
```

## Live

```text
User
 |
VideoWidget
 |
VideoManager
 |
DahuaSdkManager
 |
CLIENT_RealPlayEx
```

## Download

```text
User
 |
DownloadWidget
 |
DownloadManager
 |
CLIENT_DownloadByTimeEx
 |
Callback
 |
Signal
 |
ProgressBar
```

## Playback

```text
Search
 |
PlaybackManager
 |
SDK
 |
Render
```
