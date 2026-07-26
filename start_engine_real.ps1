Write-Host "======================================================" -ForegroundColor Cyan
Write-Host '   🔥 SPECTRE_GRID // LIVE KERNEL ENGINE (eBPF) 🔥' -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "Iniciando captura real de rede (Sem simulador de tráfego)" -ForegroundColor DarkGray
Write-Host ""

# 1. Start FastAPI backend inside WSL (Port 8002)
Write-Host "[*] Subindo Servidor FastAPI e Dashboard V2 (Porta 8002)..." -ForegroundColor Yellow
$apiJob = Start-Process wsl -ArgumentList "-d Ubuntu -e bash -c `".venv_wsl/bin/python3 -m uvicorn dashboard_api_v2:app --host 0.0.0.0 --port 8002`"" -NoNewWindow -PassThru

Write-Host "[*] Aguardando o servidor ligar..." -ForegroundColor DarkGray
Start-Sleep -Seconds 3

# 2. Start C++ eBPF Fusion Engine as Root
Write-Host "[*] Anexando Motor C++ (XDP/eBPF) no Kernel do Linux..." -ForegroundColor Red
Write-Host "[!] Isso requer privilégios de ROOT no WSL (Sendo executado via -u root)..." -ForegroundColor Red

# Comando Bash que acha a interface ativa (geralmente eth0 no WSL2) e sobe o motor
$bashScript = "IFACE=`$(ip route ls default | awk '{print `$5}' | head -n 1); if [ -z `"`$IFACE`" ]; then IFACE=eth0; fi; echo '[eBPF] Interface Detectada:' `$IFACE; cd build && ./spectre_fusion `$IFACE"

$engineJob = Start-Process wsl -ArgumentList "-d Ubuntu -u root -e bash -c `"$bashScript`"" -NoNewWindow -PassThru

# 3. Gerador de Tráfego Benigno (Removido a pedido do usuário - 100% tráfego orgânico agora)
# Write-Host "[*] Iniciando Gerador de Tráfego (Dashboard sempre ativo)..." -ForegroundColor DarkGray
# $trafficJob = Start-Process wsl -ArgumentList "-d Ubuntu -e bash spectre_traffic_gen.sh" -NoNewWindow -PassThru

# 4. Socket Data Feeder (Removido a pedido do usuário - Usando apenas motor real)
# Write-Host "[*] Iniciando Socket Feeder (dados em tempo real no Dashboard)..." -ForegroundColor DarkGray
# $feederJob = Start-Process wsl -ArgumentList "-d Ubuntu -u root -e bash spectre_socket_feeder.sh" -NoNewWindow -PassThru

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "[OK] SISTEMA ONLINE! Lendo tráfego real do WSL2." -ForegroundColor Green
Write-Host "Acesse o Dashboard V2 no Chrome do RDP em:" -ForegroundColor Cyan
Write-Host "👉 http://localhost:8002" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "Pressione CTRL+C para derrubar tudo." -ForegroundColor DarkGray

# Wait block to keep window open
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
}
finally {
    Write-Host "`n[*] Derrubando serviços..." -ForegroundColor Yellow
    if ($apiJob -and -not $apiJob.HasExited) { Stop-Process -Id $apiJob.Id -Force -ErrorAction SilentlyContinue }
    if ($engineJob -and -not $engineJob.HasExited) { Stop-Process -Id $engineJob.Id -Force -ErrorAction SilentlyContinue }
    if ($trafficJob -and -not $trafficJob.HasExited) { Stop-Process -Id $trafficJob.Id -Force -ErrorAction SilentlyContinue }
    if ($feederJob -and -not $feederJob.HasExited) { Stop-Process -Id $feederJob.Id -Force -ErrorAction SilentlyContinue }
    wsl -d Ubuntu -e bash -c "pkill -f spectre_traffic_gen.sh ; pkill -f spectre_socket_feeder.sh" 2>$null
    Write-Host "[OK] Encerrado." -ForegroundColor Green
}
