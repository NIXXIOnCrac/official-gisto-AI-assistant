@echo off
REM ============================================================
REM Build Gisto EXE — inject real keys, then run PyInstaller.
REM Run this from the repo root. The real keys come from the
REM caller's environment (they must be set before calling this).
REM ============================================================

setlocal

echo ============================================================
echo  Gisto EXE build — injecting keys + PyInstaller
echo ============================================================

if "%NOUS_API_KEY%"=="" (
    echo [ERROR] NOUS_API_KEY is not set.
    exit /b 1
)
if "%ELEVENLABS_API_KEY%"=="" (
    echo [ERROR] ELEVENLABS_API_KEY is not set.
    exit /b 1
)
if "%GOOGLE_PLACES_API_KEY%"=="" (
    echo [ERROR] GOOGLE_PLACES_API_KEY is not set.
    exit /b 1
)
if "%COMPOSIO_API_KEY%"=="" (
    echo [ERROR] COMPOSIO_API_KEY is not set.
    exit /b 1
)

echo.
echo Keys present in environment:
echo   NOUS_API_KEY      = %NOUS_API_KEY:~0,10%...
echo   ELEVENLABS_API_KEY = %ELEVENLABS_API_KEY:~0,10%...
echo   GOOGLE_PLACES_API_KEY = %GOOGLE_PLACES_API_KEY:~0,10%...
echo   COMPOSIO_API_KEY  = %COMPOSIO_API_KEY:~0,10%...
echo.

echo.
echo [1/2] Injecting XOR-obfuscated keys into src/desktop/_built_keys.py...
python scripts/build_keys.py
if errorlevel 1 (
    echo [ERROR] build_keys.py failed.
    exit /b 1
)

echo.
echo [2/2] Building PyInstaller EXE (this takes a few minutes)...
echo        Output: dist/Gisto.exe
echo.

pyinstaller --onefile ^
    --name "Gisto" ^
    --distpath dist ^
    --workpath build ^
    --specpath . ^
    --hidden-import pynput.keyboard._win32 ^
    --hidden-import pystray._win32 ^
    --hidden-import src.desktop._built_keys ^
    --hidden-import src.desktop.keys ^
    --hidden-import src.desktop.audio_watcher ^
    --hidden-import src.desktop.composio_tools ^
    --add-data "assets:gisto_assets" ^
    -w src/desktop/main.py

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

echo.
echo ============================================================
echo  Build complete: dist/Gisto.exe
echo ============================================================
echo.

REM Verify the EXE exists and show its size.
if exist dist\Gisto.exe (
    for %%A in (dist\Gisto.exe) do (
        echo Size: %%~zA bytes
    )
    echo.
    echo Ready to distribute.
) else (
    echo [ERROR] dist\Gisto.exe not found after build.
    exit /b 1
)

endlocal
