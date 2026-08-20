#!/bin/bash
# ─── Kanzan SCRCPY Launcher — Linux Entry Point ──────────────────────────────
# Works on: Ubuntu, Debian, Fedora, Arch, Raspberry Pi OS, and other distros.
# Run: chmod +x scrcpy.sh && ./scrcpy.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# ─── Detect package manager ───────────────────────────────────────────────────
detect_pkg_manager() {
    if command -v apt-get &>/dev/null; then echo "apt"
    elif command -v dnf &>/dev/null;     then echo "dnf"
    elif command -v pacman &>/dev/null;  then echo "pacman"
    elif command -v snap &>/dev/null;    then echo "snap"
    else echo "unknown"
    fi
}

install_hint_scrcpy() {
    local pm
    pm=$(detect_pkg_manager)
    echo ""
    echo "Install scrcpy:"
    case "$pm" in
        apt)    echo "  sudo apt update && sudo apt install scrcpy" ;;
        dnf)    echo "  sudo dnf install scrcpy" ;;
        pacman) echo "  sudo pacman -S scrcpy" ;;
        snap)   echo "  sudo snap install scrcpy --classic" ;;
        *)      echo "  See: https://github.com/Genymobile/scrcpy#linux" ;;
    esac
    echo "  Or build from source: https://github.com/Genymobile/scrcpy/blob/master/doc/linux.md"
}

install_hint_adb() {
    local pm
    pm=$(detect_pkg_manager)
    echo ""
    echo "Install adb (Android Platform Tools):"
    case "$pm" in
        apt)    echo "  sudo apt update && sudo apt install adb" ;;
        dnf)    echo "  sudo dnf install android-tools" ;;
        pacman) echo "  sudo pacman -S android-tools" ;;
        *)      echo "  Download: https://developer.android.com/tools/releases/platform-tools" ;;
    esac
}

# ─── Dependency checks ────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found."
    pm=$(detect_pkg_manager)
    case "$pm" in
        apt)    echo "  sudo apt install python3" ;;
        dnf)    echo "  sudo dnf install python3" ;;
        pacman) echo "  sudo pacman -S python" ;;
        *)      echo "  See: https://www.python.org/downloads/" ;;
    esac
    exit 1
fi

if ! command -v scrcpy &>/dev/null; then
    echo "Error: scrcpy not found."
    install_hint_scrcpy
    echo ""
    exit 1
fi

if ! command -v adb &>/dev/null; then
    echo "Error: adb not found."
    install_hint_adb
    echo ""
    exit 1
fi

# ─── USB permission check (Linux-specific) ────────────────────────────────────
# ADB requires udev rules for USB access without sudo on most distros.
if ! groups | grep -qE "plugdev|adbusers"; then
    echo "⚠  Warning: Your user may not be in the 'plugdev' group."
    echo "   If your device is not detected, run:"
    echo "     sudo usermod -aG plugdev \$USER"
    echo "   Then log out and back in."
    echo ""
fi

# ─── Launch ───────────────────────────────────────────────────────────────────
cd "$SCRIPT_DIR"
python3 "$SCRIPT_DIR/scrcpy_launcher.py"
