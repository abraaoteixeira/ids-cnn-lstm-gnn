@echo off
title SPECTRE Coder - AI Terminal Agent
echo ========================================================
echo   🚀 INICIANDO AGENTE DE TERMINAL CODER (Aider)
echo   🧠 Cérebro: Hermes-3 Llama 70B (NVIDIA NIM)
echo   📦 Repositório: ids-cnn-lstm-gnn
echo ========================================================

:: A chave NUNCA deve ficar hardcoded aqui.
:: Configure ela UMA VEZ no sistema com:
::   [Windows] setx NVIDIA_NIM_KEY "nvapi-SUA_CHAVE_AQUI"
:: E reinicie o terminal. Ela ficará salva permanentemente no seu perfil.
if "%NVIDIA_NIM_KEY%"=="" (
    echo [ERRO] Variavel NVIDIA_NIM_KEY nao encontrada.
    echo Execute: setx NVIDIA_NIM_KEY "nvapi-SUA_CHAVE_AQUI"
    echo Depois feche e reabra este terminal.
    pause
    exit /b 1
)

set OPENAI_API_BASE=https://integrate.api.nvidia.com/v1
set OPENAI_API_KEY=%NVIDIA_NIM_KEY%

:: Executa o Aider com o modelo Hermes-3 (bom raciocínio + seguir instruções)
:: --auto-commits: cria commits Git automaticamente para cada alteração
:: --map-tokens: aumenta o mapa de contexto do repositório para 4096 tokens
aider --model openai/nousresearch/hermes-3-llama-3.1-70b --auto-commits --map-tokens 4096
