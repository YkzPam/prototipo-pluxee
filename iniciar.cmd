@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call preparar.cmd
if errorlevel 1 goto error
".venv\Scripts\python.exe" -c "import MySQLdb, cryptography, cheroot" >nul 2>nul
if errorlevel 1 call preparar.cmd
if errorlevel 1 goto error
echo.
echo Abrir https://127.0.0.1:8443 en Chrome despues de configurar el certificado local.
echo Beneficiario: beneficiario / Clave inicial: Prototipo2026!
echo Administrador: administrador / Clave inicial: AdminPluxee2026!
echo Si se personalizo una clave, usar la vigente.
echo Mantener esta ventana abierta mientras se utiliza el prototipo.
echo.
".venv\Scripts\python.exe" scripts\arranque_seguro.py
if errorlevel 1 goto error
exit /b 0
:error
echo No se pudo preparar el prototipo. Revisar el mensaje anterior.
pause
exit /b 1
