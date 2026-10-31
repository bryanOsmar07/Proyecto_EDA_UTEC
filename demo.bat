@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Cree el entorno con python -m venv .venv e instale requirements-dev.txt.
  exit /b 1
)
".venv\Scripts\python.exe" -m src.cli serve --events 5000 --port 8766 --output results/complete_demo
