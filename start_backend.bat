@echo off
chcp 65001 >nul
echo ========================================================
echo   KeyVault-AI Backend Baslatucu (Chrome + Honor Tablet)
echo ========================================================

if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    echo [1/2] Honor Tablet USB Port Yonlendirmesi (adb reverse tcp:8000) aktif ediliyor...
    "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000 2>nul
)

echo [2/2] FastAPI Sunucusu baslatiliyor (0.0.0.0:8000)...
cd /d "%~dp0backend"
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
