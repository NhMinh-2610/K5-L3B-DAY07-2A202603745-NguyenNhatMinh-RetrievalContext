@echo off
cd /d "%~dp0"
set "LAB_PYTHON=%USERPROFILE%\.venvs\day06-dataingestion\Scripts\python.exe"
"%LAB_PYTHON%" -B -X utf8 scripts\serve_web.py --day6 "..\K5-L3B-DAY06-NguyenNhatMinh-2A202603745-DataIngestion"
pause
