#Requires -Version 5.1
<#
.SYNOPSIS
  Attach USB device (UART / ESP32) to WSL2 via usbipd-win.

.PARAMETER List
  Show usbipd list only.

.PARAMETER BusId
  e.g. 8-4 from usbipd list.

.PARAMETER AutoAttach
  usbipd --auto-attach (3.1+).
#>
param(
  [switch] $List,
  [string] $BusId = "",
  [switch] $AutoAttach
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
  Write-Error "usbipd not found. Install: winget install usbipd"
}

if ($List -or -not $BusId) {
  Write-Host "=== usbipd list (find USB-SERIAL / CP210x / CH340) ===" -ForegroundColor Cyan
  usbipd list
  if ($List) { exit 0 }
  Write-Host ""
  Write-Host "Next (same window, Admin if attach fails):" -ForegroundColor Yellow
  Write-Host "  .\scripts\wsl-usb-forward.ps1 -BusId <BUSID>"
  Write-Host ""
  exit 0
}

$extra = @()
if ($AutoAttach) { $extra += "--auto-attach" }

$attachArgs = @("attach", "--wsl", "--busid", $BusId) + $extra
Write-Host ">>> usbipd $($attachArgs -join ' ')" -ForegroundColor Green
& usbipd @attachArgs

Write-Host ""
Write-Host "In WSL: ls -la /dev/ttyUSB* /dev/ttyACM*" -ForegroundColor Cyan
