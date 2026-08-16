$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$backendRoot = Join-Path $projectRoot 'backend'
$frontendRoot = Join-Path $projectRoot 'frontend'
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw '.venv was not found. Run scripts/start.ps1 or follow the backend setup steps in README.'
}

$pnpmCommand = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
if ($null -eq $pnpmCommand) {
    throw 'pnpm was not found. Install the frontend dependencies first.'
}

Write-Host 'Running backend rule and flow tests...'
& $venvPython -m pytest (Join-Path $backendRoot 'tests') -q
if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed.' }

Write-Host 'Running the frontend production build...'
Push-Location $frontendRoot
try {
    & $pnpmCommand.Source build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
finally {
    Pop-Location
}

Write-Host 'All checks passed.' -ForegroundColor Green
