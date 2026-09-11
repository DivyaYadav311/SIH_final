@echo off
setlocal
cd /d %~dp0
if not exist venv\Scripts\python.exe (
  python -m venv venv
  call venv\Scripts\activate
  python -m pip install --upgrade pip
  pip install -r requirements.txt
) else (
  call venv\Scripts\activate
)
uvicorn src.main:app --reload --port 8000
