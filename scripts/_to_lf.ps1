#!/usr/bin/env pwsh
# _to_lf.ps1 — Convert all .sh files in the repo to LF line endings (strip CRLF/BOM)
# Run from any directory: .\scripts\_to_lf.ps1

$repoRoot = Split-Path $PSScriptRoot -Parent
$shFiles = Get-ChildItem -Path $repoRoot -Filter "*.sh" -Recurse `
    | Where-Object { $_.FullName -notmatch '\\\.venv\\|\\node_modules\\|\\\.git\\' }

foreach ($f in $shFiles) {
    $bytes = [System.IO.File]::ReadAllBytes($f.FullName)
    # Strip UTF-8 BOM if present
    $start = 0
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $start = 3
    }
    $text = [System.Text.Encoding]::UTF8.GetString($bytes, $start, $bytes.Length - $start)
    $lf   = $text -replace "`r`n", "`n" -replace "`r", "`n"
    if ($lf -ne $text -or $start -gt 0) {
        [System.IO.File]::WriteAllBytes($f.FullName, [System.Text.Encoding]::UTF8.GetBytes($lf))
        Write-Host "Fixed: $($f.FullName)"
    }
}
Write-Host "Done — $($shFiles.Count) .sh file(s) checked."
