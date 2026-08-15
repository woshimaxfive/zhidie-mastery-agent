$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$venvRoot = Join-Path $projectRoot '.venv'
$venvPython = Join-Path $venvRoot 'Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw 'Python was not found. Install Python 3.11 or newer.'
    }
    & $pythonCommand.Source -m venv $venvRoot
}

$pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
if ($null -eq $pnpmCommand) {
    throw 'pnpm was not found. Install Node.js 20+ and run: npm install -g pnpm'
}

Write-Host 'Preparing backend dependencies...'
& $venvPython -m pip install --disable-pip-version-check -e "$backendRoot"
if ($LASTEXITCODE -ne 0) {
    throw 'Backend dependency installation failed.'
}

Write-Host 'Preparing frontend dependencies...'
Push-Location $frontendRoot
try {
    & $pnpmCommand.Source install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) {
        throw 'Frontend dependency installation failed.'
    }
}
finally {
    Pop-Location
}

$backendProcess = $null
$frontendProcess = $null

try {
    $backendProcess = Start-Process -FilePath $venvPython `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
        -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru

    $frontendProcess = Start-Process -FilePath $pnpmCommand.Source `
        -ArgumentList 'dev', '--', '--host', '127.0.0.1', '--port', '5173' `
        -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 1
            if ($health.status -eq 'ok') {
                $ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if (-not $ready) {
        throw 'The backend did not start in time. Use the manual steps in README to inspect logs.'
    }

    Write-Host ''
    Write-Host 'Zhidie is running:' -ForegroundColor Green
    Write-Host '  Frontend    http://127.0.0.1:5173'
    Write-Host '  OpenAPI     http://127.0.0.1:8000/docs'
    Write-Host ''
    Read-Host 'Press Enter to stop both services'
}
finally {
    foreach ($process in @($frontendProcess, $backendProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
