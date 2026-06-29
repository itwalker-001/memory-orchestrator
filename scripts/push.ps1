#!/usr/bin/env pwsh
# push.ps1 — pack source into tar, stream to server via plink, then rebuild
#
# Usage:
#   .\scripts\push.ps1 -Server 172.16.10.123           # sync + rebuild
#   .\scripts\push.ps1 -Server 172.16.10.123 -NoRebuild
#   .\scripts\push.ps1 -Server 172.16.10.123 -Force
#   .\scripts\push.ps1 -Server 172.16.10.123 -RotateToken
#
# Credentials can be supplied via parameters or environment variables:
#   MO_PUSH_USER     (default: root)
#   MO_PUSH_PASSWORD

param(
    [Parameter(Mandatory=$true)]
    [string]$Server,

    [string]$User     = $(if ($env:MO_PUSH_USER)     { $env:MO_PUSH_USER }     else { "root" }),
    [string]$Password = $(if ($env:MO_PUSH_PASSWORD) { $env:MO_PUSH_PASSWORD } else {
        Read-Host "Password for ${User}@${Server}"
    }),
    [string]$Remote   = "/opt/memory-orchestrator",
    [string]$HostKey  = "",   # e.g. "SHA256:abc..." — bypasses host-key cache prompt

    [switch]$NoRebuild,
    [switch]$Force,
    [switch]$RotateToken
)

$ErrorActionPreference = "Stop"

$TAR   = "$env:SystemRoot\System32\tar.exe"
$PLINK = "C:\Program Files\PuTTY\plink.exe"
$PSCP  = "C:\Program Files\PuTTY\pscp.exe"
$LOCAL = Split-Path $PSScriptRoot -Parent

$PlinkExtra = if ($HostKey) { @("-hostkey", $HostKey) } else { @() }
$PscpExtra  = if ($HostKey) { @("-hostkey", $HostKey) } else { @() }

Write-Host "=== Syncing source to ${User}@${Server}:${Remote} ==="

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
        '--exclude=memory_orchestrator_server/downloads' `
        '--exclude=*.pyc' `
        'memory_orchestrator_server' `
        'memory_orchestrator_mcp' `
        'scripts/build.sh' `
        'docker-compose.yml' `
        'Dockerfile.db'
    if ($LASTEXITCODE -ne 0) { throw "tar failed (exit $LASTEXITCODE)" }

    $sizeMB = [math]::Round((Get-Item $tmpTar).Length / 1MB, 2)
    Write-Host "  Uploading ${sizeMB} MB..."

    # Clear stale wheels on the remote before extracting: tar is additive, so an
    # older mo-mcp wheel left from a prior deploy would otherwise survive and get
    # listed alongside the current one on the Help page.
    & $PLINK @PlinkExtra -pw $Password -batch "${User}@${Server}" `
        "rm -f $Remote/memory_orchestrator_server/downloads/*.whl"

    $hostKeyFlag = if ($HostKey) { " -hostkey `"$HostKey`"" } else { "" }
    $bat = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "mo-push-$(Get-Random).bat")
    "@echo off`n`"$PLINK`"$hostKeyFlag -batch -pw $Password ${User}@${Server} `"tar -xf - -C $Remote`" < `"$tmpTar`"" |
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

# Stage the locally-built mo-mcp wheel as the pre-staged wheel on the remote.
# build.sh rebuilds it with `uv build` when uv is present; this copy is the
# fallback the else-branch picks up when the server host has no uv toolchain.
$wheel = Get-ChildItem "$LOCAL\memory_orchestrator_mcp\dist\*.whl" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($wheel) {
    Write-Host "  Uploading built wheel: $($wheel.Name)"
    & $PLINK @PlinkExtra -pw $Password -batch "${User}@${Server}" `
        "mkdir -p $Remote/memory_orchestrator_server/downloads"
    & $PSCP @PscpExtra -pw $Password -batch $wheel.FullName `
        "${User}@${Server}:$Remote/memory_orchestrator_server/downloads/"
    if ($LASTEXITCODE -ne 0) { throw "pscp wheel upload failed (exit $LASTEXITCODE)" }
} else {
    Write-Host "  No local wheel in memory_orchestrator_mcp/dist/ — skipping (build.sh will build it if uv is present)."
}

# Fix CRLF on all uploaded .sh files
Write-Host "  Fixing line endings on remote .sh files..."
& $PLINK @PlinkExtra -pw $Password -batch "${User}@${Server}" `
    "find $Remote/scripts -name '*.sh' -exec sed -i 's/\r//' {} \; && chmod +x $Remote/scripts/*.sh"

if ($NoRebuild) {
    Write-Host "Skipping rebuild (-NoRebuild)."
    exit 0
}

$buildArgs = [System.Collections.Generic.List[string]]::new()
if ($Force)          { $buildArgs.Add("--force") }
if (-not $RotateToken) { $buildArgs.Add("--skip-token") }
$buildArgsStr = if ($buildArgs.Count -gt 0) { " " + ($buildArgs -join " ") } else { "" }

Write-Host ""
Write-Host "=== Rebuilding on server ==="
& $PLINK @PlinkExtra -pw $Password -batch "${User}@${Server}" `
    "cd $Remote && ./scripts/build.sh$buildArgsStr"
