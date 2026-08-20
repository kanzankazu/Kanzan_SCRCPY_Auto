#!/bin/bash
# ─── Kanzan SCRCPY Launcher — macOS Entry Point ──────────────────────────────
# Double-click this file in Finder to launch the scrcpy launcher.
# First time: right-click → Open to bypass Gatekeeper.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# ─── Check scrcpy ─────────────────────────────────────────────────────────────
if ! command -v scrcpy &>/dev/null; then
    echo "Error: scrcpy not found."
    echo ""
    read -p "Install scrcpy via Homebrew now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if ! command -v brew &>/dev/null; then
            echo "Error: Homebrew not found. Visit: https://brew.sh"
            read -p "Press Enter to exit..."
            exit 1
        fi
        echo "Installing scrcpy..."
        brew install scrcpy
        if [ $? -ne 0 ]; then
            echo "Failed to install scrcpy."
            read -p "Press Enter to exit..."
            exit 1
        fi
    else
        echo "Installation cancelled."
        read -p "Press Enter to exit..."
        exit 1
    fi
fi

# ─── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 not found."
    echo "Install via: brew install python3"
    read -p "Press Enter to exit..."
    exit 1
fi

# ─── Check adb ────────────────────────────────────────────────────────────────
if ! command -v adb &>/dev/null; then
    echo "Error: adb not found."
    echo "Install via: brew install android-platform-tools"
    read -p "Press Enter to exit..."
    exit 1
fi

# ─── Launch ───────────────────────────────────────────────────────────────────
python3 "$SCRIPT_DIR/scrcpy_launcher.py"

# Close the Terminal window after Python exits
osascript -e 'tell application "Terminal" to close (every window whose name contains "scrcpy.command")' &>/dev/null
kill -9 $PPID
