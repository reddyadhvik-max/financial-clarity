# Financial Clarity - one-shot startup
# Sets up dependencies (first run only) and launches every service:
#   - backend            (Offer Decoder API)      -> http://127.0.0.1:9000
#   - person4-data-parsing (Offer Parser API)      -> http://127.0.0.1:9100
#   - Salary Decode India Web App (frontend)       -> http://127.0.0.1:9443
# (fin2 fork — uses 9000/9100/9443 instead of 8000/8100/8443 so it can run
# alongside the original financial-clarity-master project without colliding.)
# Each service opens in its own terminal window so logs stay visible.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Ensure-Venv {
    param([string]$path, [string]$requirements)
    $venv = Join-Path $path ".venv"
    if (-not (Test-Path $venv)) {
        Write-Host "Creating virtualenv in $path ..."
        python -m venv $venv
        & "$venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
        & "$venv\Scripts\python.exe" -m pip install -r (Join-Path $path $requirements)
    }
}

Write-Host "== Setting up backend venv ==" -ForegroundColor Cyan
Ensure-Venv -path (Join-Path $root "backend") -requirements "requirements.txt"

Write-Host "== Setting up person4-data-parsing venv ==" -ForegroundColor Cyan
Ensure-Venv -path (Join-Path $root "person4-data-parsing") -requirements "requirements.txt"

$frontendDir = Join-Path $root "Salary Decode India Web App"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "== Installing frontend dependencies (npm install) ==" -ForegroundColor Cyan
    Push-Location $frontendDir
    npm install
    Pop-Location
}

$logDir = Join-Path $root ".run-logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Write-Host "== Launching services ==" -ForegroundColor Cyan

# Backend API
Start-Process powershell -WorkingDirectory (Join-Path $root "backend") -ArgumentList @(
    "-NoExit", "-Command",
    ".\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 9000 2>&1 | Tee-Object -FilePath '$logDir\backend.log'"
)

# Offer-letter parser API
Start-Process powershell -WorkingDirectory (Join-Path $root "person4-data-parsing") -ArgumentList @(
    "-NoExit", "-Command",
    ".\.venv\Scripts\Activate.ps1; uvicorn parser.api:app --reload --port 9100 2>&1 | Tee-Object -FilePath '$logDir\parser.log'"
)

# Frontend dev server
Start-Process powershell -WorkingDirectory $frontendDir -ArgumentList @(
    "-NoExit", "-Command",
    "`$env:PORT='9443'; `$env:VITE_API_BASE_URL='http://localhost:9000'; npm run dev 2>&1 | Tee-Object -FilePath '$logDir\frontend.log'"
)

Write-Host "Waiting for services to come up..." -ForegroundColor Cyan
$targets = @(
    @{ name = "backend"; port = 9000 },
    @{ name = "parser"; port = 9100 },
    @{ name = "frontend"; port = 9443 }
)
$deadline = (Get-Date).AddSeconds(45)
$pending = $targets.Clone()
while ($pending.Count -gt 0 -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    $pending = $pending | Where-Object {
        -not (Test-NetConnection -ComputerName 127.0.0.1 -Port $_.port -InformationLevel Quiet -WarningAction SilentlyContinue)
    }
}
foreach ($t in $pending) {
    Write-Host "  WARNING: $($t.name) did not come up on port $($t.port) - check $logDir\$($t.name).log" -ForegroundColor Yellow
}

if (-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 9443 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    Write-Host "Frontend isn't up yet - not opening the browser. Check .run-logs\frontend.log" -ForegroundColor Yellow
} else {
    Start-Process "http://127.0.0.1:9443"
}

Write-Host ""
Write-Host "All services launched:" -ForegroundColor Green
Write-Host "  Backend API  -> http://127.0.0.1:9000/docs"
Write-Host "  Parser API   -> http://127.0.0.1:9100/docs"
Write-Host "  Frontend     -> http://127.0.0.1:9443"
