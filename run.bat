@echo off
setlocal
title Naver Cafe Bot - Running...

echo Starting Naver Cafe Bot...
call venv\Scripts\activate.bat
streamlit run app.py
pause
