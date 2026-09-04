@echo off
rem GlyphCue -- developer / manual-QA launcher.
rem
rem Opens exactly the SAME current GlyphCue product UI as
rem Launch-GlyphCue.bat -- same module, same shell, same everything,
rem same single production evidence pipeline. The M11 Legacy Pipeline
rem Retirement Corrective Gate (2026-09-04) removed the developer OCR
rem Profile selector and its retired alternate profile entirely -- no
rem launch of this app can reach anything but production anymore.
rem
rem Runs on the console python (not pythonw) so QA can see progress and
rem any error instead of a window that silently fails to appear. Closing
rem this console window closes the app.
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [GlyphCue] Could not find "%PYTHON%".
    echo Create the virtual environment at .venv first, then run this again.
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"
set "PYTHONPATH=%PROJECT_DIR%src"

echo [GlyphCue] Developer/manual-QA mode: console output enabled.
echo.
"%PYTHON%" -m glyphcue

endlocal
