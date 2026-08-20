<p align="center">
  <img src="assets/demo.png" alt="Kanzan SCRCPY Launcher Demo" width="600"/>
</p>

<h1 align="center">Kanzan SCRCPY Launcher</h1>

<p align="center">
  Interactive CLI launcher for <a href="https://github.com/Genymobile/scrcpy">scrcpy</a> — supports real Android devices and AVD emulators with auto-boot.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white"/>
  <img alt="Platform macOS" src="https://img.shields.io/badge/Platform-macOS-lightgrey?logo=apple"/>
  <img alt="Platform Windows" src="https://img.shields.io/badge/Platform-Windows-0078D4?logo=windows"/>
  <img alt="Platform Linux" src="https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black"/>
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green"/>
  <img alt="scrcpy" src="https://img.shields.io/badge/scrcpy-2.x-orange"/>
</p>

---

## Features

- **Real device support** — detect and mirror any USB/Wi-Fi connected Android device
- **AVD emulator support** — list stopped AVDs, auto-launch and wait for full boot, then connect
- **Multi-session** — launch scrcpy on multiple devices simultaneously
- **Session management** — reconnect or kill individual sessions from the menu
- **Wi-Fi ADB pairing** — pair and connect new devices wirelessly via pairing code (Android 11+), no USB needed after initial pair
- **One-click launch** — `.command` (macOS) / `.bat` (Windows) / `.sh` (Linux) opens a terminal and runs everything automatically
- **Cross-platform** — same Python core runs on macOS, Windows, and Linux (including Raspberry Pi)

---

## Platform Support

| Platform | Real Device | AVD Emulator | Launcher |
|---|---|---|---|
| macOS | ✅ | ✅ | `scrcpy.command` |
| Windows | ✅ | ✅ | `scrcpy.bat` |
| Ubuntu / Debian | ✅ | ✅ | `scrcpy.sh` |
| Fedora / Arch | ✅ | ✅ | `scrcpy.sh` |
| Raspberry Pi OS | ✅ | ❌ * | `scrcpy.sh` |
| ChromeOS (Linux) | ✅ | ⚠️ limited | `scrcpy.sh` |

> *Raspberry Pi: Android `emulator` binary is not available for ARM architecture. Real device mirroring via USB works perfectly.

---

## Prerequisites

> **Android device:** Enable **Developer Options** → **USB Debugging** on your phone before connecting.

### macOS

| Dependency | Install |
|---|---|
| [Homebrew](https://brew.sh) | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| [scrcpy](https://github.com/Genymobile/scrcpy) | `brew install scrcpy` |
| [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) (`adb`) | `brew install android-platform-tools` |
| Python 3.8+ | Pre-installed on macOS, or `brew install python3` |

### Windows

| Dependency | Install |
|---|---|
| [scrcpy](https://github.com/Genymobile/scrcpy) | `winget install Genymobile.scrcpy` or `choco install scrcpy` |
| [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools) (`adb`) | `winget install Google.PlatformTools` or [download manually](https://developer.android.com/tools/releases/platform-tools) |
| Python 3.8+ | `winget install Python.Python.3` — check **"Add Python to PATH"** during install |

> **Tip:** After installing Platform Tools manually, add the folder to your `PATH` via System Properties → Environment Variables.

### Linux (Ubuntu / Debian / Raspberry Pi OS)

```bash
sudo apt update
sudo apt install scrcpy adb python3

# Allow USB access without sudo (required on most distros)
sudo usermod -aG plugdev $USER
# Log out and back in for group change to take effect
```

### Linux (Fedora)

```bash
sudo dnf install scrcpy android-tools python3
sudo usermod -aG plugdev $USER
```

### Linux (Arch)

```bash
sudo pacman -S scrcpy android-tools python
sudo usermod -aG plugdev $USER
```

---

## Installation

```bash
# Clone repository
git clone https://github.com/kanzankazu/Kanzan_SCRCPY_Auto.git
cd Kanzan_SCRCPY_Auto
```

**macOS / Linux** — make launchers executable:
```bash
chmod +x scrcpy.command scrcpy.sh
```

No pip install needed — zero external Python dependencies.

---

## Usage

### macOS

**Option A — Double-click**

Double-click `scrcpy.command` in Finder.

> First time: right-click → **Open** to bypass Gatekeeper.

**Option B — Terminal**
```bash
python3 scrcpy_launcher.py
```

---

### Windows

**Option A — Double-click**

Double-click `scrcpy.bat` in File Explorer.

> If Windows SmartScreen blocks it: click **More info** → **Run anyway**.

**Option B — Command Prompt / PowerShell**
```bat
python scrcpy_launcher.py
```

---

### Linux / Raspberry Pi

**Option A — Terminal (recommended)**
```bash
./scrcpy.sh
```

**Option B — Run Python directly**
```bash
python3 scrcpy_launcher.py
```

> **Desktop environments (GNOME, KDE):** You can double-click `scrcpy.sh` in the file manager.  
> If it asks "Run" or "Display" — choose **Run in Terminal**.

---

## How It Works

```
==================================================
                 scrcpy Launcher
==================================================

  No active sessions.

  Actions:
  L - Launch scrcpy
  R - Reconnect (kill + relaunch active session)
  K - Kill / stop active session
  P - Pair new device via Wi-Fi ADB
  Q - Quit

  Choose action [L/R/K/P/Q]: _
```

### Wi-Fi ADB Pairing Flow (menu P)

**Requirements:**

| Requirement | Detail |
|---|---|
| Android version | **11 (API 30) or newer** — not available on Android 10 and below |
| Same Wi-Fi network | Phone and computer must be on the **same subnet** (same router) |
| Developer Options | Must be enabled on the phone |
| Hotspot | ❌ Phone hotspot → computer is a different subnet, will fail |

**How to enable on the phone:**
1. Settings → Developer Options → **Wireless Debugging** → toggle ON
2. Tap **"Pair device with pairing code"**
3. Note the **IP address**, **Pairing Port**, and **6-digit Pairing Code** shown on screen

> The pairing code expires quickly — have the launcher ready before tapping "Pair device with pairing code".

```
  ── Wi-Fi ADB Pairing ──────────────────────────────────
  Requirements:
  ✓ Android 11 (API 30) or newer
  ✓ Phone and computer on the SAME Wi-Fi network
  ✓ Developer Options enabled on the phone
  ✗ Android 10 and below not supported (use USB instead)
  ✗ Phone hotspot → computer will not work (different subnet)

  How to enable on the phone:
  Settings → Developer Options → Wireless Debugging → ON
  Then tap: 'Pair device with pairing code'
  → Note the IP address, Pairing Port, and 6-digit Pairing Code

  Phone IP address (0 = back): 192.168.1.42
  Pairing port (from phone screen, 0 = back): 37149
  Pairing code (6 digits, 0 = back): 123456

  → Pairing with 192.168.1.42:37149 ...
  Successfully paired to 192.168.1.42:37149

  ✓ Pairing successful!

  Connect port (0 = back): 42069

  → Connecting to 192.168.1.42:42069 ...
  connected to 192.168.1.42:42069

  ✓ Device 192.168.1.42:42069 is ready!
  Go back to the menu and press L to launch scrcpy.
```

> **Note:** Pairing port and connect port are two different ports.
> - **Pairing port** → shown in the "Pair device with pairing code" dialog (random 5-digit, changes every session)
> - **Connect port** → larger port number on the main Wireless Debugging screen (persists while Wireless Debugging is on)

### Launch Flow (menu L)

```
==================================================
                 scrcpy Launcher
==================================================

  No active sessions.

  Actions:
  L - Launch scrcpy
  R - Reconnect (kill + relaunch active session)
  K - Kill / stop active session
  P - Pair new device via Wi-Fi ADB
  Q - Quit

  Choose action [L/R/K/P/Q]: l

  Available devices:

  1. emulator-5554  [sdk_gphone64_arm64]  (emulator - running)
  2. Small_Phone  (AVD - stopped)

  Select device (e.g. 1 2 / 'a' = all / '0' or 'b' = back):
  Choice: _
```

```
Press L
   │
   ├─ Real device connected?  → select device → launch scrcpy
   │
   └─ No real device?
         │
         ├─ AVD already running? → select emulator → launch scrcpy
         │
         └─ AVD stopped?  → select AVD → auto-boot → wait → launch scrcpy
```

### Multi-select

When multiple devices are available, type numbers separated by spaces — or `a` for all:

```
  1. AIZTC6OJVW9DNFYD  [POCO X6 Pro]  (real device)
  2. Pixel_6_API_34     (AVD - stopped)

  Select device (e.g. 1 2 / 'a' = all / '0' or 'b' = back):
  Choice: 1 2
```

---

## Project Structure

```
Kanzan_SCRCPY_Auto/
├── scrcpy_launcher.py      # Core launcher script (cross-platform)
├── scrcpy.command          # Double-click entry point — macOS
├── scrcpy.bat              # Double-click entry point — Windows
├── scrcpy.sh               # Entry point — Linux / Raspberry Pi
├── assets/
│   └── demo.png            # Screenshot for README
├── docs/
│   └── CONTRIBUTING.md
├── .gitignore
├── LICENSE
└── README.md
```

---

## Troubleshooting

### Common (all platforms)

**Device not detected**
```bash
# Verify ADB sees your device
adb devices

# If "unauthorized" → check your phone screen and tap "Allow"
# If "offline" → restart ADB server
adb kill-server
adb start-server
```

**AVD emulator not found**
- Make sure AVDs are created in Android Studio → Device Manager
- Set `ANDROID_HOME` in your environment:

  ```bash
  # macOS / Linux — add to ~/.zshrc or ~/.bashrc
  export ANDROID_HOME=~/Library/Android/sdk        # macOS
  export ANDROID_HOME=~/Android/Sdk                # Linux

  # Windows — System Properties → Environment Variables
  # Variable: ANDROID_HOME
  # Value:    C:\Users\<YourName>\AppData\Local\Android\Sdk
  ```

---

### macOS

**`brew: command not found`**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**`adb` or `scrcpy` not found**
```bash
brew install android-platform-tools scrcpy
```

**Gatekeeper blocks `scrcpy.command`**
```bash
xattr -d com.apple.quarantine scrcpy.command
```

---

### Windows

**`python` not found**
- Reinstall from [python.org](https://www.python.org/downloads/) — check **"Add Python to PATH"**

**`adb` or `scrcpy` not found**
```bat
winget install Google.PlatformTools
winget install Genymobile.scrcpy
```

**SmartScreen blocks `scrcpy.bat`**

Click **More info** → **Run anyway**. Or right-click → **Properties** → check **Unblock** → OK.

---

### Linux / Raspberry Pi

**Device not detected (permission denied)**
```bash
# Add user to plugdev group
sudo usermod -aG plugdev $USER

# Install udev rules for ADB
sudo apt install android-sdk-platform-tools-common   # Ubuntu/Debian

# Log out and back in, then verify:
adb devices
```

**`scrcpy` not found**
```bash
# Ubuntu/Debian/Raspberry Pi OS
sudo apt install scrcpy

# Fedora
sudo dnf install scrcpy

# Arch
sudo pacman -S scrcpy

# Snap (any distro)
sudo snap install scrcpy --classic
```

**`scrcpy.sh` permission denied**
```bash
chmod +x scrcpy.sh
./scrcpy.sh
```

**Display not available (headless server)**

scrcpy requires a display. On headless Linux, use X11 forwarding:
```bash
ssh -X user@host
./scrcpy.sh
```

**Raspberry Pi: AVD not supported**

The Android `emulator` binary is not available for ARM. Use a real Android device connected via USB instead.

---

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md).

---

## License

MIT — see [LICENSE](LICENSE) file.

---

<p align="center">Made with ☕ by <a href="https://github.com/kanzankazu">Faisal Bahri (kanzankazu)</a></p>
