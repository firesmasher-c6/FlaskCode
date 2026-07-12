#Requires -Version 5.1
<#
.SYNOPSIS
    FlaskCode Client launcher (Windows PowerShell)

.DESCRIPTION
    Connects to a FlaskCode-Server and opens an interactive CLI session.

.PARAMETER HostPort
    Server address in HOST@PORT format (e.g. 192.168.1.5@5000)

.PARAMETER Pass
    Server connection password (from server_config).

.PARAMETER User
    Auto-login with this username on startup (will prompt for password).

.PARAMETER NoEncrypt
    Send password in plain text instead of hashing it.

.EXAMPLE
    .\flaskcc.ps1 localhost@5000
    .\flaskcc.ps1 192.168.1.5@5000 -Pass mySecret
    .\flaskcc.ps1 myserver@8080 -Pass abc123 -User alice

.NOTES
    Requires Python 3.9+ in PATH.
    MIT License — No Rights Reserved.
#>

param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$HostPort,

    [Parameter()]
    [string]$Pass = "",

    [Parameter()]
    [string]$User = "",

    [Parameter()]
    [switch]$NoEncrypt
)

# ── find Python ───────────────────────────────────────────────────────────────
$PythonCandidates = @("python", "python3", "py")
$PythonExe = $null

foreach ($candidate in $PythonCandidates) {
    try {
        $ver = & $candidate -c "import sys; v=sys.version_info; print(v.major*100+v.minor)" 2>$null
        if ($LASTEXITCODE -eq 0 -and [int]$ver -ge 309) {
            $PythonExe = $candidate
            break
        }
    } catch { }
}

if (-not $PythonExe) {
    Write-Error "Python 3.9+ is required but not found in PATH."
    Write-Host "Download from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# ── locate flaskcc.py ─────────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClientPy  = Join-Path $ScriptDir "flaskcc.py"

if (-not (Test-Path $ClientPy)) {
    Write-Error "flaskcc.py not found at: $ClientPy"
    exit 1
}

# ── build argument list ────────────────────────────────────────────────────────
$PyArgs = @($ClientPy, $HostPort)

if ($Pass -ne "") {
    $PyArgs += "--pass"
    $PyArgs += $Pass
}

if ($User -ne "") {
    $PyArgs += "--user"
    $PyArgs += $User
}

if ($NoEncrypt) {
    $PyArgs += "--no-encrypt"
}

# ── enable ANSI colours on Windows 10+ ────────────────────────────────────────
if ($PSVersionTable.PSVersion.Major -ge 5) {
    try {
        # Enable virtual terminal processing
        $kernel32 = Add-Type -MemberDefinition @"
[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool GetConsoleMode(IntPtr hConsoleHandle, out uint lpMode);
[DllImport("kernel32.dll", SetLastError=true)]
public static extern bool SetConsoleMode(IntPtr hConsoleHandle, uint dwMode);
[DllImport("kernel32.dll", SetLastError=true)]
public static extern IntPtr GetStdHandle(int nStdHandle);
"@ -Name "Kernel32" -Namespace "Win32" -PassThru 2>$null

        $STD_OUTPUT = -11
        $handle = $kernel32::GetStdHandle($STD_OUTPUT)
        $mode   = 0
        $kernel32::GetConsoleMode($handle, [ref]$mode) | Out-Null
        $ENABLE_VIRTUAL_TERMINAL = 0x0004
        $kernel32::SetConsoleMode($handle, $mode -bor $ENABLE_VIRTUAL_TERMINAL) | Out-Null
    } catch { }
}

# ── launch ─────────────────────────────────────────────────────────────────────
& $PythonExe @PyArgs
exit $LASTEXITCODE
