$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path $PSScriptRoot -Parent

Set-Location $ProjectRoot

$Python = ".\.venv\Scripts\python.exe"

& $Python `
    -m ml.train_station_interchange_model

if ($LASTEXITCODE -ne 0) {
    throw "RailFlow ML training failed."
}