@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call preparar.cmd
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto error
".venv\Scripts\python.exe" manage.py preparar_demo
if errorlevel 1 goto error
echo.
echo Abrir http://127.0.0.1:8765 en Chrome.
echo Usuario: beneficiario / Clave de prueba: Prototipo2026!
echo Mantener esta ventana abierta mientras se utiliza el prototipo.
echo.
".venv\Scripts\python.exe" servidor.py
exit /b
:error
echo No se pudo preparar el prototipo. Revisar el mensaje anterior.
pause
exit /b 1
