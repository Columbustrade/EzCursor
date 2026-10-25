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

rem ---------- Phat hanh len GitHub (tuy chon)
set "REPO=Columbustrade/EzCursor"
set "VER="
for /f "tokens=3" %%v in ('findstr /c:"#define MyAppVersion" EzCursor.iss') do set "VER=%%~v"
set "SETUP=installer\EzCursor_Setup_%VER%.exe"
echo.
echo Luu y: hay Commit va Push ma nguon bang GitHub Desktop TRUOC khi phat hanh.
choice /c YN /m "Phat hanh phien ban %VER% len GitHub ngay bay gio"
if errorlevel 2 goto ketthuc
call :phathanh

:ketthuc
start "" "%~dp0installer"
pause
exit /b 0

:phathanh
where gh >nul 2>nul
if errorlevel 1 (
    echo.
    echo *** Chua cai GitHub CLI. Hay cai tai https://cli.github.com roi chay lai file nay. ***
    start "" "https://cli.github.com"
    exit /b 0
)
gh auth status >nul 2>nul
if errorlevel 1 (
    echo Dang nhap GitHub lan dau, hay lam theo huong dan ben duoi...
    gh auth login
)
gh auth status >nul 2>nul
if errorlevel 1 (
    echo *** Chua dang nhap duoc GitHub, bo qua buoc phat hanh. ***
    exit /b 0
)
if not exist "%SETUP%" (
    echo *** Khong tim thay %SETUP% ***
    exit /b 0
)
gh release view v%VER% --repo %REPO% >nul 2>nul
if not errorlevel 1 (
    echo.
    echo *** Ban phat hanh v%VER% da co tren GitHub. ***
    echo Hay tang so phien ban trong ezcursor.py va EzCursor.iss, build lai roi phat hanh.
    exit /b 0
)
if exist release_notes.txt goto conotes
(
    echo Co gi moi trong phien ban %VER%:
    echo - 
) > release_notes.txt
:conotes
echo.
echo Dang mo Notepad de ban viet noi dung "Co gi moi".
echo Sua xong hay LUU (Ctrl+S) va DONG Notepad de tiep tuc...
start /wait notepad release_notes.txt
echo.
echo Dang tao ban phat hanh v%VER% va tai bo cai len GitHub...
gh release create v%VER% "%SETUP%" --repo %REPO% --title "EzCursor %VER%" --notes-file release_notes.txt
if errorlevel 1 (
    echo *** Phat hanh that bai. Hay chup man hinh cua so nay de duoc ho tro. ***
    exit /b 0
)
echo.
echo === DA PHAT HANH v%VER% LEN GITHUB ===
start "" "https://github.com/%REPO%/releases/tag/v%VER%"
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
