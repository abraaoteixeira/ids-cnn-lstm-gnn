@echo off
title SPECTRE Coder - DeepSeek V4 (NVIDIA NIM)
echo ========================================================
echo   🚀 INICIANDO AGENTE DE TERMINAL CODER (Aider)
echo   🧠 Cérebro: DeepSeek V4 Flash (NVIDIA NIM) [TESTADO OK]
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

:: Executa o Aider com o modelo DeepSeek V4 Flash (confirmado funcionando!)
:: Para usar o modelo maior (Pro), comente a linha abaixo e descomente a seguinte:
aider --model openai/deepseek-ai/deepseek-v4-flash --auto-commits --map-tokens 4096
:: aider --model openai/deepseek-ai/deepseek-v4-pro --auto-commits --map-tokens 4096
