param(
    [Parameter(Mandatory = $true)]
    [string]$SqlPath,

    [string]$Dsn = $env:MO_DB_DSN,

    [switch]$Force,

    [switch]$NoSingleTransaction,

    [switch]$EchoSql
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

trap {
    [Console]::Error.WriteLine("")
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    $logVariable = Get-Variable -Name logPath -ErrorAction SilentlyContinue
    if ($logVariable -and $logVariable.Value) {
        [Console]::Error.WriteLine("Log: $($logVariable.Value)")
    }
    exit 1
}

if (-not $Dsn) {
    $Dsn = "postgresql+asyncpg://postgres:1234@localhost:5432/memory_orchestrator"
}

$SqlPath = (Resolve-Path -LiteralPath $SqlPath).Path
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logPath = Join-Path $logDir ("import-backup-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

function Find-Psql {
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    $default = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
    if (Test-Path -LiteralPath $default) {
        return $default
    }

    throw "psql was not found. Add PostgreSQL bin to PATH or install PostgreSQL client tools."
}

function Convert-ToPsqlUri([string]$SqlAlchemyDsn) {
    return $SqlAlchemyDsn -replace "^postgresql\+asyncpg://", "postgresql://"
}

function Get-MaintenanceUri([string]$PsqlUri) {
    $builder = [System.UriBuilder]::new([System.Uri]$PsqlUri)
    $builder.Path = "postgres"
    return $builder.Uri.AbsoluteUri
}

function Get-DatabaseName([string]$PsqlUri) {
    $uri = [System.Uri]$PsqlUri
    $database = $uri.AbsolutePath.TrimStart("/")
    if (-not $database) {
        throw "DSN does not include a target database name."
    }
    return [System.Uri]::UnescapeDataString($database)
}

function Quote-Literal([string]$Value) {
    return "'" + $Value.Replace("'", "''") + "'"
}

function Quote-Identifier([string]$Value) {
    return '"' + $Value.Replace('"', '""') + '"'
}

function Invoke-PsqlChecked([string[]]$Arguments, [string]$Step) {
    Write-Host ""
    Write-Host "==> $Step"
    & $script:Psql @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with psql exit code $LASTEXITCODE. Log: $logPath"
    }
}

$script:Psql = Find-Psql
$targetUri = Convert-ToPsqlUri $Dsn
$maintenanceUri = Get-MaintenanceUri $targetUri
$databaseName = Get-DatabaseName $targetUri
$file = Get-Item -LiteralPath $SqlPath

$dropCount = (Select-String -LiteralPath $SqlPath -Pattern "^\s*DROP\s+" -CaseSensitive:$false).Count
$copyCount = (Select-String -LiteralPath $SqlPath -Pattern "^COPY\s+" -CaseSensitive:$false).Count
$hasHnsw = [bool](Select-String -LiteralPath $SqlPath -Pattern "USING\s+hnsw|memories_embedding_idx" -CaseSensitive:$false -Quiet)

Write-Host "SQL file: $SqlPath"
Write-Host ("Size: {0:N0} bytes" -f $file.Length)
Write-Host "Target database: $databaseName"
Write-Host "Maintenance database: postgres"
Write-Host "COPY sections: $copyCount"
Write-Host "DROP statements: $dropCount"
Write-Host "HNSW vector index detected: $hasHnsw"
Write-Host "Log: $logPath"

if ($dropCount -gt 0 -and -not $Force) {
    throw "This dump contains DROP statements. Re-run with -Force to import it."
}

$env:PGCONNECT_TIMEOUT = "10"

Invoke-PsqlChecked @(
    $maintenanceUri,
    "-v", "ON_ERROR_STOP=1",
    "-v", "VERBOSITY=verbose",
    "--echo-errors",
    "-c", "SELECT 1"
) "Checking PostgreSQL maintenance connection"

$existsSql = "SELECT 1 FROM pg_database WHERE datname = $(Quote-Literal $databaseName)"
$exists = & $script:Psql $maintenanceUri "-Atq" "-v" "ON_ERROR_STOP=1" "--echo-errors" "-c" $existsSql
if ($LASTEXITCODE -ne 0) {
    throw "Database existence check failed with psql exit code $LASTEXITCODE."
}

if (-not $exists) {
    Invoke-PsqlChecked @(
        $maintenanceUri,
        "-v", "ON_ERROR_STOP=1",
        "-v", "VERBOSITY=verbose",
        "--echo-errors",
        "-c", "CREATE DATABASE $(Quote-Identifier $databaseName)"
    ) "Creating target database"
}
else {
    Write-Host ""
    Write-Host "==> Target database already exists"
}

$importArgs = @(
    $targetUri,
    "-v", "ON_ERROR_STOP=1",
    "-v", "VERBOSITY=verbose",
    "--echo-errors",
    "-L", $logPath,
    "-f", $SqlPath
)

if (-not $NoSingleTransaction) {
    $importArgs = @("--single-transaction") + $importArgs
}

if ($EchoSql) {
    $importArgs = @("--echo-all") + $importArgs
}

if ($hasHnsw) {
    Write-Host ""
    Write-Host "Note: this dump builds an HNSW vector index near the end. That step can look idle."
}

$start = Get-Date
Invoke-PsqlChecked $importArgs "Importing SQL dump"
$elapsed = (Get-Date) - $start

Write-Host ""
Write-Host ("Import finished in {0:c}" -f $elapsed)
Write-Host "Log: $logPath"
