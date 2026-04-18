#!/usr/bin/env bash
# Проброс USB (COM/UART) в WSL2 через usbipd-win с хоста Windows.
#
# На Windows один раз: winget install usbipd
# В WSL (Ubuntu/Debian): sudo apt update && sudo apt install -y linux-tools-virtual hwdata
#   и при необходимости: sudo update-alternatives --install /usr/local/bin/usbip usbip /usr/lib/linux-tools/*/usbip 20
#
# Использование:
#   ./scripts/wsl-usb-forward.sh list          # список USB (через powershell + usbipd)
#   ./scripts/wsl-usb-forward.sh attach 1-2  # проброс BUSID в WSL
#   ./scripts/wsl-usb-forward.sh modules       # загрузка vhci (если attach ругается)
#   ./scripts/wsl-usb-forward.sh devices       # локальные /dev/tty*
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

have_ps1() {
  command -v powershell.exe >/dev/null 2>&1
}

ps_usbipd() {
  # -NoProfile быстрее; usbipd должен быть в PATH на Windows
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$*"
}

cmd="${1:-help}"

case "$cmd" in
  list)
    if ! have_ps1; then
      echo "powershell.exe недоступен (вы не в WSL или нет interop)." >&2
      exit 1
    fi
    echo "=== Устройства на стороне Windows (usbipd list) ==="
    ps_usbipd "if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) { Write-Error 'Установите usbipd: winget install usbipd' }; usbipd list"
    echo ""
    echo "Найдите строку с вашим USB-UART (COM3), запомните BUSID (например 1-2), затем:"
    echo "  $0 attach <BUSID>"
    ;;
  attach)
    bus="${2:-}"
    if [[ -z "$bus" ]]; then
      echo "Укажите BUSID: $0 attach 1-2" >&2
      exit 1
    fi
    if ! have_ps1; then
      echo "powershell.exe недоступен." >&2
      exit 1
    fi
    echo "Attaching $bus to WSL (Admin PowerShell on Windows if this fails)..."
    # Inline Command avoids UTF-8 .ps1 parse issues when run from WSL path
    if [[ "${3:-}" == "auto" ]]; then
      ps_usbipd "usbipd attach --wsl --busid $bus --auto-attach"
    else
      ps_usbipd "usbipd attach --wsl --busid $bus"
    fi
    sleep 1
    "$0" devices
    ;;
  modules)
    echo "Загрузка модулей USB/IP (может потребоваться пароль sudo)..."
    sudo modprobe usbip-core 2>/dev/null || true
    sudo modprobe vhci-hcd 2>/dev/null || true
    echo "Готово. Если modprobe не находит модуль — обновите WSL: wsl --update"
    ;;
  devices)
    echo "=== Последовательные порты в этой WSL-сессии ==="
    ls -la /dev/ttyS{0..7} 2>/dev/null || true
    ls -la /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true
    echo ""
    echo "COM3 в Windows после attach обычно становится /dev/ttyUSB0 или /dev/ttyACM0 (смотрите dmesg | tail)."
    ;;
  esphome)
    # Пример: BUS=/dev/ttyUSB0 ./scripts/wsl-usb-forward.sh esphome
    dev="${SERIAL_DEV:-/dev/ttyUSB0}"
    cfg="${ESPHOME_CFG:-$ROOT/esphome/bird-feeder-scale.yaml}"
    if [[ ! -e "$dev" ]]; then
      echo "Нет $dev. Сделайте: $0 list && $0 attach <BUSID> && export SERIAL_DEV=/dev/ttyUSB0" >&2
      exit 1
    fi
    cd "$ROOT"
    exec esphome run "$cfg" --device "$dev"
    ;;
  help|*)
    cat <<EOF
Проброс USB-UART (COM) из Windows в WSL2 через usbipd.

  1) Windows: winget install usbipd
  2) WSL: sudo apt install -y linux-tools-virtual hwdata
     (при необходимости см. комментарии в начале этого файла про update-alternatives для usbip)
  3) $0 list
  4) $0 attach <BUSID>     # при отказе — PowerShell от администратора с тем же BusId
  5) $0 devices            # убедиться, что появился /dev/ttyUSB0 или ttyACM0

ESPHome (после attach):

  SERIAL_DEV=/dev/ttyUSB0 $0 esphome

Документация Microsoft: https://learn.microsoft.com/windows/wsl/connect-usb
EOF
    ;;
esac
