@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencias
rem El acceso de Microsoft Store llamado "python" no es un Python instalado: se comprueba que funcione.
set "PYTHON_CMD="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD python -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul && set "PYTHON_CMD=python"
if not defined PYTHON_CMD goto sin_python
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto sin_python
:dependencias
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto sin_dependencias
echo Preparacion terminada. Ejecutar iniciar.cmd.
exit /b 0
:sin_python
echo Se necesita Python 3.12 o superior instalado desde https://www.python.org/downloads/
echo Durante la instalacion marcar "Add python.exe to PATH" y luego ejecutar de nuevo este archivo.
pause
exit /b 1
:sin_dependencias
echo No se pudieron instalar las dependencias. Revisar la conexion a internet y ejecutar de nuevo.
pause
exit /b 1
