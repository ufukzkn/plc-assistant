@echo off
setlocal
pushd "%~dp0" || (
    echo PLC Assistant klasoru acilamadi.
    pause
    exit /b 1
)

set "PYTHON_EXE=.venv\Scripts\python.exe"
set "PYTHON_ARGS="
if exist "%PYTHON_EXE%" goto run

set "PYTHON_EXE=py.exe"
set "PYTHON_ARGS=-3"
py.exe -3 --version >nul 2>&1
if not errorlevel 1 goto run

set "PYTHON_EXE=python.exe"
set "PYTHON_ARGS="
python.exe --version >nul 2>&1
if not errorlevel 1 goto run

echo Python bulunamadi. Python 3.10 veya uzeri ve Tcl/Tk kurun.
popd
pause
exit /b 1

:run
"%PYTHON_EXE%" %PYTHON_ARGS% "main.py"
set "APP_EXIT=%ERRORLEVEL%"
popd
pause
exit /b %APP_EXIT%
