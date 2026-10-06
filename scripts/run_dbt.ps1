param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DbtArgs
)

$ProjectRoot = (
    Resolve-Path "$PSScriptRoot\.."
).Path

$DbtExe = (
    Resolve-Path (
        Join-Path `
            $ProjectRoot `
            ".venv\Scripts\dbt.exe"
    )
).Path

# ---------------------------------------------------------------------
# Native programs such as dbt can legitimately write warnings to STDERR.
# Do not let PowerShell convert those warnings into terminating errors.
# ---------------------------------------------------------------------

$ErrorActionPreference = "Continue"

if (
    Test-Path variable:PSNativeCommandUseErrorActionPreference
) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$env:RAILFLOW_PROJECT_ROOT = (
    $ProjectRoot.Replace(
        "\",
        "/"
    )
)

$env:RAILFLOW_DUCKDB_PATH = (
    (
        Join-Path `
            $ProjectRoot `
            "dbt\railflow_analytics.duckdb"
    ).Replace(
        "\",
        "/"
    )
)

$ProjectDir = Join-Path `
    $ProjectRoot `
    "dbt"

$ProfilesDir = Join-Path `
    $ProjectRoot `
    "dbt\profiles"

& $DbtExe `
    @DbtArgs `
    --project-dir $ProjectDir `
    --profiles-dir $ProfilesDir

$DbtExitCode = $LASTEXITCODE

$global:LASTEXITCODE = $DbtExitCode

if ($DbtExitCode -ne 0) {

    Write-Host ""
    Write-Host "dbt exit code:" $DbtExitCode

    return
}

Write-Host ""
Write-Host "dbt exit code: 0"