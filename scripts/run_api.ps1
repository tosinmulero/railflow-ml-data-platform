$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path `
    $PSScriptRoot `
    -Parent

Set-Location $ProjectRoot

$Python = ".\.venv\Scripts\python.exe"

Write-Host ""
Write-Host "RailFlow API"
Write-Host "http://127.0.0.1:8000"
Write-Host "Swagger:"
Write-Host "http://127.0.0.1:8000/docs"
Write-Host ""

& $Python `
    -m uvicorn `
    api.main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --reload