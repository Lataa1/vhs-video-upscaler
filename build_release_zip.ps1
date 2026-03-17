param(
    [string]$Version = "0.1.0"
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$repoRoot = $PSScriptRoot
$exePath = Join-Path $repoRoot "dist\VHSUpscaler.exe"

if (-not (Test-Path $exePath)) {
    throw "Missing build output: $exePath. Run build_exe.ps1 first."
}

$packageName = "VHSUpscaler-$Version-windows-x64"
$stagingRoot = Join-Path $repoRoot "release-build"
$artifactRoot = Join-Path $repoRoot "release-artifacts"
$stagingDir = Join-Path $stagingRoot $packageName
$zipPath = Join-Path $artifactRoot "$packageName.zip"

if (Test-Path $stagingDir) {
    Remove-Item -Recurse -Force $stagingDir
}
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

New-Item -ItemType Directory -Force $stagingDir | Out-Null
New-Item -ItemType Directory -Force $artifactRoot | Out-Null

$filesToCopy = @(
    "dist\VHSUpscaler.exe",
    "vhs_upscaler_gui.py",
    "vhs_upscaler_config.json",
    "launch_vhs_upscaler.bat",
    "launch_vhs_upscaler.ps1",
    "LICENSE",
    "README.md",
    "VHS_UPSCALER_APP_README.md",
    "CHANGELOG.md",
    "PAL_VHS_HYBRID_WORKFLOW.md",
    "pal_vhs_qtgmc_restore.vpy"
)

foreach ($relativePath in $filesToCopy) {
    $sourcePath = Join-Path $repoRoot $relativePath
    if (-not (Test-Path $sourcePath)) {
        throw "Missing file for release package: $sourcePath"
    }

    $destinationPath = Join-Path $stagingDir $relativePath
    $destinationDir = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Force $destinationDir | Out-Null
    Copy-Item -Path $sourcePath -Destination $destinationPath -Force
}

Compress-Archive -Path (Join-Path $stagingDir '*') -DestinationPath $zipPath -CompressionLevel Optimal

Write-Output "Created release package:"
Write-Output $zipPath
