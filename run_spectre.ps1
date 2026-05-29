# ==============================================================================
# SPECTRE_GRID v2.0 - Unified Start Script (Windows + WSL)
# ==============================================================================

Write-Host "Starting SPECTRE_GRID v2.0 Environment..." -ForegroundColor Cyan

# 1. Start FastAPI backend inside WSL (on port 8002)
Write-Host "[*] Starting FastAPI Backend on WSL (Port 8002)..." -ForegroundColor Yellow
$apiJob = Start-Process wsl -ArgumentList '-d Ubuntu -u abras bash -c "cd /home/abras/ids-cnn-lstm-gnn && source .venv_fast/bin/activate && uvicorn dashboard_api_v2:app --host 0.0.0.0 --port 8002"' -NoNewWindow -PassThru

# 2. Start Traffic Simulator inside WSL
Write-Host "[*] Starting Traffic Simulator on WSL..." -ForegroundColor Yellow
$simJob = Start-Process wsl -ArgumentList '-d Ubuntu -u abras bash -c "cd /home/abras/ids-cnn-lstm-gnn && source .venv_fast/bin/activate && python3 traffic_simulator.py"' -NoNewWindow -PassThru

# 3. Start Host Port Forwarder on Windows (mapping localhost:8001 to WSL 8002)
Write-Host "[*] Starting Windows Port Forwarder (Port 8001 -> WSL 8002)..." -ForegroundColor Yellow
$forwardJob = Start-Process .venv\Scripts\python.exe -ArgumentList "C:\Users\abraa\.gemini\antigravity\scratch\wsl_port_forward.py" -NoNewWindow -PassThru

Start-Sleep -Seconds 3

# Check processes
$apiRunning = Get-Process -Id $apiJob.Id -ErrorAction SilentlyContinue
$simRunning = Get-Process -Id $simJob.Id -ErrorAction SilentlyContinue
$forwardRunning = Get-Process -Id $forwardJob.Id -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
if ($apiRunning -and $forwardRunning) {
    Write-Host "ENVIRONMENT STARTED SUCCESSFULLY!" -ForegroundColor Green
    Write-Host "Open in Browser: http://localhost:8001/static/index.html" -ForegroundColor Green
    Write-Host "WebSocket Endpoint: ws://localhost:8001/ws/threats" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Cyan
    Write-Host "PIDs:" -ForegroundColor Cyan
    Write-Host " - FastAPI (WSL): $($apiJob.Id)" -ForegroundColor Cyan
    Write-Host " - Traffic Simulator (WSL): $($simJob.Id)" -ForegroundColor Cyan
    Write-Host " - Port Forwarder (Windows): $($forwardJob.Id)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To stop the environment, run:" -ForegroundColor Yellow
    Write-Host "Stop-Process -Id $($apiJob.Id), $($simJob.Id), $($forwardJob.Id) -Force" -ForegroundColor Red
} else {
    Write-Host "Failed to start one or more components." -ForegroundColor Red
    Write-Host "API running: $($apiRunning -ne $null)"
    Write-Host "Simulator running: $($simRunning -ne $null)"
    Write-Host "Forwarder running: $($forwardRunning -ne $null)"
}
