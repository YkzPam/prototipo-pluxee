@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencias
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m venv .venv
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Se necesita Python 3.12 o superior instalado desde python.org.
        pause
        exit /b 1
    )
    python -m venv .venv
)
if errorlevel 1 exit /b 1
:dependencias
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo Preparacion terminada. Ejecutar iniciar.cmd.
