$Host.UI.RawUI.WindowTitle = "Flask Code AI"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python was not found on PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainPy = Join-Path $scriptDir "main.py"
$RESTART_CODE = 42

do {
    python $mainPy
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq $RESTART_CODE) {
        Read-Host "Press Enter to reboot"
    }
} while ($exitCode -eq $RESTART_CODE)

Read-Host "Press Enter to exit"