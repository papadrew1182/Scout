@echo off
echo Starting Scout backend server...
cd /d "%~dp0backend"
"C:\Users\rober\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
