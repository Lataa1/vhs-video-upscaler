$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

py -3.12 -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name VHSUpscaler `
  ".\vhs_upscaler_gui.py"
