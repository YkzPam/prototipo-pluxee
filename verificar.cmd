@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" manage.py check --settings=config.settings.testing
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m coverage run manage.py test --settings=config.settings.testing
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m coverage report --fail-under=80
pause
