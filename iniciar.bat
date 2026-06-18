@echo off
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\python -m pip install -r requirements.txt
start "Servidor de Reservas" cmd /k ".venv\Scripts\python app.py"
timeout /t 3 /nobreak >nul
start http://127.0.0.1:5001/reserva
