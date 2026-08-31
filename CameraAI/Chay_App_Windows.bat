@echo off
title Dahua WizMind AI NVR5832-EI2 - Application Launcher
color 0A
cls

echo ==============================================================================
echo           DAHUA DHI-NVR5832-EI2 AI METADATA & 10S VIDEO SUMMARIZER
echo ==============================================================================
echo.
echo [1/2] Dang khoi dong Web Server & Dahua NVR Listener (Port 8000)...
start /b python main.py > nul 2>&1

echo [2/2] Dang mo Ung dung Desktop va Trinh duyet...
timeout /t 3 /nobreak > nul

start http://localhost:8000

python app_win.py

pause
