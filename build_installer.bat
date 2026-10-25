@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === [1/3] Cai thu vien can thiet ===
set "PY="
py -3.13 --version >nul 2>nul && set "PY=py -3.13"
if not defined PY (py -3.12 --version >nul 2>nul && set "PY=py -3.12")
if not defined PY (python --version >nul 2>nul && set "PY=python")
if not defined PY (py --version >nul 2>nul && set "PY=py")
if not defined PY (
    echo *** Khong tim thay Python tren may. ***
    echo Hay cai Python 3.13 64-bit tai https://www.python.org/downloads/windows/
    echo Nho tich o "Add python.exe to PATH", cai xong dong cua so nay roi chay lai.
    start "" "https://www.python.org/downloads/windows/"
    pause
    exit /b 1
)
echo Dung Python:
%PY% --version
%PY% -m pip install --upgrade pillow pystray customtkinter pyinstaller
if errorlevel 1 goto loi

echo.
echo === [2/3] Dong goi EzCursor.exe ===
%PY% -m PyInstaller --noconfirm --onedir --noconsole --hidden-import pystray._win32 --collect-all customtkinter --add-data "fonts;fonts" --add-data "bibata;bibata" --add-data "assets;assets" --add-data "ezcursor.ico;." --add-data "logo.png;." --icon ezcursor.ico --name EzCursor ezcursor.py
if errorlevel 1 goto loi

echo.
echo === [3/3] Tao bo cai dat ===
call :timiscc
if not defined ISCC (
    echo Chua co Inno Setup, dang thu cai tu dong bang winget...
    winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
    call :timiscc
)
if not defined ISCC (
    echo.
    echo *** Khong tim thay Inno Setup. ***
    echo Hay tai va cai Inno Setup 6 tai: https://jrsoftware.org/isdl.php
    echo Cai xong thi chay lai file nay.
    start "" "https://jrsoftware.org/isdl.php"
    pause
    exit /b 1
)
"%ISCC%" EzCursor.iss
if errorlevel 1 goto loi

echo.
echo === XONG! Bo cai dat nam trong thu muc: %~dp0installer ===
start "" "%~dp0installer"
pause
exit /b 0

:timiscc
set ISCC=
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do (
    if exist %%P set ISCC=%%~P
)
exit /b 0

:loi
echo.
echo *** Co loi xay ra. Hay chup man hinh cua so nay de duoc ho tro. ***
pause
exit /b 1
