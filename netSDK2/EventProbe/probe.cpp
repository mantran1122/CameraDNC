// EventProbe - cong cu chan doan su kien IVS tu thiet bi Dahua.
// Dang nhap thiet bi, attach EVENT_IVS_ALL tren nhieu kenh va in ra
// moi su kien nhan duoc (ma su kien + kenh + thoi gian).
//
// Cach dung: EventProbe.exe <ip> <port> <user> <password> [soKenh=8]

#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>

#include "dhnetsdk.h"

static const char* EventName(DWORD type)
{
    switch (type) {
    case EVENT_IVS_CROSSLINEDETECTION:   return "Tripwire (CrossLine)";
    case EVENT_IVS_CROSSREGIONDETECTION: return "Intrusion (CrossRegion)";
    default:                             return "(loai khac - xem ma hex)";
    }
}

static void PrintNow()
{
    time_t t = time(nullptr);
    struct tm tmv;
    localtime_s(&tmv, &t);
    printf("%02d:%02d:%02d", tmv.tm_hour, tmv.tm_min, tmv.tm_sec);
}

// Moi handle attach ung voi 1 kenh - luu de tra nguoc kenh trong callback
static LLONG g_handles[64] = {0};
static int   g_handleChannel[64] = {0};
static int   g_handleCount = 0;

static int CALLBACK AnalyzerDataCB(LLONG lAnalyzerHandle, DWORD dwAlarmType,
                                   void* /*pAlarmInfo*/, BYTE* /*pBuffer*/,
                                   DWORD /*dwBufSize*/, LDWORD /*dwUser*/,
                                   int /*nSequence*/, void* /*reserved*/)
{
    int channel = -1;
    for (int i = 0; i < g_handleCount; ++i) {
        if (g_handles[i] == lAnalyzerHandle) { channel = g_handleChannel[i]; break; }
    }

    PrintNow();
    printf("  [SU KIEN] kenh SDK=%d (web D%d)  ma=0x%08X  %s\n",
           channel, channel + 1, dwAlarmType, EventName(dwAlarmType));
    fflush(stdout);
    return 0;
}

static void CALLBACK DisconnectCB(LLONG, char* ip, LONG port, LDWORD)
{
    printf("!! Mat ket noi toi %s:%ld\n", ip ? ip : "?", port);
    fflush(stdout);
}

int main(int argc, char* argv[])
{
    if (argc < 5) {
        printf("Cach dung: EventProbe.exe <ip> <port> <user> <password> [soKenh=8]\n");
        return 1;
    }
    const char* ip = argv[1];
    int port = atoi(argv[2]);
    const char* user = argv[3];
    const char* pass = argv[4];
    int numChannels = (argc >= 6) ? atoi(argv[5]) : 8;
    if (numChannels > 64) numChannels = 64;

    if (!CLIENT_Init(DisconnectCB, 0)) {
        printf("CLIENT_Init that bai\n");
        return 1;
    }

    NET_IN_LOGIN_WITH_HIGHLEVEL_SECURITY inLogin;
    NET_OUT_LOGIN_WITH_HIGHLEVEL_SECURITY outLogin;
    memset(&inLogin, 0, sizeof(inLogin));
    memset(&outLogin, 0, sizeof(outLogin));
    inLogin.dwSize = sizeof(inLogin);
    outLogin.dwSize = sizeof(outLogin);
    strncpy_s(inLogin.szIP, ip, _TRUNCATE);
    inLogin.nPort = port;
    strncpy_s(inLogin.szUserName, user, _TRUNCATE);
    strncpy_s(inLogin.szPassword, pass, _TRUNCATE);

    LLONG loginID = CLIENT_LoginWithHighLevelSecurity(&inLogin, &outLogin);
    if (loginID == 0) {
        printf("Dang nhap THAT BAI, ma loi: %d\n", (int)(CLIENT_GetLastError() & 0x7fffffff));
        CLIENT_Cleanup();
        return 1;
    }
    printf("Dang nhap OK: %s:%d  (thiet bi bao co %d kenh)\n",
           ip, port, outLogin.stuDeviceInfo.nChanNum);

    int attachTotal = numChannels;
    if (outLogin.stuDeviceInfo.nChanNum > 0 && outLogin.stuDeviceInfo.nChanNum < attachTotal)
        attachTotal = outLogin.stuDeviceInfo.nChanNum;

    for (int ch = 0; ch < attachTotal; ++ch) {
        LLONG h = CLIENT_RealLoadPictureEx(loginID, ch, EVENT_IVS_ALL, TRUE,
                                           AnalyzerDataCB, 0, NULL);
        if (h != 0) {
            g_handles[g_handleCount] = h;
            g_handleChannel[g_handleCount] = ch;
            ++g_handleCount;
            printf("  Attach kenh SDK=%d (web D%d): OK\n", ch, ch + 1);
        } else {
            printf("  Attach kenh SDK=%d (web D%d): loi %d\n",
                   ch, ch + 1, (int)(CLIENT_GetLastError() & 0x7fffffff));
        }
    }

    printf("\nDang lang nghe su kien... Di qua truoc camera de test.\n");
    printf("Nhan phim Enter de thoat.\n\n");
    fflush(stdout);

    getchar();

    for (int i = 0; i < g_handleCount; ++i)
        CLIENT_StopLoadPic(g_handles[i]);
    CLIENT_Logout(loginID);
    CLIENT_Cleanup();
    return 0;
}
