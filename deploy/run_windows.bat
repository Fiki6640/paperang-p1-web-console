@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo ======================================
echo   Paperang P1 Web 打印服务
echo ======================================
echo.
echo 正在启动服务...
echo 访问地址: http://localhost:5000
echo 按 Ctrl+C 停止服务
echo.
python app.py
pause
