param(
    [ValidateSet("stable", "beta", "nightly")]
    [string]$Toolchain = "stable",

    [switch]$SkipCargoMirror
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RustupDistServer = "https://mirrors.tuna.tsinghua.edu.cn/rustup"
$RustupUpdateRoot = "$RustupDistServer/rustup"
$CargoSparseRegistry = "sparse+https://mirrors.tuna.tsinghua.edu.cn/crates.io-index/"

function Get-RustupTargetTriple {
    switch ([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture) {
        "X64" { return "x86_64-pc-windows-msvc" }
        "Arm64" { return "aarch64-pc-windows-msvc" }
        "X86" { return "i686-pc-windows-msvc" }
        default { throw "Unsupported Windows architecture: $([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)" }
    }
}

function Set-RustupMirrorEnvironment {
    $env:RUSTUP_DIST_SERVER = $RustupDistServer
    $env:RUSTUP_UPDATE_ROOT = $RustupUpdateRoot

    [Environment]::SetEnvironmentVariable("RUSTUP_DIST_SERVER", $RustupDistServer, "User")
    [Environment]::SetEnvironmentVariable("RUSTUP_UPDATE_ROOT", $RustupUpdateRoot, "User")

    Write-Host "Configured rustup mirror environment variables."
}

function Set-CargoMirror {
    $cargoHome = if ($env:CARGO_HOME) { $env:CARGO_HOME } else { Join-Path $env:USERPROFILE ".cargo" }
    $cargoConfig = Join-Path $cargoHome "config.toml"
    $beginMarker = "# BEGIN install-rust-tsinghua managed"
    $endMarker = "# END install-rust-tsinghua managed"
    $managedBlock = @"
$beginMarker
[source.crates-io]
replace-with = 'mirror'

[source.mirror]
registry = "$CargoSparseRegistry"

[registries.mirror]
index = "$CargoSparseRegistry"
$endMarker
"@

    New-Item -ItemType Directory -Force -Path $cargoHome | Out-Null

    $content = ""
    if (Test-Path $cargoConfig) {
        $backup = "$cargoConfig.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
        Copy-Item -LiteralPath $cargoConfig -Destination $backup
        Write-Host "Backed up existing Cargo config to: $backup"
        $content = Get-Content -LiteralPath $cargoConfig -Raw
    }

    $managedPattern = "(?ms)^$([regex]::Escape($beginMarker)).*?^$([regex]::Escape($endMarker))\r?\n?"
    if ($content -match $managedPattern) {
        $content = [regex]::Replace($content, $managedPattern, "")
    }
    else {
        $cargoSections = @("source\.crates-io", "source\.mirror", "registries\.mirror")
        foreach ($section in $cargoSections) {
            $sectionPattern = "(?ms)^\[$section\]\r?\n.*?(?=^\[|\z)"
            $content = [regex]::Replace($content, $sectionPattern, "")
        }
    }

    $newContent = $content.TrimEnd() + [Environment]::NewLine + [Environment]::NewLine + $managedBlock + [Environment]::NewLine
    Set-Content -LiteralPath $cargoConfig -Encoding UTF8 -Value $newContent

    Write-Host "Configured Cargo crates.io mirror: $cargoConfig"
}

function Install-Rustup {
    $rustup = Get-Command rustup -ErrorAction SilentlyContinue
    if ($rustup) {
        Write-Host "rustup already exists: $($rustup.Source)"
        return
    }

    $targetTriple = Get-RustupTargetTriple
    $installerUrl = "$RustupUpdateRoot/dist/$targetTriple/rustup-init.exe"
    $installerPath = Join-Path $env:TEMP "rustup-init-$targetTriple.exe"

    Write-Host "Downloading rustup-init from: $installerUrl"
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath

    Write-Host "Installing rustup with default host: $targetTriple"
    & $installerPath -y --default-toolchain none --default-host $targetTriple
}

Set-RustupMirrorEnvironment

if (-not $SkipCargoMirror) {
    Set-CargoMirror
}

Install-Rustup

$cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
if (Test-Path $cargoBin) {
    $env:Path = "$cargoBin;$env:Path"
}

rustup toolchain install $Toolchain
rustup default $Toolchain

rustc --version
cargo --version

Write-Host ""
Write-Host "Rust installation finished. Open a new PowerShell window if rustc/cargo are not found in your current shell."
