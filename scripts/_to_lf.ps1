$f = "D:\AIPROJECT\memory-orchestrator\scripts\build.sh"
$bytes = [System.IO.File]::ReadAllBytes($f)
# Strip UTF-8 BOM (EF BB BF) if present
if ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
    $bytes = $bytes[3..($bytes.Length - 1)]
}
$text = [System.Text.Encoding]::UTF8.GetString($bytes) -replace "`r`n", "`n" -replace "`r", "`n"
[System.IO.File]::WriteAllBytes($f, [System.Text.Encoding]::UTF8.GetBytes($text))
Write-Host "Done"
