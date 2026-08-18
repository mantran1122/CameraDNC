@echo off
rem Chay EventProbe voi duong dan DLL cua SDK
set PATH=D:\dnc\netSDK2\Bin;%PATH%
set /p PASS=Nhap mat khau dau ghi (admin@192.168.3.26):
D:\dnc\netSDK2\EventProbe\EventProbe.exe 192.168.3.26 37777 admin %PASS% 8
pause
