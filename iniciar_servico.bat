@echo off
cd /d %~dp0

if not exist .venv (
  python -m venv .venv
)

call .venv\Scripts\python -m pip install -r requirements.txt
call .venv\Scripts\python -m waitress --host=127.0.0.1 --port=5001 app:app
