#!/usr/bin/env python3
"""
scrcpy_launcher.py
------------------
Interactive scrcpy launcher with real device + AVD emulator support.

Device detection flow:
1. Check real devices + already-running emulators (adb devices)
2. If no real device found → list stopped AVDs
3. Select AVD → auto-launch emulator → wait for boot → launch scrcpy

Menu actions: Launch, Reconnect, Kill, Pair (Wi-Fi ADB), Refresh
"""

import subprocess
import sys
import os
import time
import re

# { serial: Popen } — active scrcpy sessions
active_sessions: dict[str, subprocess.Popen] = {}

# { avd_name: Popen } — emulator processes launched from this script
emulator_procs: dict[str, subprocess.Popen] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check_command(cmd: str) -> bool:
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


def get_device_label(serial: str) -> str:
    """Fetch device model name for a human-readable label."""
    try:
        r = subprocess.run(
            ["adb", "-s", serial, "shell", "getprop", "ro.product.model"],
            capture_output=True, text=True, timeout=3
        )
        model = r.stdout.strip()
        if model:
            return f"{serial}  [{model}]"
    except Exception:
        pass
    return serial


def get_connected_devices() -> tuple[list[str], list[str]]:
    """
    Return (real_devices, running_emulators) from `adb devices`.
    real_devices      : serials not starting with 'emulator-'
    running_emulators : serials starting with 'emulator-' with status 'device'
    """
    result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
    real, emus = [], []
    for line in result.stdout.strip().splitlines():
        if line.startswith("List of devices") or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serial = parts[0]
            if serial.startswith("emulator-"):
                emus.append(serial)
            else:
                real.append(serial)
    return real, emus


def get_avd_list() -> list[str]:
    """Return list of available AVD names (not necessarily running)."""
    avds = []

    # Try avdmanager first
    if check_command("avdmanager"):
        r = subprocess.run(
            ["avdmanager", "list", "avd", "-c"],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            avds = [line.strip() for line in r.stdout.strip().splitlines() if line.strip()]
            if avds:
                return avds

    # Fallback: scan ~/.android/avd/
    avd_dir = os.path.expanduser("~/.android/avd")
    if os.path.isdir(avd_dir):
        for entry in os.listdir(avd_dir):
            if entry.endswith(".avd"):
                avds.append(entry[:-4])  # strip .avd suffix

    return avds


def get_running_avd_names() -> list[str]:
    """
    Get AVD names of currently running emulators
    via `adb -s emulator-XXXX emu avd name`.
    """
    _, emus = get_connected_devices()
    names = []
    for serial in emus:
        try:
            r = subprocess.run(
                ["adb", "-s", serial, "emu", "avd", "name"],
                capture_output=True, text=True, timeout=3
            )
            # output: "<avd_name>\nOK"
            lines = [l.strip() for l in r.stdout.strip().splitlines() if l.strip() and l.strip() != "OK"]
            if lines:
                names.append(lines[0])
        except Exception:
            pass
    return names


def find_emulator_binary() -> str | None:
    """Find the `emulator` binary in ANDROID_HOME or PATH."""
    if check_command("emulator"):
        return "emulator"
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if android_home:
        candidate = os.path.join(android_home, "emulator", "emulator")
        if os.path.isfile(candidate):
            return candidate
    # Common macOS location
    common = os.path.expanduser("~/Library/Android/sdk/emulator/emulator")
    if os.path.isfile(common):
        return common
    return None


def launch_avd(avd_name: str) -> bool:
    """
    Launch the emulator for the given AVD and wait until fully booted.
    Returns True on success, False on failure or timeout.
    """
    emulator_bin = find_emulator_binary()
    if not emulator_bin:
        print("  ✗ 'emulator' binary not found.")
        print("    Make sure ANDROID_HOME is set or the emulator is in PATH.")
        return False

    print(f"\n  → Launching AVD: {avd_name}")
    print("    Waiting for emulator to boot...")

    proc = subprocess.Popen(
        [emulator_bin, "-avd", avd_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    emulator_procs[avd_name] = proc

    # Wait until adb detects the new emulator and boot completes
    timeout = 120  # seconds
    start = time.time()
    new_serial = None

    print("    ", end="", flush=True)
    while time.time() - start < timeout:
        time.sleep(3)
        print(".", end="", flush=True)

        # Check if emulator process crashed
        if proc.poll() is not None:
            print()
            print("  ✗ Emulator process terminated unexpectedly.")
            return False

        _, emus = get_connected_devices()
        # Find newly appeared emulator not yet in active_sessions
        for serial in emus:
            if serial not in active_sessions:
                try:
                    r = subprocess.run(
                        ["adb", "-s", serial, "emu", "avd", "name"],
                        capture_output=True, text=True, timeout=3
                    )
                    lines = [l.strip() for l in r.stdout.strip().splitlines()
                             if l.strip() and l.strip() != "OK"]
                    if lines and lines[0] == avd_name:
                        new_serial = serial
                except Exception:
                    pass

        if new_serial:
            # Wait for boot_completed
            try:
                r = subprocess.run(
                    ["adb", "-s", new_serial, "shell",
                     "getprop", "sys.boot_completed"],
                    capture_output=True, text=True, timeout=3
                )
                if r.stdout.strip() == "1":
                    print()
                    print(f"  ✓ Emulator ready: {new_serial}")
                    return True
            except Exception:
                pass

    print()
    print(f"  ✗ Timeout ({timeout}s): emulator did not finish booting.")
    return False


def get_new_emulator_serial(avd_name: str) -> str | None:
    """Find the serial of the emulator running a given AVD."""
    _, emus = get_connected_devices()
    for serial in emus:
        try:
            r = subprocess.run(
                ["adb", "-s", serial, "emu", "avd", "name"],
                capture_output=True, text=True, timeout=3
            )
            lines = [l.strip() for l in r.stdout.strip().splitlines()
                     if l.strip() and l.strip() != "OK"]
            if lines and lines[0] == avd_name:
                return serial
        except Exception:
            pass
    return None


def cleanup_dead_sessions():
    """Remove scrcpy sessions that have already exited."""
    dead = [s for s, p in active_sessions.items() if p.poll() is not None]
    for s in dead:
        del active_sessions[s]


def print_header():
    print()
    print("=" * 50)
    print("             scrcpy Launcher")
    print("=" * 50)


# ---------------------------------------------------------------------------
# Device selection
# ---------------------------------------------------------------------------

def select_from_list(items: list[str], labels: list[str], prompt_label: str) -> list[str]:
    """
    Numbered multi-select prompt.
    If only 1 item → return it directly without prompting.
    Returns [] if user chooses to go back (0 / b / Enter).
    """
    if len(items) == 1:
        print(f"\n  Only 1 {prompt_label} available: {labels[0]}")
        return items

    print()
    for i, label in enumerate(labels, start=1):
        print(f"  {i}. {label}")

    print()
    print(f"  Select {prompt_label} (e.g. 1 2 / 'a' = all / '0' or 'b' = back):")

    while True:
        try:
            raw = input("  Choice: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled.")
            return []

        # Back / cancel
        if raw == "" or raw.lower() in ("0", "b", "back"):
            print("  Going back to menu.")
            return []

        # Select all
        if raw.lower() == "a":
            return items

        parts = raw.split()
        selected, valid = [], True
        for part in parts:
            if not part.isdigit():
                print(f"  Invalid input: '{part}'. Enter numbers, 'a' = all, '0'/'b' = back.\n")
                valid = False
                break
            idx = int(part) - 1
            if idx < 0 or idx >= len(items):
                print(f"  Number {part} is out of range.\n")
                valid = False
                break
            if items[idx] not in selected:
                selected.append(items[idx])

        if valid and selected:
            return selected
        elif valid:
            print("  Nothing selected. Try again.\n")


# ---------------------------------------------------------------------------
# Build device list for launch
# ---------------------------------------------------------------------------

def build_launch_candidates() -> tuple[list[str], list[str], list[str]]:
    """
    Return (serials, labels, types) of devices available to launch.

    Logic:
    - Always include real devices + running emulators
    - If no real device is connected → also include stopped AVDs
    """
    real_devices, running_emus = get_connected_devices()
    running_avd_names = get_running_avd_names()

    serials, labels, types = [], [], []

    # Real devices
    for s in real_devices:
        serials.append(s)
        labels.append(f"{get_device_label(s)}  (real device)")
        types.append("real")

    # Running emulators
    for s in running_emus:
        serials.append(s)
        labels.append(f"{get_device_label(s)}  (emulator - running)")
        types.append("emu_running")

    # Stopped AVDs — only shown when no real device is connected
    if not real_devices:
        all_avds = get_avd_list()
        stopped_avds = [a for a in all_avds if a not in running_avd_names]
        for avd in stopped_avds:
            serials.append(f"avd:{avd}")   # avd: prefix as internal marker
            labels.append(f"{avd}  (AVD - stopped)")
            types.append("avd_stopped")

    return serials, labels, types


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def do_launch_scrcpy(serial: str):
    """Start scrcpy for a single serial and register it in active_sessions."""
    print(f"  → Launching scrcpy: {get_device_label(serial)}")
    proc = subprocess.Popen(
        ["scrcpy", "-s", serial, "--stay-awake"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    active_sessions[serial] = proc


def action_launch():
    cleanup_dead_sessions()
    serials, labels, types = build_launch_candidates()

    if not serials:
        print("\n  No devices or AVDs available.")
        print("  Connect a device or create an AVD in Android Studio.")
        return

    # Skip devices that already have an active session
    already = list(active_sessions.keys())
    filtered = [(s, l, t) for s, l, t in zip(serials, labels, types) if s not in already]

    if not filtered:
        print("\n  All devices already have an active scrcpy session.")
        return

    if already:
        print(f"\n  (Already active, skipped: {', '.join(already)})")

    f_serials, f_labels, f_types = zip(*filtered)
    f_serials, f_labels, f_types = list(f_serials), list(f_labels), list(f_types)

    print(f"\n  Available devices:")
    selected_serials = select_from_list(f_serials, f_labels, "device")
    if not selected_serials:
        return

    print()
    for s in selected_serials:
        idx = f_serials.index(s)
        device_type = f_types[idx]

        if device_type == "avd_stopped":
            # Boot the emulator first
            avd_name = s.replace("avd:", "", 1)
            success = launch_avd(avd_name)
            if not success:
                continue
            # Find the serial of the newly booted emulator
            real_serial = get_new_emulator_serial(avd_name)
            if not real_serial:
                print(f"  ✗ Could not find serial for AVD: {avd_name}")
                continue
            do_launch_scrcpy(real_serial)
        else:
            do_launch_scrcpy(s)

    print("\n  scrcpy is running. Close the scrcpy window to end the session.")


def action_kill(serials: list[str]):
    for serial in serials:
        if serial in active_sessions:
            proc = active_sessions[serial]
            if proc.poll() is None:
                proc.terminate()
                proc.wait()
            print(f"  ✓ Session stopped: {get_device_label(serial)}")
            del active_sessions[serial]


def action_kill_menu():
    cleanup_dead_sessions()
    if not active_sessions:
        print("\n  No active scrcpy sessions.")
        return

    running = list(active_sessions.keys())
    labels = [get_device_label(s) for s in running]
    print(f"\n  Active scrcpy sessions:")
    selected = select_from_list(running, labels, "session")
    if not selected:
        return
    print()
    action_kill(selected)


def action_pair():
    """
    Pair + connect a device via Wi-Fi ADB (Android 11+).

    Flow:
    1. User enters IP + pairing port (from phone: Settings → Developer Options
       → Wireless Debugging → Pair device with pairing code)
    2. adb pair <ip>:<port> with 6-digit pairing code
    3. adb connect <ip>:<connect_port> → device ready to use
    """
    print("\n  ── Wi-Fi ADB Pairing ─────────────────────────────────")
    print()
    print("  Requirements:")
    print("  ✓ Android 11 (API 30) or newer")
    print("  ✓ Phone and computer on the SAME Wi-Fi network")
    print("  ✓ Developer Options enabled on the phone")
    print("  ✗ Android 10 and below not supported (use USB instead)")
    print("  ✗ Phone hotspot → computer will not work (different subnet)")
    print()
    print("  How to enable on the phone:")
    print("  Settings → Developer Options → Wireless Debugging → ON")
    print("  Then tap: 'Pair device with pairing code'")
    print("  → Note the IP address, Pairing Port, and 6-digit Pairing Code")
    print()
    print("  Type '0' or press Enter at any step to go back to the menu.")
    print()

    # Input IP
    try:
        ip = input("  Phone IP address (0 = back): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return
    if not ip or ip in ("0", "b", "back"):
        print("  Going back to menu.")
        return

    # Input pairing port
    try:
        pair_port = input("  Pairing port (from phone screen, 0 = back): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return
    if not pair_port or pair_port in ("0", "b", "back"):
        print("  Going back to menu.")
        return
    if not pair_port.isdigit():
        print("  Invalid port.")
        return

    # Input 6-digit pairing code
    try:
        code = input("  Pairing code (6 digits, 0 = back): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return
    if not code or code in ("0", "b", "back"):
        print("  Going back to menu.")
        return

    # Run adb pair
    print(f"\n  → Pairing with {ip}:{pair_port} ...")
    try:
        proc = subprocess.run(
            ["adb", "pair", f"{ip}:{pair_port}", code],
            capture_output=True, text=True, timeout=15
        )
        output = (proc.stdout + proc.stderr).strip()
        print(f"  {output}")

        if proc.returncode != 0 or "error" in output.lower() or "failed" in output.lower():
            print("\n  ✗ Pairing failed. Check IP, port, and pairing code.")
            return
    except subprocess.TimeoutExpired:
        print("  ✗ Timeout: could not reach device. Check IP and port.")
        return
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return

    print("\n  ✓ Pairing successful!")
    print()

    # Input connect port (main Wireless Debugging port, different from pairing port)
    print("  Now enter the main connection port.")
    print("  (The larger port number under 'IP address & Port' on the Wireless Debugging screen)")
    try:
        connect_port = input("  Connect port (0 = back): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return
    if not connect_port or connect_port in ("0", "b", "back"):
        print("  Going back to menu.")
        return
    if not connect_port.isdigit():
        print("  Invalid port.")
        return

    # Run adb connect
    print(f"\n  → Connecting to {ip}:{connect_port} ...")
    try:
        proc = subprocess.run(
            ["adb", "connect", f"{ip}:{connect_port}"],
            capture_output=True, text=True, timeout=10
        )
        output = (proc.stdout + proc.stderr).strip()
        print(f"  {output}")

        if "connected" in output.lower():
            print(f"\n  ✓ Device {ip}:{connect_port} is ready!")
            print("  Go back to the menu and press L to launch scrcpy.")
        else:
            print("\n  ✗ Connection failed. Try again or check the port.")
    except subprocess.TimeoutExpired:
        print("  ✗ Timeout while connecting.")
    except Exception as e:
        print(f"  ✗ Error: {e}")


def action_reconnect():
    cleanup_dead_sessions()
    if not active_sessions:
        print("\n  No active sessions to reconnect.")
        return

    running = list(active_sessions.keys())
    labels = [get_device_label(s) for s in running]
    print(f"\n  Active sessions (will be restarted):")
    selected = select_from_list(running, labels, "session")
    if not selected:
        return

    print()
    action_kill(selected)

    current_devices, _ = get_connected_devices()
    _, running_emus = get_connected_devices()
    all_connected = current_devices + running_emus

    for serial in selected:
        if serial in all_connected:
            do_launch_scrcpy(serial)
        else:
            print(f"  ✗ Device no longer connected: {serial}")

    print("\n  Reconnect complete.")


# ---------------------------------------------------------------------------
# Status & Main loop
# ---------------------------------------------------------------------------

def get_idle_devices() -> list[str]:
    """
    Return devices that are ADB-connected but have no active scrcpy session.
    Includes real devices + running emulators, excludes active_sessions.
    """
    real, emus = get_connected_devices()
    all_connected = real + emus
    return [s for s in all_connected if s not in active_sessions]


def print_status():
    cleanup_dead_sessions()

    # Active scrcpy sessions
    if active_sessions:
        print(f"\n  Active sessions ({len(active_sessions)}):")
        for s in active_sessions:
            print(f"    ● {get_device_label(s)}")
    else:
        print("\n  No active sessions.")

    # Devices connected via ADB but not yet mirroring
    idle = get_idle_devices()
    if idle:
        print(f"\n  Connected, idle ({len(idle)}):")
        for s in idle:
            print(f"    ○ {get_device_label(s)}")
    else:
        print("  No idle devices.")


def main():
    if not check_command("adb"):
        print("Error: adb not found. Please install Android Platform Tools.")
        sys.exit(1)
    if not check_command("scrcpy"):
        print("Error: scrcpy not found. Install via: brew install scrcpy")
        sys.exit(1)

    while True:
        print_header()
        print_status()
        print()
        print("  Actions:")
        print("  L - Launch scrcpy")
        print("  R - Reconnect (kill + relaunch active session)")
        print("  K - Kill / stop active session")
        print("  P - Pair new device via Wi-Fi ADB")
        print("  F - Refresh device list")
        print("  Q - Quit")
        print()

        try:
            choice = input("  Choose action [L/R/K/P/F/Q]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            choice = "Q"

        if choice == "L":
            action_launch()
        elif choice == "R":
            action_reconnect()
        elif choice == "K":
            action_kill_menu()
        elif choice == "P":
            action_pair()
        elif choice == "F":
            print("\n  Refreshing...")
            continue  # loop immediately → print_header + print_status re-runs
        elif choice == "Q":
            cleanup_dead_sessions()
            if active_sessions:
                print("\n  There are still active scrcpy sessions.")
                try:
                    confirm = input("  Kill all before quitting? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    confirm = "n"
                if confirm == "y":
                    action_kill(list(active_sessions.keys()))
            print("\n  Goodbye!\n")
            break
        else:
            print("\n  Invalid choice. Enter L, R, K, P, F, or Q.")

        if choice != "F":
            input("\n  Press Enter to return to menu...")


if __name__ == "__main__":
    main()
