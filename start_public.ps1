$ErrorActionPreference = "Stop"

$projectDirectory = $PSScriptRoot
$port = if ($env:PORT) { $env:PORT } else { "5000" }
$localUrl = "http://127.0.0.1:$port"
$localCloudflared = Join-Path $projectDirectory "cloudflared.exe"
$virtualEnvironmentPython = Join-Path $projectDirectory ".venv\Scripts\python.exe"

$pythonPath = $null
if (Test-Path $virtualEnvironmentPython) {
    $pythonPath = $virtualEnvironmentPython
} else {
    $pythonCommand = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    }
    if ($pythonCommand) {
        $pythonPath = $pythonCommand.Source
    }
}

if (-not $pythonPath) {
    Write-Host "Python was not found. Install Python 3.10 or later first." -ForegroundColor Red
    exit 1
}

if (Test-Path $localCloudflared) {
    $cloudflaredPath = $localCloudflared
} else {
    $cloudflaredCommand = Get-Command cloudflared -ErrorAction SilentlyContinue
    if (-not $cloudflaredCommand) {
        Write-Host "cloudflared was not found." -ForegroundColor Yellow
        Write-Host "Place cloudflared.exe next to app.py, then run this script again."
        exit 1
    }
    $cloudflaredPath = $cloudflaredCommand.Source
}

$occupiedPort = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($occupiedPort) {
    Write-Host "Port $port is already in use. Close the old Smart Photo Assistant process first." -ForegroundColor Red
    exit 1
}

$env:FLASK_HOST = "127.0.0.1"
$env:FLASK_DEBUG = "false"

Write-Host "Starting Smart Photo Assistant..." -ForegroundColor Cyan
$serverProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList "app.py" `
    -WorkingDirectory $projectDirectory `
    -PassThru

try {
    $serverReady = $false
    for ($attempt = 1; $attempt -le 15; $attempt += 1) {
        if ($serverProcess.HasExited) {
            throw "Flask failed to start. Run .\.venv\Scripts\python.exe app.py to view the error."
        }
        try {
            $null = Invoke-WebRequest -Uri $localUrl -UseBasicParsing -TimeoutSec 2
            $serverReady = $true
            break
        } catch {
            Start-Sleep -Seconds 1
        }
    }

    if (-not $serverReady) {
        throw "Flask startup timed out. Run .\.venv\Scripts\python.exe app.py to view the error."
    }

    Write-Host ""
    Write-Host "Local site: $localUrl" -ForegroundColor Green
    Write-Host "Creating a public URL. Wait for https://xxxxx.trycloudflare.com" -ForegroundColor Cyan
    Write-Host "Open that HTTPS URL on your phone. Press Ctrl+C when finished." -ForegroundColor Yellow
    Write-Host ""

    & $cloudflaredPath tunnel --url $localUrl
} finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Smart Photo Assistant and the public URL are closed." -ForegroundColor Yellow
}