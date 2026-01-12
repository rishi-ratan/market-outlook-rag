@echo off
REM Start backend server
cd /d "%~dp0"
uvicorn apps.api.main:app --reload --port 8000
pause
