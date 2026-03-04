@echo off
cd /d "%~dp0"
pip install -r requirements.txt -q
start python main.py
timeout /t 2 /nobreak >nul
start http://localhost:8000
