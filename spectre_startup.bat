@echo off
:: SPECTRE_GRID — Auto Startup Script
:: Coloque este arquivo em: Shell:startup (Win+R -> shell:startup)
:: Ele inicia todos os serviços do SPECTRE_GRID ao ligar o PC

title SPECTRE_GRID Startup

echo [SPECTRE_GRID] Iniciando servicos...
timeout /t 10 /nobreak >nul

:: 1. Receiver GNN (STGNN + Ensemble)
echo [1/3] Iniciando Receiver GNN...
start "SPECTRE Receiver" wsl -u root bash -c "cd /mnt/c/Users/abraa/Documents/ids-cnn-lstm-gnn && source .venv_wsl/bin/activate && python3 -u /mnt/c/Users/abraa/Documents/antigravity/adventurous-oppenheimer/receiver_gnn.py >> /tmp/receiver.log 2>&1"
timeout /t 5 /nobreak >nul

:: 2. Dashboard API (FastAPI + SQLite)
echo [2/3] Iniciando Dashboard API...
start "SPECTRE API" wsl -u root bash -c "cd /mnt/c/Users/abraa/Documents/ids-cnn-lstm-gnn && source .venv_wsl/bin/activate && python3 dashboard_api_v2.py >> /tmp/api.log 2>&1"
timeout /t 5 /nobreak >nul

:: 3. Frontend Vite (React Dashboard)
echo [3/3] Iniciando Frontend...
start "SPECTRE Dashboard" cmd /c "cd /d C:\Users\abraa\Documents\ids-cnn-lstm-gnn\dashboard_v2 && npm run dev"

echo [SPECTRE_GRID] Todos os servicos iniciados!
echo Dashboard: http://localhost:5173
echo API:       http://localhost:8001
timeout /t 5 /nobreak >nul
