@echo off
setlocal EnableExtensions
set "APP_EXIT_CODE=1"
title Frivault - Development Launcher
color 0B
cls

echo ================================================================================
echo   FRIVAULT  ^|  DEVELOPMENT LAUNCHER
echo   Local desktop test run - no installer required
echo ================================================================================
echo.

cd /d "%~dp0"
if errorlevel 1 goto project_error

set "PYTHON=%~dp0.venv315\Scripts\python.exe"
if not exist "%PYTHON%" goto python_missing
if not exist "%~dp0src\frivault\__main__.py" goto source_missing

echo [1/3] Project files found.
echo [2/3] Python environment:
"%PYTHON%" --version
if errorlevel 1 goto python_error
echo.

echo [3/3] Launching Frivault...
echo The desktop window should appear shortly.
echo This status window will stay open while Frivault is running.
echo.
echo STATUS: Launch command active. Waiting for the Frivault window to close...
echo -------------------------------------------------------------------------------
"%PYTHON%" -u -m frivault
set "APP_EXIT_CODE=%ERRORLEVEL%"
echo -------------------------------------------------------------------------------

if "%APP_EXIT_CODE%"=="0" goto normal_exit
goto app_error

:normal_exit
echo STATUS: Frivault closed normally.
echo You can close this window now.
goto finish

:app_error
color 0C
echo STATUS: Frivault stopped with an error. Exit code: %APP_EXIT_CODE%
echo Check the app log at:
echo %LOCALAPPDATA%\Frivault\Logs\frivault.log
echo If the log is missing, check that WebView2 Runtime is installed.
goto finish

:project_error
color 0C
echo ERROR: Could not open the Frivault project folder.
goto finish

:python_missing
color 0C
echo ERROR: The Python 3.15 project environment was not found:
echo %PYTHON%
echo Restore or prepare the .venv315 environment, then run this file again.
goto finish

:source_missing
color 0C
echo ERROR: Frivault source files were not found under src\frivault.
goto finish

:python_error
color 0C
echo ERROR: The configured Python environment could not start.
goto finish

:finish
echo.
echo Press any key to close this window.
pause >nul
exit /b %APP_EXIT_CODE%
