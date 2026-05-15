#!/usr/bin/env pwsh
# push.ps1 — pack source into tar, stream to server via plink, then rebuild
#
# Usage:
#   .\scripts\push.ps1               # sync + rebuild (token unchanged)
#   .\scripts\push.ps1 -NoRebuild    # sync only
#   .\scripts\push.ps1 -Force        # sync + rebuild base image
#   .\scripts\push.ps1 -RotateToken  # sync + rebuild + rotate ui_admin token

param(
    [switch]$NoRebuild,
    [switch]$Force,
    [switch]$RotateToken
)

$ErrorActionPreference = "Stop"

$TAR    = "$env:SystemRoot\System32\tar.exe"
$PLINK  = "C:\Program Files\PuTTY\plink.exe"
$PW     = "6L2inux~"
$SRV    = "172.16.10.124"
$RUSER  = "root"
$REMOTE = "/opt/memory-orchestrator"
$LOCAL  = Split-Path $PSScriptRoot -Parent

Write-Host "=== Syncing source to ${RUSER}@${SRV}:${REMOTE} ==="

$tmpTar = [System.IO.Path]::Combine(
    [System.IO.Path]::GetTempPath(),
    "mo-push-$(Get-Random).tar"
)

Push-Location $LOCAL
try {
    Write-Host "  Packing sources..."
    & $TAR -cf $tmpTar `
        '--exclude=__pycache__' `
        '--exclude=.venv' `
        '--exclude=node_modules' `
        '--exclude=memory_orchestrator_server/frontend/dist' `
        '--exclude=memory_orchestrator_server/models' `
        '--exclude=memory_orchestrator_server/logs' `
        '--exclude=*.pyc' `
        'memory_orchestrator_server' `
        'scripts/build.sh' `
        'docker-compose.yml'
    if ($LASTEXITCODE -ne 0) { throw "tar failed (exit $LASTEXITCODE)" }

    $sizeMB = [math]::Round((Get-Item $tmpTar).Length / 1MB, 2)
    Write-Host "  Uploading ${sizeMB} MB..."

    # Write a temp bat to avoid cmd quoting issues with paths containing spaces
    $bat = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "mo-push-$(Get-Random).bat")
    "@echo off`n`"$PLINK`" -batch -pw $PW ${RUSER}@${SRV} `"tar -xf - -C $REMOTE`" < `"$tmpTar`"" |
        Out-File $bat -Encoding ASCII
    try {
        cmd /c $bat
        if ($LASTEXITCODE -ne 0) { throw "plink extract failed (exit $LASTEXITCODE)" }
    } finally {
        Remove-Item $bat -ErrorAction SilentlyContinue
    }
} finally {
    Pop-Location
    Remove-Item $tmpTar -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=== Sync complete ==="

if ($NoRebuild) {
    Write-Host "Skipping rebuild (-NoRebuild)."
    exit 0
}

$buildArgs = [System.Collections.Generic.List[string]]::new()
if ($Force)       { $buildArgs.Add("--force") }
if (-not $RotateToken) { $buildArgs.Add("--skip-token") }
$buildArgsStr = if ($buildArgs.Count -gt 0) { " " + ($buildArgs -join " ") } else { "" }

Write-Host ""
Write-Host "=== Rebuilding on server ==="
& $PLINK -pw $PW -batch "${RUSER}@${SRV}" `
    "chmod +x $REMOTE/scripts/build.sh && cd $REMOTE && ./scripts/build.sh$buildArgsStr"
