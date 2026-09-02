@echo off
rem GlyphCue -- developer / manual-QA launcher.
rem
rem Opens exactly the SAME current GlyphCue product UI as
rem Launch-GlyphCue.bat -- same module, same shell, same everything --
rem and additionally reveals the developer/manual-QA "OCR Profile"
rem dropdown in Path A, so Experimental Hybrid can be selected by hand.
rem
rem This does NOT change the default. The dropdown still opens on
rem Production, and a run only uses Experimental Hybrid if you pick it.
rem Not a shipped feature: there is no in-app way to reveal this.
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
set "GLYPHCUE_DEV_OCR_PROFILE_SELECTOR=1"

echo [GlyphCue] Developer/manual-QA mode: OCR Profile selector enabled.
echo [GlyphCue] Default profile is still Production -- choose Experimental
echo [GlyphCue] Hybrid in the Path A "OCR Profile" dropdown to test it.
echo.
"%PYTHON%" -m glyphcue

endlocal
