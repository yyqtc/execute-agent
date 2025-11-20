@echo off

set PYTHONIOENCODING=utf-8

python "%~dp0main.py" %*

if errorlevel 1 (
    echo.
    echo 错误：Python 脚本执行失败，错误代码：%errorlevel%
    pause
    exit /b %errorlevel%
)