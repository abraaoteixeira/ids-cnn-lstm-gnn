@echo off
title SPECTRE Coder - AI Terminal Agent
echo ========================================================
echo   🚀 INICIANDO AGENTE DE TERMINAL CODER (Aider)
echo   🧠 Cérebro: Qwen 3 Coder 480B (NVIDIA NIM)
echo   📦 Repositório: ids-cnn-lstm-gnn
echo ========================================================

:: Configurações da API NVIDIA NIM
set OPENAI_API_BASE=https://integrate.api.nvidia.com/v1
set OPENAI_API_KEY=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

:: Executa o Aider com auto-commit ativado
:: Isso cria commits Git automaticamente para cada alteração sugerida pela IA
aider --model openai/qwen/qwen3-coder-480b-a35b-instruct --auto-commits
