$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path `
    $PSScriptRoot `
    -Parent

Set-Location $ProjectRoot

$Python = ".\.venv\Scripts\python.exe"

$DbPath = (
    Resolve-Path `
        ".\mlflow\mlflow.db"
).Path -replace "\\", "/"

$ArtifactPath = (
    Resolve-Path `
        ".\mlflow\artifacts"
).Path -replace "\\", "/"

$BackendUri = (
    "sqlite:///" + $DbPath
)

$ArtifactUri = (
    "file:///" + $ArtifactPath
)

Write-Host ""
Write-Host "RailFlow MLflow UI"
Write-Host "http://127.0.0.1:5000"
Write-Host ""

& $Python `
    -m mlflow `
    server `
    --backend-store-uri `
    $BackendUri `
    --default-artifact-root `
    $ArtifactUri `
    --host 127.0.0.1 `
    --port 5000