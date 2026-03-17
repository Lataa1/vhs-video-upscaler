@echo off
setlocal
cd /d "%~dp0"

set "APP_PY=%~dp0vhs_upscaler_gui.py"
set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
set "PY313=%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"

if exist "%PY312%" (
    start "" "%PY312%" "%APP_PY%"
    goto :eof
)

if exist "%PY313%" (
    start "" "%PY313%" "%APP_PY%"
    goto :eof
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "" py -3.12 "%APP_PY%"
    goto :eof
)

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%APP_PY%"
    goto :eof
)

where python >nul 2>nul
if %errorlevel%==0 (
    start "" python "%APP_PY%"
    goto :eof
)

echo Python was not found.
echo Install Python 3 or use the portable tools in this project folder.
pause
