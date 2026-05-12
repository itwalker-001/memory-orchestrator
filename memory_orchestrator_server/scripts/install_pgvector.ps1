#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Installs pgvector extension files into a local PostgreSQL 16 installation.

.DESCRIPTION
  Copies vector.dll, vector.control, vector--*.sql, and vector header files
  from scripts/pgvector/ to the PostgreSQL install directory.
  Must be run as Administrator (files land under C:\Program Files).

.PARAMETER PgRoot
  PostgreSQL install root. Defaults to C:\Program Files\PostgreSQL\16.
#>
param(
    [string]$PgRoot = "C:\Program Files\PostgreSQL\16"
)

$ErrorActionPreference = "Stop"

# Resolve script directory and source root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Src = Join-Path $ScriptDir "pgvector"

if (-not (Test-Path $Src)) {
    Write-Error "pgvector source directory not found: $Src"
    exit 1
}
if (-not (Test-Path $PgRoot)) {
    Write-Error "PostgreSQL install dir not found: $PgRoot"
    exit 1
}

Write-Host "Installing pgvector from $Src to $PgRoot"

Copy-Item -Path (Join-Path $Src "lib\vector.dll") `
          -Destination (Join-Path $PgRoot "lib\") -Force
Write-Host "  [ok] vector.dll -> lib\"

Copy-Item -Path (Join-Path $Src "share\extension\*") `
          -Destination (Join-Path $PgRoot "share\extension\") -Force
Write-Host "  [ok] vector.control, vector--*.sql -> share\extension\"

$IncludeDst = Join-Path $PgRoot "include\server\extension\vector"
New-Item -ItemType Directory -Force -Path $IncludeDst | Out-Null
Copy-Item -Path (Join-Path $Src "include\server\extension\vector\*") `
          -Destination $IncludeDst -Force
Write-Host "  [ok] headers -> include\server\extension\vector\"

Write-Host ""
Write-Host "pgvector files installed. No service restart required for CREATE EXTENSION."
Write-Host "Next step: in your controller session, I'll run CREATE EXTENSION vector in the target database."
