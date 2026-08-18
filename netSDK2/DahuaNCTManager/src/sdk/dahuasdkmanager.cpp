#include "src/sdk/dahuasdkmanager.h"

#include "src/managers/loggermanager.h"

#include <QDateTime>
#include <QLibrary>
#include <QMetaObject>

#include <cstring>
#include <dhnetsdk.h>
#include <dhconfigsdk.h>

namespace {

typedef BOOL(__stdcall *PlayOpenStreamFn)(LONG nPort, BYTE *pFileHeadBuf, DWORD nSize, DWORD nBufPoolSize);
typedef BOOL(__stdcall *PlayGetFreePortFn)(LONG *nPort);
typedef BOOL(__stdcall *PlayReleasePortFn)(LONG nPort);
typedef BOOL(__stdcall *PlayPlayFn)(LONG nPort, HWND hWnd);
typedef BOOL(__stdcall *PlayInputDataFn)(LONG nPort, BYTE *pBuf, DWORD nSize);
typedef BOOL(__stdcall *PlayStopFn)(LONG nPort);
typedef BOOL(__stdcall *PlayCloseStreamFn)(LONG nPort);
typedef BOOL(__stdcall *PlaySetViewProportionFn)(LONG nPort, int nWidthProportion, int nHeightProportion);
typedef BOOL(__stdcall *PlayViewResolutionChangedFn)(LONG nPort, int nWidth, int nHeight, DWORD nRegionNum);
typedef DWORD(__stdcall *PlayGetLastErrorFn)(LONG nPort);

struct PlaySdkState
{
    QLibrary module;
    PlayGetFreePortFn getFreePort = nullptr;
    PlayReleasePortFn releasePort = nullptr;
    PlayOpenStreamFn openStream = nullptr;
    PlayPlayFn play = nullptr;
    PlayInputDataFn inputData = nullptr;
    PlayStopFn stop = nullptr;
    PlayCloseStreamFn closeStream = nullptr;
    PlaySetViewProportionFn setViewProportion = nullptr;
    PlayViewResolutionChangedFn viewResolutionChanged = nullptr;
    PlayGetLastErrorFn getLastError = nullptr;
};

PlaySdkState g_playSdkState;

HWND toRenderTargetHandle(quintptr renderHandle)
{
    if (renderHandle == 0) {
        return nullptr;
    }

    return reinterpret_cast<HWND>(renderHandle);
}

bool loadPlaySdk()
{
    if (g_playSdkState.module.isLoaded()) {
        return g_playSdkState.getFreePort != nullptr
            && g_playSdkState.releasePort != nullptr
            && g_playSdkState.openStream != nullptr
            && g_playSdkState.play != nullptr
            && g_playSdkState.inputData != nullptr
            && g_playSdkState.stop != nullptr
            && g_playSdkState.closeStream != nullptr
            && g_playSdkState.setViewProportion != nullptr
            && g_playSdkState.viewResolutionChanged != nullptr;
    }

    g_playSdkState.module.setFileName(QStringLiteral("play"));
    if (!g_playSdkState.module.load()) {
        return false;
    }

    g_playSdkState.getFreePort = reinterpret_cast<PlayGetFreePortFn>(g_playSdkState.module.resolve("PLAY_GetFreePort"));
    g_playSdkState.releasePort = reinterpret_cast<PlayReleasePortFn>(g_playSdkState.module.resolve("PLAY_ReleasePort"));
    g_playSdkState.openStream = reinterpret_cast<PlayOpenStreamFn>(g_playSdkState.module.resolve("PLAY_OpenStream"));
    g_playSdkState.play = reinterpret_cast<PlayPlayFn>(g_playSdkState.module.resolve("PLAY_Play"));
    g_playSdkState.inputData = reinterpret_cast<PlayInputDataFn>(g_playSdkState.module.resolve("PLAY_InputData"));
    g_playSdkState.stop = reinterpret_cast<PlayStopFn>(g_playSdkState.module.resolve("PLAY_Stop"));
    g_playSdkState.closeStream = reinterpret_cast<PlayCloseStreamFn>(g_playSdkState.module.resolve("PLAY_CloseStream"));
    g_playSdkState.setViewProportion = reinterpret_cast<PlaySetViewProportionFn>(g_playSdkState.module.resolve("PLAY_SetViewProportion"));
    g_playSdkState.viewResolutionChanged = reinterpret_cast<PlayViewResolutionChangedFn>(g_playSdkState.module.resolve("PLAY_ViewResolutionChanged"));
    g_playSdkState.getLastError = reinterpret_cast<PlayGetLastErrorFn>(g_playSdkState.module.resolve("PLAY_GetLastError"));

    return g_playSdkState.getFreePort != nullptr
        && g_playSdkState.releasePort != nullptr
        && g_playSdkState.openStream != nullptr
        && g_playSdkState.play != nullptr
        && g_playSdkState.inputData != nullptr
        && g_playSdkState.stop != nullptr
        && g_playSdkState.closeStream != nullptr
        && g_playSdkState.setViewProportion != nullptr
        && g_playSdkState.viewResolutionChanged != nullptr;
}

QString summarizePreviewChannels(const QVector<PreviewChannelInfo> &channels)
{
    QStringList labels;
    labels.reserve(channels.size());
    for (const PreviewChannelInfo &channel : channels) {
        labels.append(QStringLiteral("%1:%2").arg(channel.sdkChannel).arg(channel.displayName));
    }
    return labels.join(QStringLiteral(" | "));
}

QStringList queryRtspUrls(qint64 loginHandle, int channel)
{
    NET_DEV_RTSPURL_LIST rtspUrls = {};
    rtspUrls.dwSize = sizeof(rtspUrls);
    rtspUrls.nChannelID = channel;

    int returnedLength = 0;
    if (!CLIENT_QueryDevState(static_cast<LLONG>(loginHandle),
                              DH_DEVSTATE_RTSP_URL,
                              reinterpret_cast<char *>(&rtspUrls),
                              sizeof(rtspUrls),
                              &returnedLength)) {
        return {};
    }

    QStringList urls;
    for (int index = 0; index < rtspUrls.nUrlNum && index < DH_MAX_URL_NUM; ++index) {
        const QString url = QString::fromLocal8Bit(rtspUrls.szURLList[index]).trimmed();
        if (!url.isEmpty()) {
            urls.append(url);
        }
    }
    return urls;
}

void stopPlaySdkStream(long port)
{
    if (port < 0) {
        return;
    }

    if (g_playSdkState.stop != nullptr) {
        g_playSdkState.stop(port);
    }
    if (g_playSdkState.closeStream != nullptr) {
        g_playSdkState.closeStream(port);
    }
    if (g_playSdkState.releasePort != nullptr) {
        g_playSdkState.releasePort(port);
    }
}

QString formatPlaySdkError(long port)
{
    if (g_playSdkState.getLastError == nullptr) {
        return QStringLiteral("PlaySDK error");
    }

    const DWORD errorCode = g_playSdkState.getLastError(port);
    return QStringLiteral("PlaySDK error 0x%1").arg(QString::number(errorCode, 16).toUpper());
}

void CALLBACK handleDisconnect(LLONG, char *deviceIp, LONG devicePort, LDWORD)
{
    DahuaSdkManager &instance = DahuaSdkManager::instance();
    const QString host = QString::fromLocal8Bit(deviceIp ? deviceIp : "");
    QMetaObject::invokeMethod(
        &instance,
        [host, devicePort, &instance]() {
            LoggerManager::instance().logWarning(QStringLiteral("Disconnected from %1:%2").arg(host).arg(devicePort));
            emit instance.deviceDisconnected(host, static_cast<int>(devicePort));
            emit instance.connectionStateChanged(false, QStringLiteral("Reconnecting %1:%2").arg(host).arg(devicePort));
        },
        Qt::QueuedConnection);
}

void CALLBACK handleReconnect(LLONG, char *deviceIp, LONG devicePort, LDWORD)
{
    DahuaSdkManager &instance = DahuaSdkManager::instance();
    const QString host = QString::fromLocal8Bit(deviceIp ? deviceIp : "");
    QMetaObject::invokeMethod(
        &instance,
        [host, devicePort, &instance]() {
            LoggerManager::instance().logInfo(QStringLiteral("Reconnected to %1:%2").arg(host).arg(devicePort));
            emit instance.deviceReconnected(host, static_cast<int>(devicePort));
            emit instance.connectionStateChanged(true, QStringLiteral("Reconnected to %1:%2").arg(host).arg(devicePort));
        },
        Qt::QueuedConnection);
}

void CALLBACK handleDownloadProgress(LLONG, DWORD totalSize, DWORD downloadedSize, int, NET_RECORDFILE_INFO, LDWORD)
{
    DahuaSdkManager &instance = DahuaSdkManager::instance();
    QMetaObject::invokeMethod(
        &instance,
        [totalSize, downloadedSize, &instance]() {
            if (downloadedSize == static_cast<DWORD>(-1)) {
                instance.stopDownload();
                LoggerManager::instance().logInfo(QStringLiteral("Download completed"));
                emit instance.downloadProgressChanged(100);
                emit instance.downloadStateChanged(false, QStringLiteral("Download completed"));
                return;
            }

            if (downloadedSize == static_cast<DWORD>(-2)) {
                instance.stopDownload();
                LoggerManager::instance().logError(QStringLiteral("Download failed during transfer"));
                emit instance.downloadStateChanged(false, QStringLiteral("Download failed during transfer"));
                return;
            }

            if (totalSize > 0 && downloadedSize <= totalSize) {
                const int progress = static_cast<int>((static_cast<double>(downloadedSize) / static_cast<double>(totalSize)) * 100.0);
                emit instance.downloadProgressChanged(progress);
            }
        },
        Qt::QueuedConnection);
}

void CALLBACK handleRealData(LLONG realHandle, DWORD dataType, BYTE *buffer, DWORD bufferSize, LLONG, LDWORD)
{
    if (dataType != 0 || buffer == nullptr || bufferSize == 0 || g_playSdkState.inputData == nullptr) {
        return;
    }

    DahuaSdkManager::instance().feedPlaySdkData(static_cast<qint64>(realHandle), buffer, bufferSize);
}

NET_TIME toNetTime(const QDateTime &dateTime)
{
    const QDate date = dateTime.date();
    const QTime time = dateTime.time();

    NET_TIME netTime = {};
    netTime.dwYear = static_cast<DWORD>(date.year());
    netTime.dwMonth = static_cast<DWORD>(date.month());
    netTime.dwDay = static_cast<DWORD>(date.day());
    netTime.dwHour = static_cast<DWORD>(time.hour());
    netTime.dwMinute = static_cast<DWORD>(time.minute());
    netTime.dwSecond = static_cast<DWORD>(time.second());
    return netTime;
}

QString describeErrorCode(unsigned long errorCode)
{
    switch (errorCode) {
    case NET_INVALID_HANDLE:
        return QStringLiteral("Invalid SDK handle or unsupported preview target");
    case NET_DEV_VER_NOMATCH:
        return QStringLiteral("Device protocol version does not match the SDK");
    case NET_OPEN_CHANNEL_ERROR:
        return QStringLiteral("Failed to open the requested device channel");
    case NET_ILLEGAL_PARAM:
        return QStringLiteral("One or more SDK parameters are invalid");
    case NET_RENDER_OPEN_ERROR:
        return QStringLiteral("Unable to create the preview render surface");
    case NET_SDK_INIT_ERROR:
    case NET_NO_INIT:
        return QStringLiteral("SDK is not initialized");
    case NET_LOGIN_ERROR_PASSWORD:
    case NET_LOGIN_ERROR_USER_OR_PASSOWRD:
        return QStringLiteral("Invalid username or password");
    case NET_LOGIN_ERROR_USER:
        return QStringLiteral("The user account does not exist");
    case NET_LOGIN_ERROR_TIMEOUT:
        return QStringLiteral("Login timed out");
    case NET_LOGIN_ERROR_CONNECT:
    case NET_LOGIN_ERROR_NETWORK:
        return QStringLiteral("Unable to reach device over the network");
    case NET_LOGIN_ERROR_RELOGGIN:
        return QStringLiteral("Device session is already active");
    case NET_NOT_SUPPORTED:
    case NET_ERROR_UNSUPPORTED:
        return QStringLiteral("Operation is not supported by the device");
    case NET_NO_RECORD_FOUND:
    case NET_ERROR_NO_RECORD:
        return QStringLiteral("No record found for the requested time range");
    default:
        return QStringLiteral("Unmapped SDK error");
    }
}

} // namespace

DahuaSdkManager::DahuaSdkManager(QObject *parent)
    : QObject(parent)
{
}

DahuaSdkManager &DahuaSdkManager::instance()
{
    static DahuaSdkManager instance;
    return instance;
}

bool DahuaSdkManager::initialize()
{
    if (m_initialized) {
        return true;
    }

    if (!CLIENT_Init(&handleDisconnect, 0)) {
        m_lastError = formatLastError();
        LoggerManager::instance().logError(QStringLiteral("SDK init failed: %1").arg(m_lastError));
        emit sdkLogMessage(QStringLiteral("SDK init failed: %1").arg(m_lastError));
        return false;
    }

    CLIENT_SetAutoReconnect(&handleReconnect, 0);
    m_initialized = true;
    LoggerManager::instance().logInfo(QStringLiteral("Dahua NetSDK initialized"));
    emit sdkLogMessage(QStringLiteral("Dahua NetSDK initialized"));
    return true;
}

void DahuaSdkManager::cleanup()
{
    if (!m_initialized) {
        return;
    }

    logout();
    CLIENT_Cleanup();
    m_initialized = false;
    LoggerManager::instance().logInfo(QStringLiteral("Dahua NetSDK cleaned up"));
    emit sdkLogMessage(QStringLiteral("Dahua NetSDK cleaned up"));
}

bool DahuaSdkManager::login(const DeviceConnectionInfo &deviceInfo)
{
    if (!initialize()) {
        return false;
    }

    releasePreviewLogin();
    m_lastConnectionInfo = deviceInfo;

    NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY input = {};
    input.dwSize = sizeof(input);
    input.nPort = deviceInfo.port;
    input.emSpecCap = EM_LOGIN_SPEC_CAP_TCP;
    input.nClientType = 3;

    const QByteArray hostBytes = deviceInfo.host.toLocal8Bit();
    const QByteArray usernameBytes = deviceInfo.username.toLocal8Bit();
    const QByteArray passwordBytes = deviceInfo.password.toLocal8Bit();

    std::strncpy(input.szIP, hostBytes.constData(), sizeof(input.szIP) - 1);
    std::strncpy(input.szUserName, usernameBytes.constData(), sizeof(input.szUserName) - 1);
    std::strncpy(input.szPassword, passwordBytes.constData(), sizeof(input.szPassword) - 1);

    NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY output = {};
    output.dwSize = sizeof(output);

    m_loginHandle = static_cast<qint64>(CLIENT_LoginWithHighLevelSecurity(&input, &output));
    if (m_loginHandle == 0) {
        m_channelCount = 0;
        m_previewChannels.clear();
        m_lastError = formatLastError();
        const QString message = QStringLiteral("Login failed for %1:%2 (%3)")
                                    .arg(deviceInfo.host)
                                    .arg(deviceInfo.port)
                                    .arg(m_lastError);
        LoggerManager::instance().logError(message);
        emitConnectionEvent(false, message);
        return false;
    }

    m_channelCount = qMax(0, output.stuDeviceInfo.nChanNum);
    m_previewChannels.clear();

    EM_DEV_PROTOCOL_TYPE protocolType = EM_DEV_PROTOCOL_GENERAL;
    if (CLIENT_GetDevProtocolType(static_cast<LLONG>(m_loginHandle), &protocolType)) {
        LoggerManager::instance().logInfo(
            QStringLiteral("Device protocol type reported by SDK: %1").arg(static_cast<int>(protocolType)));
    } else {
        LoggerManager::instance().logWarning(QStringLiteral("Unable to query device protocol type"));
    }

    int returnedLength = 0;
    NET_DEV_CHN_COUNT_INFO channelInfo = {sizeof(NET_DEV_CHN_COUNT_INFO)};
    channelInfo.stuVideoIn.dwSize = sizeof(channelInfo.stuVideoIn);
    channelInfo.stuVideoOut.dwSize = sizeof(channelInfo.stuVideoOut);
    if (CLIENT_QueryDevState(static_cast<LLONG>(m_loginHandle),
                             DH_DEVSTATE_DEV_CHN_COUNT,
                             reinterpret_cast<char *>(&channelInfo),
                             channelInfo.dwSize,
                             &returnedLength)) {
        m_channelCount = qMax(m_channelCount, channelInfo.stuVideoIn.nMaxTotal);
        LoggerManager::instance().logInfo(
            QStringLiteral("Device channel report: login=%1, video-in-total=%2, video-out-total=%3")
                .arg(output.stuDeviceInfo.nChanNum)
                .arg(channelInfo.stuVideoIn.nMaxTotal)
                .arg(channelInfo.stuVideoOut.nMaxTotal));
    } else {
        LoggerManager::instance().logWarning(
            QStringLiteral("Unable to query detailed channel count, falling back to login info (%1 channels)")
                .arg(m_channelCount));
    }

    DH_IN_MATRIX_GET_CAMERAS matrixInput = {sizeof(DH_IN_MATRIX_GET_CAMERAS)};
    DH_OUT_MATRIX_GET_CAMERAS matrixOutput = {sizeof(DH_OUT_MATRIX_GET_CAMERAS)};
    QVector<DH_MATRIX_CAMERA_INFO> matrixCameras(256);
    for (DH_MATRIX_CAMERA_INFO &camera : matrixCameras) {
        std::memset(&camera, 0, sizeof(DH_MATRIX_CAMERA_INFO));
        camera.dwSize = sizeof(DH_MATRIX_CAMERA_INFO);
        camera.stuRemoteDevice.dwSize = sizeof(DH_REMOTE_DEVICE);
    }
    matrixOutput.pstuCameras = matrixCameras.data();
    matrixOutput.nMaxCameraCount = matrixCameras.size();

    if (CLIENT_MatrixGetCameras(static_cast<LLONG>(m_loginHandle), &matrixInput, &matrixOutput, 1000)) {
        for (int index = 0; index < matrixOutput.nRetCameraCount; ++index) {
            const DH_MATRIX_CAMERA_INFO &camera = matrixCameras.at(index);
            PreviewChannelInfo info;
            info.sdkChannel = camera.nUniqueChannel;
            const QString channelName = QString::fromLocal8Bit(camera.szName).trimmed();
            info.displayName = channelName.isEmpty()
                                   ? QStringLiteral("CH-%1  Matrix Camera").arg(camera.nUniqueChannel + 1, 2, 10, QLatin1Char('0'))
                                   : QStringLiteral("CH-%1  %2")
                                         .arg(camera.nUniqueChannel + 1, 2, 10, QLatin1Char('0'))
                                         .arg(channelName);
            m_previewChannels.append(info);
        }

        if (!m_previewChannels.isEmpty()) {
            LoggerManager::instance().logInfo(
                QStringLiteral("Matrix camera report: %1 unique channels discovered").arg(m_previewChannels.size()));
        }
    } else {
        LoggerManager::instance().logWarning(QStringLiteral("Matrix camera query failed for this device"));
    }

    if (m_previewChannels.isEmpty()) {
        QVector<DEV_ENCODER_INFO> encoderInfos(128);
        DEV_ENCODER_CFG_EX2 encoderConfig = {};
        encoderConfig.nDevInfoMaxNum = encoderInfos.size();
        encoderConfig.pstuDevInfo = encoderInfos.data();

        DWORD bytesReturned = 0;
        if (CLIENT_GetDevConfig(static_cast<LLONG>(m_loginHandle),
                                DH_DEV_ENCODER_CFG_EX2,
                                -1,
                                &encoderConfig,
                                sizeof(encoderConfig),
                                &bytesReturned,
                                1000)) {
            for (int index = 0; index < qMin(encoderConfig.nChannels, encoderInfos.size()); ++index) {
                const DEV_ENCODER_INFO &encoder = encoderInfos.at(index);
                const int sdkChannel = encoder.dwDecoderID > 0
                                           ? static_cast<int>(encoder.dwDecoderID)
                                           : index;
                const QString channelName = QString::fromLocal8Bit(encoder.szChnName).trimmed();
                const QString deviceName = QString::fromLocal8Bit(encoder.szDevName).trimmed();

                PreviewChannelInfo info;
                info.sdkChannel = sdkChannel;
                info.displayName = channelName.isEmpty()
                                       ? QStringLiteral("CH-%1  %2")
                                             .arg(sdkChannel + 1, 2, 10, QLatin1Char('0'))
                                             .arg(deviceName.isEmpty() ? QStringLiteral("Encoder") : deviceName)
                                       : QStringLiteral("CH-%1  %2")
                                             .arg(sdkChannel + 1, 2, 10, QLatin1Char('0'))
                                             .arg(channelName);
                m_previewChannels.append(info);

                LoggerManager::instance().logInfo(
                    QStringLiteral("Encoder map[%1]: sdkChannel=%2, remoteChannel=%3, device=%4, ip=%5")
                        .arg(index)
                        .arg(sdkChannel)
                        .arg(encoder.nDevChannel)
                        .arg(deviceName.isEmpty() ? QStringLiteral("--") : deviceName)
                        .arg(QString::fromLocal8Bit(encoder.szDevIp).trimmed()));
            }

            if (!m_previewChannels.isEmpty()) {
                LoggerManager::instance().logInfo(
                    QStringLiteral("Encoder config report: %1 channels discovered").arg(m_previewChannels.size()));
            }
        } else {
            LoggerManager::instance().logWarning(QStringLiteral("Encoder config query failed for this device"));
        }
    }

    if (m_previewChannels.isEmpty()) {
        constexpr int maxJsonBytes = 256 * 1024;
        QByteArray jsonBuffer(maxJsonBytes, '\0');
        int remoteDeviceError = 0;
        if (CLIENT_GetNewDevConfig(static_cast<LLONG>(m_loginHandle),
                                   const_cast<char *>(CFG_CMD_REMOTEDEVICE),
                                   -1,
                                   jsonBuffer.data(),
                                   static_cast<DWORD>(jsonBuffer.size()),
                                   &remoteDeviceError,
                                   1000,
                                   nullptr)) {
            QVector<AV_CFG_RemoteDevice> remoteDevices(128);
            for (AV_CFG_RemoteDevice &device : remoteDevices) {
                std::memset(&device, 0, sizeof(AV_CFG_RemoteDevice));
                device.nStructSize = sizeof(AV_CFG_RemoteDevice);
            }

            int parsedBytes = 0;
            if (CLIENT_ParseData(const_cast<char *>(CFG_CMD_REMOTEDEVICE),
                                 jsonBuffer.data(),
                                 remoteDevices.data(),
                                 static_cast<DWORD>(sizeof(AV_CFG_RemoteDevice) * remoteDevices.size()),
                                 &parsedBytes)) {
                const int remoteDeviceCount = parsedBytes / static_cast<int>(sizeof(AV_CFG_RemoteDevice));
                LoggerManager::instance().logInfo(
                    QStringLiteral("Remote device report: %1 remote devices discovered").arg(remoteDeviceCount));

                for (int index = 0; index < remoteDeviceCount && index < remoteDevices.size(); ++index) {
                    const AV_CFG_RemoteDevice &device = remoteDevices.at(index);
                    LoggerManager::instance().logInfo(
                        QStringLiteral("Remote device[%1]: id=%2, name=%3, ip=%4, protocol=%5, videoChannels=%6")
                            .arg(index)
                            .arg(QString::fromLocal8Bit(device.szID).trimmed())
                            .arg(QString::fromLocal8Bit(device.szName).trimmed())
                            .arg(QString::fromLocal8Bit(device.szIP).trimmed())
                            .arg(QString::fromLocal8Bit(device.szProtocol).trimmed())
                            .arg(device.nVideoChannel));
                }
            } else {
                LoggerManager::instance().logWarning(QStringLiteral("Remote device config parse failed for this device"));
            }
        } else {
            LoggerManager::instance().logWarning(
                QStringLiteral("Remote device config query failed for this device (error=%1)").arg(remoteDeviceError));
        }
    }

    if (m_previewChannels.isEmpty()) {
        for (int index = 0; index < m_channelCount; ++index) {
            PreviewChannelInfo info;
            info.sdkChannel = index;
            info.displayName = QStringLiteral("CH-%1  Main Stream").arg(index + 1, 2, 10, QLatin1Char('0'));
            m_previewChannels.append(info);
        }
    }

    LoggerManager::instance().logInfo(
        QStringLiteral("Preview channel candidates: %1").arg(summarizePreviewChannels(m_previewChannels)));

    const QString message = QStringLiteral("Connected to %1:%2").arg(deviceInfo.host).arg(deviceInfo.port);
    LoggerManager::instance().logInfo(message);
    emitConnectionEvent(true, message);
    return true;
}

void DahuaSdkManager::logout()
{
    stopLive();
    stopDownload();
    releasePreviewLogin();
    if (m_loginHandle == 0) {
        m_channelCount = 0;
        m_previewChannels.clear();
        return;
    }

    CLIENT_Logout(m_loginHandle);
    m_loginHandle = 0;
    m_channelCount = 0;
    m_previewChannels.clear();
    LoggerManager::instance().logInfo(QStringLiteral("Device logged out"));
    emitConnectionEvent(false, QStringLiteral("Device logged out"));
}

bool DahuaSdkManager::startLive(int channel, quintptr renderHandleToken, int renderWidth, int renderHeight)
{
    if (m_loginHandle == 0 || renderHandleToken == 0) {
        const QString message = QStringLiteral("Live view requires an active login and a valid render target");
        LoggerManager::instance().logWarning(message);
        emit liveStateChanged(false, message);
        return false;
    }

    for (int index = m_liveSessions.size() - 1; index >= 0; --index) {
        if (m_liveSessions.at(index).renderHandle == renderHandleToken) {
            stopLiveSession(index);
        }
    }

    HWND renderHandle = toRenderTargetHandle(renderHandleToken);
    if (renderHandle == nullptr) {
        const QString message = QStringLiteral("Unable to prepare a native preview surface for live view");
        LoggerManager::instance().logError(message);
        emit liveStateChanged(false, message);
        return false;
    }

    LivePreviewSession session;
    session.renderHandle = renderHandleToken;
    session.channel = channel;

    if (m_previewFillMode) {
        if (!loadPlaySdk()) {
            const QString message = QStringLiteral("Unable to load play.dll for fill preview mode");
            LoggerManager::instance().logError(message);
            emit liveStateChanged(false, message);
            return false;
        }

        LONG playPort = -1;
        if (!g_playSdkState.getFreePort(&playPort)) {
            const QString message = QStringLiteral("PlaySDK failed to allocate a preview port");
            LoggerManager::instance().logError(message);
            emit liveStateChanged(false, message);
            return false;
        }

        if (!g_playSdkState.openStream(playPort, nullptr, 0, 1024 * 512 * 6)) {
            const QString message = QStringLiteral("PlaySDK failed to open stream buffer (%1)").arg(formatPlaySdkError(playPort));
            LoggerManager::instance().logError(message);
            g_playSdkState.releasePort(playPort);
            emit liveStateChanged(false, message);
            return false;
        }

        const int hostWidth = qMax(1, renderWidth);
        const int hostHeight = qMax(1, renderHeight);

        if (!g_playSdkState.play(playPort, renderHandle)) {
            const QString message = QStringLiteral("PlaySDK failed to bind preview surface (%1)").arg(formatPlaySdkError(playPort));
            LoggerManager::instance().logError(message);
            stopPlaySdkStream(playPort);
            emit liveStateChanged(false, message);
            return false;
        }

        g_playSdkState.setViewProportion(playPort, hostWidth, hostHeight);
        g_playSdkState.viewResolutionChanged(playPort, hostWidth, hostHeight, 0);

        session.callbackMode = true;
        session.playPort = playPort;

        session.handle = static_cast<qint64>(CLIENT_RealPlayEx(static_cast<LLONG>(m_loginHandle),
                                                               channel,
                                                               nullptr,
                                                               DH_RType_Realplay_0));
        if (session.handle == 0) {
            session.handle = static_cast<qint64>(CLIENT_RealPlayEx(static_cast<LLONG>(m_loginHandle),
                                                                   channel,
                                                                   nullptr));
        }

        if (session.handle == 0) {
            stopPlaySdkStream(playPort);
            m_lastError = formatLastError();
            const QString message = QStringLiteral("Start live failed on channel %1 in fill preview mode (%2)")
                                        .arg(channel)
                                        .arg(m_lastError);
            LoggerManager::instance().logError(message);
            emit liveStateChanged(false, message);
            return false;
        }

        if (!CLIENT_SetRealDataCallBackEx2(static_cast<LLONG>(session.handle), &handleRealData, 0, REALDATA_FLAG_RAW_DATA)) {
            m_lastError = formatLastError();
            const QString message = QStringLiteral("Live stream opened but fill-mode callback registration failed (%1)").arg(m_lastError);
            LoggerManager::instance().logError(message);
            CLIENT_StopRealPlayEx(static_cast<LLONG>(session.handle));
            stopPlaySdkStream(playPort);
            emit liveStateChanged(false, message);
            return false;
        }

        m_liveSessions.append(session);
        const QString message = QStringLiteral("Live preview started on channel %1 using fill preview mode").arg(channel);
        LoggerManager::instance().logInfo(message);
        emit liveStateChanged(true, message);
        return true;
    }

    NET_IN_REALPLAY_BY_DATA_TYPE directPlayIn = {sizeof(NET_IN_REALPLAY_BY_DATA_TYPE)};
    directPlayIn.nChannelID = channel;
    directPlayIn.hWnd = renderHandle;
    directPlayIn.rType = DH_RType_Realplay;
    directPlayIn.emDataType = EM_REAL_DATA_TYPE_PRIVATE;

    NET_OUT_REALPLAY_BY_DATA_TYPE directPlayOut = {sizeof(NET_OUT_REALPLAY_BY_DATA_TYPE)};
    session.handle = static_cast<qint64>(CLIENT_RealPlayByDataType(static_cast<LLONG>(m_loginHandle),
                                                                   &directPlayIn,
                                                                   &directPlayOut,
                                                                   5000));
    if (session.handle != 0) {
        m_liveSessions.append(session);
        const QString message = QStringLiteral("Live preview started on channel %1 using RealPlayByDataType").arg(channel);
        LoggerManager::instance().logInfo(message);
        emit liveStateChanged(true, message);
        return true;
    }

    const QString realPlayByTypeError = formatLastError();
    LoggerManager::instance().logWarning(
        QStringLiteral("RealPlayByDataType failed on channel %1 (%2), retrying with direct RealPlayEx main-stream type")
            .arg(channel)
            .arg(realPlayByTypeError));

    session.handle = static_cast<qint64>(CLIENT_RealPlayEx(static_cast<LLONG>(m_loginHandle),
                                                           channel,
                                                           renderHandle,
                                                           DH_RType_Realplay_0));
    if (session.handle != 0) {
        m_liveSessions.append(session);
        const QString message = QStringLiteral("Live preview started on channel %1 using direct RealPlayEx main-stream type")
                                    .arg(channel);
        LoggerManager::instance().logInfo(message);
        emit liveStateChanged(true, message);
        return true;
    }

    const QString directMainStreamError = formatLastError();
    LoggerManager::instance().logWarning(
        QStringLiteral("Direct RealPlayEx main-stream type failed on channel %1 (%2), retrying with default RealPlayEx")
            .arg(channel)
            .arg(directMainStreamError));

    session.handle = static_cast<qint64>(CLIENT_RealPlayEx(static_cast<LLONG>(m_loginHandle),
                                                           channel,
                                                           renderHandle));
    if (session.handle != 0) {
        m_liveSessions.append(session);
        const QString message = QStringLiteral("Live preview started on channel %1 using direct RealPlayEx").arg(channel);
        LoggerManager::instance().logInfo(message);
        emit liveStateChanged(true, message);
        return true;
    }

    const QString directRealPlayError = formatLastError();
    LoggerManager::instance().logWarning(
        QStringLiteral("Direct RealPlayEx failed on channel %1 (%2), retrying through legacy preview login")
            .arg(channel)
            .arg(directRealPlayError));

    if (ensurePreviewLogin()) {
        const LLONG previewLoginHandle = static_cast<LLONG>(m_previewLoginHandle);

        session.handle = static_cast<qint64>(CLIENT_StartRealPlay(previewLoginHandle,
                                                                  channel,
                                                                  renderHandle,
                                                                  DH_RType_Realplay_0,
                                                                  nullptr,
                                                                  nullptr,
                                                                  0,
                                                                  5000));
        if (session.handle != 0) {
            m_liveSessions.append(session);
            const QString message = QStringLiteral("Live preview started on channel %1 using legacy preview login + CLIENT_StartRealPlay")
                                        .arg(channel);
            LoggerManager::instance().logInfo(message);
            emit liveStateChanged(true, message);
            return true;
        }

        LoggerManager::instance().logWarning(
            QStringLiteral("Legacy preview login CLIENT_StartRealPlay failed on channel %1 (%2), retrying with CLIENT_RealPlay")
                .arg(channel)
                .arg(formatLastError()));

        session.handle = static_cast<qint64>(CLIENT_RealPlay(previewLoginHandle, channel, renderHandle));
        if (session.handle != 0) {
            m_liveSessions.append(session);
            const QString message = QStringLiteral("Live preview started on channel %1 using legacy preview login + CLIENT_RealPlay")
                                        .arg(channel);
            LoggerManager::instance().logInfo(message);
            emit liveStateChanged(true, message);
            return true;
        }

        LoggerManager::instance().logWarning(
            QStringLiteral("Legacy preview login CLIENT_RealPlay failed on channel %1 (%2), retrying with CLIENT_RealPlayEx2")
                .arg(channel)
                .arg(formatLastError()));

        NET_IN_REALPLAY previewLoginRealPlayIn = {};
        previewLoginRealPlayIn.dwSize = sizeof(previewLoginRealPlayIn);
        previewLoginRealPlayIn.nChannelID = channel;
        previewLoginRealPlayIn.rType = DH_RType_Realplay_0;
        previewLoginRealPlayIn.hWnd = renderHandle;
        previewLoginRealPlayIn.bWait = TRUE;

        NET_OUT_REALPLAY previewLoginRealPlayOut = {};
        previewLoginRealPlayOut.dwSize = sizeof(previewLoginRealPlayOut);

        session.handle = static_cast<qint64>(CLIENT_RealPlayEx2(previewLoginHandle,
                                                                &previewLoginRealPlayIn,
                                                                &previewLoginRealPlayOut,
                                                                5000));
        if (session.handle != 0) {
            m_liveSessions.append(session);
            const QString message = QStringLiteral("Live preview started on channel %1 using legacy preview login + CLIENT_RealPlayEx2")
                                        .arg(channel);
            LoggerManager::instance().logInfo(message);
            emit liveStateChanged(true, message);
            return true;
        }

        LoggerManager::instance().logWarning(
            QStringLiteral("Legacy preview login CLIENT_RealPlayEx2 failed on channel %1 (%2), falling back to current-session legacy APIs")
                .arg(channel)
                .arg(formatLastError()));
    } else {
        LoggerManager::instance().logWarning(QStringLiteral("Legacy preview login is unavailable, continuing with current-session fallbacks"));
    }

    session.handle = static_cast<qint64>(CLIENT_StartRealPlay(static_cast<LLONG>(m_loginHandle),
                                                              channel,
                                                              renderHandle,
                                                              DH_RType_Realplay_0,
                                                              nullptr,
                                                              nullptr,
                                                              0,
                                                              5000));
    if (session.handle != 0) {
        m_liveSessions.append(session);
        const QString message = QStringLiteral("Live preview started on channel %1 using legacy CLIENT_StartRealPlay")
                                    .arg(channel);
        LoggerManager::instance().logInfo(message);
        emit liveStateChanged(true, message);
        return true;
    }

    const QString startRealPlayError = formatLastError();
    LoggerManager::instance().logWarning(
        QStringLiteral("Legacy CLIENT_StartRealPlay failed on channel %1 (%2), retrying with CLIENT_RealPlay")
            .arg(channel)
            .arg(startRealPlayError));

    session.handle = static_cast<qint64>(CLIENT_RealPlay(static_cast<LLONG>(m_loginHandle), channel, renderHandle));
    if (session.handle != 0) {
        m_liveSessions.append(session);
        const QString message = QStringLiteral("Live preview started on channel %1 using legacy CLIENT_RealPlay").arg(channel);
        LoggerManager::instance().logInfo(message);
        emit liveStateChanged(true, message);
        return true;
    }

    const QString legacyRealPlayError = formatLastError();
    LoggerManager::instance().logWarning(
        QStringLiteral("Legacy CLIENT_RealPlay failed on channel %1 (%2), retrying with CLIENT_RealPlayEx2")
            .arg(channel)
            .arg(legacyRealPlayError));

    NET_IN_REALPLAY realPlayIn = {};
    realPlayIn.dwSize = sizeof(realPlayIn);
    realPlayIn.nChannelID = channel;
    realPlayIn.rType = DH_RType_Realplay_0;
    realPlayIn.hWnd = renderHandle;
    realPlayIn.bWait = TRUE;

    NET_OUT_REALPLAY realPlayOut = {};
    realPlayOut.dwSize = sizeof(realPlayOut);

    session.handle = static_cast<qint64>(CLIENT_RealPlayEx2(static_cast<LLONG>(m_loginHandle),
                                                            &realPlayIn,
                                                            &realPlayOut,
                                                            5000));
    if (session.handle != 0) {
        m_liveSessions.append(session);
        const QString message = QStringLiteral("Live preview started on channel %1 using CLIENT_RealPlayEx2").arg(channel);
        LoggerManager::instance().logInfo(message);
        emit liveStateChanged(true, message);
        return true;
    }

    const QString realPlayEx2Error = formatLastError();
    LoggerManager::instance().logWarning(
        QStringLiteral("CLIENT_RealPlayEx2 failed on channel %1 (%2), switching to callback preview mode")
            .arg(channel)
            .arg(realPlayEx2Error));

    const QStringList rtspUrls = queryRtspUrls(m_loginHandle, channel);
    if (!rtspUrls.isEmpty()) {
        LoggerManager::instance().logInfo(
            QStringLiteral("RTSP URL candidates for channel %1: %2").arg(channel).arg(rtspUrls.join(QStringLiteral(" | "))));
    } else {
        LoggerManager::instance().logWarning(
            QStringLiteral("No RTSP URL candidates reported by SDK for channel %1").arg(channel));
    }

    if (!loadPlaySdk()) {
        const QString message = QStringLiteral("Unable to load play.dll for callback-based preview");
        LoggerManager::instance().logError(message);
        emit liveStateChanged(false, message);
        return false;
    }

    if (!m_liveSessions.isEmpty()) {
        const QString message = QStringLiteral("Multi-camera preview is unavailable because this device fell back to callback preview mode");
        LoggerManager::instance().logWarning(message);
        emit liveStateChanged(true, message);
        return false;
    }

    LONG playPort = -1;
    if (!g_playSdkState.getFreePort(&playPort)) {
        const QString message = QStringLiteral("PlaySDK failed to allocate a preview port");
        LoggerManager::instance().logError(message);
        emit liveStateChanged(false, message);
        return false;
    }

    if (!g_playSdkState.openStream(playPort, nullptr, 0, 1024 * 512 * 6)) {
        const QString message = QStringLiteral("PlaySDK failed to open stream buffer (%1)").arg(formatPlaySdkError(playPort));
        LoggerManager::instance().logError(message);
        g_playSdkState.releasePort(playPort);
        emit liveStateChanged(false, message);
        return false;
    }

    if (!g_playSdkState.play(playPort, renderHandle)) {
        const QString message = QStringLiteral("PlaySDK failed to bind preview surface (%1)").arg(formatPlaySdkError(playPort));
        LoggerManager::instance().logError(message);
        stopPlaySdkStream(playPort);
        emit liveStateChanged(false, message);
        return false;
    }

    session.callbackMode = true;
    session.playPort = playPort;

    session.handle = static_cast<qint64>(CLIENT_RealPlayEx(static_cast<LLONG>(m_loginHandle),
                                                           channel,
                                                           nullptr));
    if (session.handle == 0) {
        LoggerManager::instance().logWarning(
            QStringLiteral("Callback preview with default realplay type failed on channel %1, retrying with main-stream type")
                .arg(channel));

        session.handle = static_cast<qint64>(CLIENT_RealPlayEx(static_cast<LLONG>(m_loginHandle),
                                                               channel,
                                                               nullptr,
                                                               DH_RType_Realplay_0));
    }

    if (session.handle == 0) {
        stopPlaySdkStream(playPort);
        m_lastError = formatLastError();
        const QString message = QStringLiteral("Start live failed on channel %1 in callback preview mode after retry (%2)")
                                    .arg(channel)
                                    .arg(m_lastError);
        LoggerManager::instance().logError(message);
        emit liveStateChanged(false, message);
        return false;
    }

    if (!CLIENT_SetRealDataCallBackEx2(static_cast<LLONG>(session.handle), &handleRealData, 0, REALDATA_FLAG_RAW_DATA)) {
        m_lastError = formatLastError();
        const QString message = QStringLiteral("Live stream opened but callback registration failed (%1)").arg(m_lastError);
        LoggerManager::instance().logError(message);
        CLIENT_StopRealPlayEx(static_cast<LLONG>(session.handle));
        session.handle = 0;
        stopPlaySdkStream(playPort);
        emit liveStateChanged(false, message);
        return false;
    }

    m_liveSessions.append(session);
    const QString message = QStringLiteral("Live preview started on channel %1").arg(channel);
    LoggerManager::instance().logInfo(message);
    emit liveStateChanged(true, message);
    return true;
}

void DahuaSdkManager::stopLive()
{
    for (int index = m_liveSessions.size() - 1; index >= 0; --index) {
        stopLiveSession(index);
    }
    m_liveSessions.clear();
    LoggerManager::instance().logInfo(QStringLiteral("Live preview stopped"));
    emit liveStateChanged(false, QStringLiteral("Live preview stopped"));
}

void DahuaSdkManager::stopLive(quintptr renderHandle)
{
    if (renderHandle == 0) {
        return;
    }

    bool stoppedAnySession = false;
    for (int index = m_liveSessions.size() - 1; index >= 0; --index) {
        if (m_liveSessions.at(index).renderHandle != renderHandle) {
            continue;
        }

        stopLiveSession(index);
        stoppedAnySession = true;
    }

    if (!stoppedAnySession) {
        return;
    }

    const bool previewStillActive = !m_liveSessions.isEmpty();
    const QString message = previewStillActive
        ? QStringLiteral("Stopped live preview on one tile")
        : QStringLiteral("Live preview stopped");
    LoggerManager::instance().logInfo(message);
    emit liveStateChanged(previewStillActive, message);
}

void DahuaSdkManager::setPreviewFillMode(bool enabled)
{
    m_previewFillMode = enabled;
}

void DahuaSdkManager::stopLiveSession(int index)
{
    if (index < 0 || index >= m_liveSessions.size()) {
        return;
    }

    const LivePreviewSession session = m_liveSessions.at(index);
    if (session.handle != 0) {
        CLIENT_StopRealPlayEx(static_cast<LLONG>(session.handle));
    }
    if (session.callbackMode) {
        stopPlaySdkStream(session.playPort);
    }

    m_liveSessions.removeAt(index);
}

bool DahuaSdkManager::downloadByTime(const DownloadTask &task)
{
    if (m_loginHandle == 0 || !task.isValid()) {
        const QString message = QStringLiteral("Download requires an active login and a valid task");
        LoggerManager::instance().logWarning(message);
        emit downloadStateChanged(false, message);
        return false;
    }

    stopDownload();

    QByteArray filePath = task.filePath.toLocal8Bit();
    NET_TIME startTime = toNetTime(task.startTime);
    NET_TIME endTime = toNetTime(task.endTime);

    m_downloadHandle = static_cast<qint64>(CLIENT_DownloadByTimeEx(static_cast<LLONG>(m_loginHandle),
                                                                   task.channel,
                                                                   0,
                                                                   &startTime,
                                                                   &endTime,
                                                                   filePath.data(),
                                                                   &handleDownloadProgress,
                                                                   0,
                                                                   nullptr,
                                                                   0,
                                                                   nullptr));
    if (m_downloadHandle == 0) {
        m_lastError = formatLastError();
        const QString message = QStringLiteral("Download start failed (%1)").arg(m_lastError);
        LoggerManager::instance().logError(message);
        emit downloadStateChanged(false, message);
        return false;
    }

    const QString message = QStringLiteral("Download started: %1").arg(task.filePath);
    LoggerManager::instance().logInfo(message);
    emit downloadProgressChanged(0);
    emit downloadStateChanged(true, message);
    return true;
}

void DahuaSdkManager::stopDownload()
{
    if (m_downloadHandle == 0) {
        return;
    }

    CLIENT_StopDownload(static_cast<LLONG>(m_downloadHandle));
    m_downloadHandle = 0;
    LoggerManager::instance().logInfo(QStringLiteral("Download stopped"));
    emit downloadStateChanged(false, QStringLiteral("Download stopped"));
}

bool DahuaSdkManager::isInitialized() const
{
    return m_initialized;
}

bool DahuaSdkManager::isLoggedIn() const
{
    return m_loginHandle != 0;
}

bool DahuaSdkManager::isPreviewing() const
{
    return !m_liveSessions.isEmpty();
}

bool DahuaSdkManager::isDownloading() const
{
    return m_downloadHandle != 0;
}

int DahuaSdkManager::channelCount() const
{
    return m_channelCount;
}

QVector<PreviewChannelInfo> DahuaSdkManager::previewChannels() const
{
    return m_previewChannels;
}

QString DahuaSdkManager::lastError() const
{
    return m_lastError;
}

int DahuaSdkManager::findLiveSessionIndex(qint64 liveHandle) const
{
    for (int index = 0; index < m_liveSessions.size(); ++index) {
        if (m_liveSessions.at(index).handle == liveHandle) {
            return index;
        }
    }

    return -1;
}

void DahuaSdkManager::feedPlaySdkData(qint64 liveHandle, unsigned char *buffer, unsigned long bufferSize)
{
    const int sessionIndex = findLiveSessionIndex(liveHandle);
    if (sessionIndex < 0) {
        return;
    }

    const LivePreviewSession &session = m_liveSessions.at(sessionIndex);
    if (!session.callbackMode || session.playPort < 0 || g_playSdkState.inputData == nullptr) {
        return;
    }

    g_playSdkState.inputData(session.playPort, buffer, bufferSize);
}

void DahuaSdkManager::emitConnectionEvent(bool connected, const QString &message)
{
    emit sdkLogMessage(message);
    emit connectionStateChanged(connected, message);
}

QString DahuaSdkManager::formatLastError() const
{
    const unsigned long errorCode = CLIENT_GetLastError();
    return QStringLiteral("%1 (0x%2)")
        .arg(describeErrorCode(errorCode),
             QString::number(errorCode, 16).toUpper());
}

bool DahuaSdkManager::ensurePreviewLogin()
{
    if (m_previewLoginHandle != 0) {
        return true;
    }

    if (!m_lastConnectionInfo.isValid()) {
        LoggerManager::instance().logWarning(QStringLiteral("Legacy preview login skipped because connection info is incomplete"));
        return false;
    }

    NET_DEVICEINFO_Ex deviceInfo = {};
    int errorCode = 0;

    const QByteArray hostBytes = m_lastConnectionInfo.host.toLocal8Bit();
    const QByteArray usernameBytes = m_lastConnectionInfo.username.toLocal8Bit();
    const QByteArray passwordBytes = m_lastConnectionInfo.password.toLocal8Bit();

    m_previewLoginHandle = static_cast<qint64>(CLIENT_LoginEx2(hostBytes.constData(),
                                                               static_cast<WORD>(m_lastConnectionInfo.port),
                                                               usernameBytes.constData(),
                                                               passwordBytes.constData(),
                                                               EM_LOGIN_SPEC_CAP_TCP,
                                                               nullptr,
                                                               &deviceInfo,
                                                               &errorCode));
    if (m_previewLoginHandle == 0) {
        LoggerManager::instance().logWarning(
            QStringLiteral("Legacy preview login failed for %1:%2 (sdkError=%3, apiError=%4)")
                .arg(m_lastConnectionInfo.host)
                .arg(m_lastConnectionInfo.port)
                .arg(errorCode)
                .arg(formatLastError()));
        return false;
    }

    LoggerManager::instance().logInfo(
        QStringLiteral("Legacy preview login established for %1:%2 (%3 channels)")
            .arg(m_lastConnectionInfo.host)
            .arg(m_lastConnectionInfo.port)
            .arg(deviceInfo.nChanNum));
    return true;
}

void DahuaSdkManager::releasePreviewLogin()
{
    if (m_previewLoginHandle == 0) {
        return;
    }

    CLIENT_Logout(static_cast<LLONG>(m_previewLoginHandle));
    m_previewLoginHandle = 0;
    LoggerManager::instance().logInfo(QStringLiteral("Legacy preview login released"));
}
