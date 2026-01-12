@echo off
REM Start frontend server
cd /d "%~dp0\apps\web"
if not exist "node_modules" (
    echo Installing dependencies...
    npm install
)
npm run dev
pause
