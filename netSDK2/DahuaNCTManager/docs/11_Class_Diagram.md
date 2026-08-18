# 11. Class Diagram

## Core UML

```text
MainWindow
    |
    +--> AppController
             |
             +--> DeviceManager
             +--> VideoManager
             +--> DownloadManager
             +--> PlaybackManager
             +--> SnapshotManager
             +--> ConfigManager
             +--> Logger
             |
             +--> DahuaSdkManager (Singleton)

DeviceManager ---- DeviceInfo
VideoManager ----- VideoWidget
DownloadManager -- DownloadTask
PlaybackManager -- PlaybackTask
```

## Dependency Rules

UI -> Controller -> Manager -> SDK -> Device

Không được gọi ngược chiều.

## Singleton

- DahuaSdkManager
- Logger
- ConfigManager

## Future

- AlarmManager
- AIManager
- PTZManager
- PluginManager
