@echo off
rem GlyphCue -- DevQA/engineering-only fail-closed DirectML launcher.
rem
rem Runs a real DirectML preflight (constructs DirectMlOcrEngine and
rem DirectMlTextDetector, verifies DmlExecutionProvider is active on both
rem underlying ONNX Runtime sessions) BEFORE starting the app. If the
rem preflight fails for any reason, this script prints why and stops --
rem it never silently launches into the Paddle CPU fallback. This is a
rem diagnostic entrypoint only: passing the preflight does not change
rem product behavior in any way. It then starts the exact same product
rem UI as Launch-GlyphCue.bat / Launch-GlyphCue-DevQA.bat -- same
rem glyphcue.ui.app module, same single PRODUCTION_TRIGGER pipeline, same
rem Architecture B. There is no second pipeline and no in-app backend
rem selector; this launcher only decides whether the environment it runs
rem in is proven capable of the already-existing DirectML runtime path
rem before handing off to that one unchanged product.
rem
rem Uses a DEDICATED venv (.venv-directml-devqa) with the [ocr,directml]
rem extras installed, kept separate from the trusted .venv used by the
rem normal launchers -- this script never installs into or modifies that
rem trusted development environment.
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON=%PROJECT_DIR%.venv-directml-devqa\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo [GlyphCue DevQA] Could not find "%PYTHON%".
    echo Create it first:
    echo   py -3.12 -m venv .venv-directml-devqa
    echo   .venv-directml-devqa\Scripts\python.exe -m pip install -e ".[ocr,directml]"
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"
set "PYTHONPATH=%PROJECT_DIR%src"

echo [GlyphCue DevQA] Running fail-closed DirectML preflight...
"%PYTHON%" tools\devqa_directml_verify.py
if errorlevel 1 (
    echo.
    echo [GlyphCue DevQA] DirectML preflight FAILED -- refusing to launch.
    echo This entrypoint does not fall back to Paddle CPU. See the error above.
    pause
    exit /b 1
)

echo.
echo [GlyphCue DevQA] DirectML preflight PASSED. Launching product UI ^(same PRODUCTION_TRIGGER pipeline^)...
echo.
"%PYTHON%" -m glyphcue

endlocal
