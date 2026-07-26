@echo off
:: SPECTRE_GRID — Auto Startup Script
:: Coloque este arquivo em: Shell:startup (Win+R -> shell:startup)
:: Ele inicia todos os serviços do SPECTRE_GRID ao ligar o PC

title SPECTRE_GRID Startup

echo [SPECTRE_GRID] Iniciando servicos...
timeout /t 10 /nobreak >nul

:: Configurar encoding UTF-8 para evitar problemas com caracteres acentuados nos caminhos
chcp 65001 > nul

:: Obter caminhos dinâmicos do Windows para o WSL
set LOCAL_PATH=%~dp0
set LOCAL_PATH_WSL=%LOCAL_PATH:\=/%
for /f "delims=" %%i in ('wsl wslpath -u "%LOCAL_PATH_WSL%"') do set WSL_DIR=%%i
if "%WSL_DIR:~-1%"=="/" set WSL_DIR=%WSL_DIR:~0,-1%

:: 1. Spectre Fusion (C++ Motor + eBPF/XDP)
:: REGRA DE LATÊNCIA: O Motor DEVE rodar na pasta nativa do Linux (~/ids-cnn-lstm-gnn)
echo [1/2] Iniciando Spectre Fusion no ambiente nativo do Linux...
start "SPECTRE Fusion" wsl -u root bash -c "cd ~/ids-cnn-lstm-gnn && ACTIVE_IFACE=\$(ip route ls default | awk '{print \$5}' | head -n 1) && if [ -z \"\$ACTIVE_IFACE\" ]; then ACTIVE_IFACE=\$(ip -o link show | awk -F': ' '\$2 != \"lo\" {print \$2; exit}'); fi && if [ -z \"\$ACTIVE_IFACE\" ]; then ACTIVE_IFACE=\"eth0\"; fi && ./build/spectre_fusion \$ACTIVE_IFACE >> /tmp/fusion.log 2>&1"
timeout /t 5 /nobreak >nul

:: 2. Dashboard API (FastAPI + SQLite + Frontend Compilado)
:: MARTELADO: A API DEVE rodar na pasta montada do Windows para carregar a Interface Nova
echo [2/2] Iniciando Dashboard API (Servindo a Interface Nova)...
start "SPECTRE API" wsl -u root bash -c "cd %WSL_DIR% && python3 dashboard_api_v2.py >> /tmp/api.log 2>&1"

echo [SPECTRE_GRID] Todos os servicos iniciados!
echo Dashboard Oficial: http://localhost:8001
timeout /t 5 /nobreak >nul
