@echo off
chcp 65001 > nul
title SPECTRE Coder - DeepSeek V4 (NVIDIA NIM)

:: Path fixo do projeto (evita bug do caractere especial no username)
cd /d "C:\Users\Abra%C3%A3o\Documents\projects\ids-cnn-lstm-gnn" 2>nul || cd /d "%USERPROFILE%\Documents\projects\ids-cnn-lstm-gnn"

echo ========================================================
echo   INICIANDO AGENTE DE TERMINAL CODER (Aider)
echo   Cerebro: DeepSeek V4 Flash via NVIDIA NIM
echo   Repositorio: ids-cnn-lstm-gnn
echo ========================================================

if "%NVIDIA_NIM_KEY%"=="" (
    echo [ERRO] Variavel NVIDIA_NIM_KEY nao encontrada.
    echo Execute: setx NVIDIA_NIM_KEY "nvapi-SUA_CHAVE_AQUI"
    echo Depois feche e reabra este terminal.
    pause
    exit /b 1
)

set OPENAI_API_BASE=https://integrate.api.nvidia.com/v1
set OPENAI_API_KEY=%NVIDIA_NIM_KEY%
set PATH=%USERPROFILE%\.local\bin;%PATH%

:: Flags:
:: --no-show-model-warnings : suprime aviso de contexto desconhecido
:: --no-check-update        : nao pergunta sobre release notes
:: --auto-commits           : commita cada alteracao aceita
:: --map-tokens 4096        : contexto maior do repositorio
aider --model openai/deepseek-ai/deepseek-v4-flash ^
      --no-show-model-warnings ^
      --no-check-update ^
      --auto-commits ^
      --map-tokens 4096 ^
      --chat-history-file "%TEMP%\spectre_aider_history.md"
