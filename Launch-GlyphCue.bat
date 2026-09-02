@echo off
rem GlyphCue -- normal launcher.
rem
rem Opens the current GlyphCue product UI (the persistent Evidence
rem Workbench shell) with the shipped defaults. Path A OCR runs the
rem PRODUCTION_TRIGGER profile and no developer controls are shown.
rem
rem Everything is relative to this file, so the checkout can live
rem anywhere and the launcher still works.
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHONW=%PROJECT_DIR%.venv\Scripts\pythonw.exe"

if not exist "%PYTHONW%" (
    echo [GlyphCue] Could not find "%PYTHONW%".
    echo Create the virtual environment at .venv first, then run this again.
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"
set "PYTHONPATH=%PROJECT_DIR%src"
start "" "%PYTHONW%" -m glyphcue

endlocal
