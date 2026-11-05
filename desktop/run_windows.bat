@echo off
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv || (echo Python 3.10+ is required. & pause & exit /b 1)
)
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\python -m pip install -q -r requirements.txt
.venv\Scripts\python main.py
pause
