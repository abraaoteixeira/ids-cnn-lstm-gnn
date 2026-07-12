@echo off
chcp 65001 > nul
title SPECTRE Coder - DeepSeek V4 (NVIDIA NIM)

:: Navega para a pasta do proprio bat (raiz do projeto)
cd /d "%~dp0"

echo ========================================================
echo   INICIANDO AGENTE DE TERMINAL CODER (Aider)
echo   Cerebro: DeepSeek V4 Flash (NVIDIA NIM) [TESTADO OK]
echo   Repositorio: ids-cnn-lstm-gnn
echo ========================================================

:: A chave NUNCA deve ficar hardcoded aqui.
:: Configure ela UMA VEZ no sistema com:
::   setx NVIDIA_NIM_KEY "nvapi-SUA_CHAVE_AQUI"
:: E reinicie o terminal. Ela ficara salva permanentemente no seu perfil.
if "%NVIDIA_NIM_KEY%"=="" (
    echo [ERRO] Variavel NVIDIA_NIM_KEY nao encontrada.
    echo Execute: setx NVIDIA_NIM_KEY "nvapi-SUA_CHAVE_AQUI"
    echo Depois feche e reabra este terminal.
    pause
    exit /b 1
)

set OPENAI_API_BASE=https://integrate.api.nvidia.com/v1
set OPENAI_API_KEY=%NVIDIA_NIM_KEY%

:: Garante que o aider (instalado via uv) esta no PATH
set PATH=%USERPROFILE%\.local\bin;%PATH%

:: Executa o Aider
:: --chat-history-file: salva historico em temp para evitar Permission Denied
:: --auto-commits: commita automaticamente cada alteracao aceita
:: --map-tokens: aumenta contexto do repositorio
aider --model openai/deepseek-ai/deepseek-v4-flash ^
      --auto-commits ^
      --map-tokens 4096 ^
      --chat-history-file "%TEMP%\spectre_aider_history.md"
