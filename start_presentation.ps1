# ==============================================================================
# SPECTRE_GRID v2.0 - Presentation Mode (Live, No Simulation)
# ==============================================================================

Write-Host "Iniciando SPECTRE_GRID (Modo Apresentação ao Vivo)..." -ForegroundColor Cyan

# 1. Start FastAPI backend inside WSL (Port 8002)
Write-Host "[*] Subindo o Servidor FastAPI no WSL..." -ForegroundColor Yellow
$apiJob = Start-Process wsl -ArgumentList "-d Ubuntu -e bash -c `".venv_wsl/bin/python3 -m uvicorn dashboard_api_v2:app --host 0.0.0.0 --port 8002`"" -NoNewWindow -PassThru

Write-Host "[*] Aguardando o servidor ligar..." -ForegroundColor DarkGray
Start-Sleep -Seconds 4

# 2. Start Cloudflare Tunnel
Write-Host "[*] Criando link público mundial via Cloudflare Tunnel..." -ForegroundColor Yellow
Write-Host "--------------------------------------------------------" -ForegroundColor Green
Write-Host "O link publico vai aparecer logo abaixo (terminado em .trycloudflare.com)" -ForegroundColor Green
Write-Host "Mande esse link para as pessoas da platéia!" -ForegroundColor Green
Write-Host "--------------------------------------------------------" -ForegroundColor Green

# Executa o cloudflared que acabamos de baixar
.\scratch\cloudflared.exe tunnel --url http://localhost:8002

# Ao fechar o tunnel (Ctrl+C), mata o servidor FastAPI também
Stop-Process -Id $apiJob.Id -Force -ErrorAction SilentlyContinue
