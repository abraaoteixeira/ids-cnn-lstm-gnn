# ==============================================================================
# SPECTRE_GRID v2.0 - Unified Start Script (Windows + WSL)
# ==============================================================================
param (
    [int]$Port = 8001,
    [string]$Distro = ""
)

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   🚀 INICIANDO ECOSSISTEMA SPECTRE_GRID V2.0 (WSL)   " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# 0. Auto-detecção de Distro WSL
if (-not $Distro) {
    $rawDistros = (wsl.exe -l -q | ForEach-Object { $_.Trim().Replace("`0", "") } | Where-Object { $_.Length -gt 0 })
    if ($rawDistros -contains "Ubuntu") {
        $Distro = "Ubuntu"
    } elseif ($rawDistros.Count -gt 0) {
        $Distro = $rawDistros[0]
    } else {
        $Distro = ""
    }
}

$distroFlag = if ($Distro) { "-d $Distro" } else { "" }
Write-Host "[*] WSL Distro selecionada: $(if ($Distro) { $Distro } else { 'Padrão' })" -ForegroundColor DarkGray
Write-Host "[*] Porta configurada: $Port" -ForegroundColor DarkGray

# 1. Start FastAPI backend inside WSL
Write-Host "[*] Subindo Servidor FastAPI V2 (Porta $Port)..." -ForegroundColor Yellow
$apiCmd = "if [ -d .venv_wsl ]; then PY=.venv_wsl/bin/python3; elif [ -d .venv ]; then PY=.venv/bin/python3; else PY=python3; fi; `$PY -m uvicorn dashboard_api_v2:app --host 0.0.0.0 --port $Port"
$apiJob = Start-Process wsl -ArgumentList "$distroFlag -e bash -c `"$apiCmd`"" -NoNewWindow -PassThru

# 2. Start Traffic Simulator inside WSL
Write-Host "[*] Subindo Simulador de Tráfego Top-20 STGNN no WSL..." -ForegroundColor Yellow
$simCmd = "if [ -d .venv_wsl ]; then PY=../.venv_wsl/bin/python3; elif [ -d .venv ]; then PY=../.venv/bin/python3; else PY=python3; fi; cd tools && `$PY traffic_simulator.py"
$simJob = Start-Process wsl -ArgumentList "$distroFlag -e bash -c `"$simCmd`"" -NoNewWindow -PassThru

Start-Sleep -Seconds 3

# Check processes
$apiRunning = Get-Process -Id $apiJob.Id -ErrorAction SilentlyContinue
$simRunning = Get-Process -Id $simJob.Id -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
if ($apiRunning) {
    Write-Host "🎉 AMBIENTE SPECTRE_GRID OPERACIONAL COM SUCESSO!" -ForegroundColor Green
    Write-Host " - Dashboard UI:      http://localhost:$Port" -ForegroundColor White
    Write-Host " - WebSocket Stream:  ws://localhost:$Port/ws/threats" -ForegroundColor White
    Write-Host " - Documentação API:  http://localhost:$Port/docs" -ForegroundColor White
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "PIDs dos Processos:" -ForegroundColor Cyan
    Write-Host " - FastAPI (WSL):           $($apiJob.Id)" -ForegroundColor DarkGray
    Write-Host " - Traffic Simulator (WSL):  $($simJob.Id)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "Para encerrar o ambiente, execute:" -ForegroundColor Yellow
    Write-Host "Stop-Process -Id $($apiJob.Id), $($simJob.Id) -Force" -ForegroundColor Red
} else {
    Write-Host "Falha ao inicializar um ou mais componentes." -ForegroundColor Red
    Write-Host "API running: $($apiRunning -ne $null)"
    Write-Host "Simulator running: $($simRunning -ne $null)"
}
