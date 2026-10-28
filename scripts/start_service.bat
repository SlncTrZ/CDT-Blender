@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo   CDT-Blender: On-Demand Service Launcher (PC 171)
echo ============================================================

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
cd /d "%REPO_ROOT%"

:: Locate Python
set "PYTHON_EXE="
if exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"
) else if exist "%REPO_ROOT%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%REPO_ROOT%\venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    ) else (
        echo [ERROR] Python not found. Please create a virtualenv in .venv or install Python 3.11+.
        exit /b 1
    )
)

:: Configuration
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8812"

set "TRANSPORT=%~2"
if "%TRANSPORT%"=="" set "TRANSPORT=http"

if "%BLENDER_MCP_TOKEN%"=="" (
    set "BLENDER_MCP_TOKEN=cdt-blender-session-token"
)

echo [INFO] Python:     %PYTHON_EXE%
echo [INFO] Transport:  %TRANSPORT%
echo [INFO] Port:       %PORT%
echo [INFO] Note:       Ensure Blender 4.x is running with blender_mcp_addon enabled (port 8888).
echo ------------------------------------------------------------
echo Starting CDT-Blender bridge service...

if "%TRANSPORT%"=="stdio" (
    "%PYTHON_EXE%" -m blender_mcp_bridge.main serve --transport stdio
) else (
    "%PYTHON_EXE%" -m blender_mcp_bridge.main serve --transport http --host 127.0.0.1 --port %PORT%
)

exit /b %errorlevel%
