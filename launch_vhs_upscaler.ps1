$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$appPy = Join-Path $PSScriptRoot "vhs_upscaler_gui.py"
$quotedAppPy = '"' + $appPy + '"'
$localPrograms = Join-Path $env:LOCALAPPDATA "Programs\Python"
$preferred = @(
    (Join-Path $localPrograms "Python312\pythonw.exe"),
    (Join-Path $localPrograms "Python313\pythonw.exe"),
    (Join-Path $localPrograms "Python312\python.exe"),
    (Join-Path $localPrograms "Python313\python.exe")
)

function Start-VhsUpscaler {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string]$ArgumentString
    )

    Start-Process -FilePath $FilePath -ArgumentList $ArgumentString -WorkingDirectory $PSScriptRoot
    exit 0
}

foreach ($candidate in $preferred) {
    if (Test-Path $candidate) {
        Start-VhsUpscaler -FilePath $candidate -ArgumentString $quotedAppPy
    }
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    Start-VhsUpscaler -FilePath $py.Source -ArgumentString "-3.12 $quotedAppPy"
}

$pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
if ($pythonw) {
    Start-VhsUpscaler -FilePath $pythonw.Source -ArgumentString $quotedAppPy
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
    Start-VhsUpscaler -FilePath $python.Source -ArgumentString $quotedAppPy
}

throw "Python was not found. Install Python 3 first."
