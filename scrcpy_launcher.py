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
                    wait_for_boot_and_tune(new_serial, timeout=30)
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


# ---------------------------------------------------------------------------
# AVD creation helpers
# ---------------------------------------------------------------------------

# Device profiles: (display_label, avd_manager_id, recommended_ram_mb)
DEVICE_PROFILES = [
    ("Medium Phone  (1080×2400, 420 dpi) — recommended",  "medium_phone",   3072),
    ("Pixel 8       (1080×2400, 420 dpi)",                 "pixel_8",        3072),
    ("Pixel 8 Pro   (1344×2992, 560 dpi) — high-end",     "pixel_8_pro",    4096),
    ("Small Phone   (720×1280, 320 dpi)  — lightweight",   "2.7in QVGA",     1536),
    ("Pixel Tablet  (2560×1600, 320 dpi) — tablet layout", "pixel_tablet",   4096),
]

def detect_host_abi() -> str:
    """
    Detect the best ABI for emulator images based on host CPU.
    Apple Silicon → arm64-v8a  |  Intel/AMD → x86_64
    """
    try:
        r = subprocess.run(["uname", "-m"], capture_output=True, text=True)
        machine = r.stdout.strip().lower()
        if machine in ("arm64", "aarch64"):
            return "arm64-v8a"
    except Exception:
        pass
    return "x86_64"


def get_android_home() -> str | None:
    """Return ANDROID_HOME / ANDROID_SDK_ROOT path, or auto-detect common locations."""
    path = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if path and os.path.isdir(path):
        return path
    # Common macOS location
    candidates = [
        os.path.expanduser("~/Library/Android/sdk"),
        os.path.expanduser("~/Android/Sdk"),           # Linux default
        "/usr/local/lib/android/sdk",                  # CI / GitHub Actions
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None


def scan_system_images(android_home: str, preferred_abi: str) -> list[dict]:
    """
    Scan $ANDROID_HOME/system-images/ and return a list of available image dicts:
      { path, api, tag, abi, label, recommended }
    Sorted: preferred ABI first, then by API level descending.
    """
    images_dir = os.path.join(android_home, "system-images")
    if not os.path.isdir(images_dir):
        return []

    images = []
    for android_ver in os.listdir(images_dir):          # e.g. android-34
        ver_path = os.path.join(images_dir, android_ver)
        if not os.path.isdir(ver_path):
            continue
        for tag in os.listdir(ver_path):                # e.g. google_apis
            tag_path = os.path.join(ver_path, tag)
            if not os.path.isdir(tag_path):
                continue
            for abi in os.listdir(tag_path):            # e.g. arm64-v8a
                abi_path = os.path.join(tag_path, abi)
                if not os.path.isdir(abi_path):
                    continue
                # Validate it's a real system image
                if not os.path.isfile(os.path.join(abi_path, "system.img")):
                    continue

                api_num = int(android_ver.replace("android-", "")) if android_ver.replace("android-", "").isdigit() else 0
                recommended = (abi == preferred_abi and tag == "google_apis" and api_num >= 33)

                # Human-readable tag label
                tag_label = {
                    "google_apis":            "Google APIs",
                    "google_apis_playstore":  "Google Play Store",
                    "default":                "AOSP (no Google)",
                }.get(tag, tag)

                label = f"API {api_num}  |  {tag_label:<22}  |  {abi}"
                if recommended:
                    label += "  ← recommended"

                images.append({
                    "path":        f"{android_ver};{tag};{abi}",
                    "api":         api_num,
                    "tag":         tag,
                    "abi":         abi,
                    "label":       label,
                    "recommended": recommended,
                })

    # Sort: recommended first, then by API desc, preferred ABI first
    images.sort(key=lambda x: (
        not x["recommended"],
        -x["api"],
        x["abi"] != preferred_abi,
    ))
    return images


def disable_animations(serial: str):
    """Disable all animation scales on a device/emulator via ADB."""
    for key in ["window_animation_scale", "transition_animation_scale", "animator_duration_scale"]:
        subprocess.run(
            ["adb", "-s", serial, "shell", "settings", "put", "global", key, "0"],
            capture_output=True
        )


def wait_for_boot_and_tune(serial: str, timeout: int = 120):
    """
    Wait until boot_completed == 1, then auto-disable animations.
    Shows a progress indicator while waiting.
    """
    print("    Waiting for full boot", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(3)
        print(".", end="", flush=True)
        try:
            r = subprocess.run(
                ["adb", "-s", serial, "shell", "getprop", "sys.boot_completed"],
                capture_output=True, text=True, timeout=3
            )
            if r.stdout.strip() == "1":
                print(" done!")
                print("  → Disabling animations for faster testing...")
                disable_animations(serial)
                print("  ✓ Animations disabled. Emulator is ready.")
                return True
        except Exception:
            pass
    print()
    print(f"  ⚠  Boot timeout ({timeout}s). You can disable animations manually:")
    print("     adb shell settings put global window_animation_scale 0")
    print("     adb shell settings put global transition_animation_scale 0")
    print("     adb shell settings put global animator_duration_scale 0")
    return False


def prompt_avd_config(defaults: dict) -> dict | None:
    """
    Show current defaults, let user override each field or accept all.
    Returns final config dict, or None if user cancels.
    """
    print()
    print("  Current configuration (press Enter to keep default):")
    print(f"  ┌{'─'*44}┐")
    print(f"  │  RAM        : {defaults['ram_mb']} MB{'':<20}│")
    print(f"  │  CPU cores  : {defaults['cpu_cores']}{'':<28}│")
    print(f"  │  Storage    : {defaults['storage_mb']} MB{'':<18}│")
    print(f"  │  Graphics   : {defaults['graphics']}{'':<25}│")
    print(f"  └{'─'*44}┘")
    print()

    cfg = dict(defaults)

    # RAM
    try:
        raw = input(f"  RAM in MB [{defaults['ram_mb']}] (0=back): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw in ("0", "b", "back"):
        return None
    if raw and raw.isdigit():
        cfg["ram_mb"] = int(raw)

    # CPU cores
    try:
        raw = input(f"  CPU cores [{defaults['cpu_cores']}] (0=back): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw in ("0", "b", "back"):
        return None
    if raw and raw.isdigit():
        cfg["cpu_cores"] = int(raw)

    # Storage
    try:
        raw = input(f"  Internal storage MB [{defaults['storage_mb']}] (0=back): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw in ("0", "b", "back"):
        return None
    if raw and raw.isdigit():
        cfg["storage_mb"] = int(raw)

    # Graphics
    try:
        raw = input(f"  Graphics [hardware/software/auto] [{defaults['graphics']}] (0=back): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return None
    if raw in ("0", "b", "back"):
        return None
    if raw in ("hardware", "software", "auto"):
        cfg["graphics"] = raw

    return cfg


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


def action_new_avd():
    """
    Wizard to create a new AVD.

    Jalur A — No system images found:
      Show install instructions (sdkmanager CLI + Android Studio SDK Manager).

    Jalur B — System images available:
      1. Pick system image
      2. Pick device profile
      3. Enter AVD name
      4. Review + customize hardware config (smart defaults)
      5. Run avdmanager create avd
      6. Offer to launch immediately → if launched, auto-disable animations after boot
    """
    print("\n  ── Create New AVD ────────────────────────────────────")

    # ── Prerequisite checks ──────────────────────────────────────────────────
    if not check_command("avdmanager"):
        print()
        print("  ✗ 'avdmanager' not found.")
        print("    Make sure Android Studio is installed and ANDROID_HOME is set:")
        print()
        print("    macOS  : export ANDROID_HOME=~/Library/Android/sdk")
        print("    Linux  : export ANDROID_HOME=~/Android/Sdk")
        print("    Windows: set ANDROID_HOME=%LOCALAPPDATA%\\Android\\Sdk")
        print()
        print("    Then add $ANDROID_HOME/cmdline-tools/latest/bin to your PATH.")
        return

    android_home = get_android_home()
    if not android_home:
        print()
        print("  ✗ ANDROID_HOME not found. Set it and try again:")
        print("    macOS/Linux : export ANDROID_HOME=~/Library/Android/sdk")
        print("    Windows     : set ANDROID_HOME=%LOCALAPPDATA%\\Android\\Sdk")
        return

    preferred_abi = detect_host_abi()
    print(f"\n  Host ABI detected: {preferred_abi}")

    # ── Scan system images ───────────────────────────────────────────────────
    print("  Scanning system images...", end="", flush=True)
    images = scan_system_images(android_home, preferred_abi)
    print(f" found {len(images)}.")

    # ── JALUR A: No system images → show install wizard ──────────────────────
    if not images:
        print()
        print("  ✗ No system images found in:")
        print(f"    {android_home}/system-images/")
        print()
        print("  ── Install System Image ──────────────────────────────")
        print()
        print("  Option 1 — Android Studio (recommended):")
        print("    Tools → SDK Manager → SDK Platforms")
        print("    Check the API level you want → Apply")
        print()
        print("  Option 2 — Command line (sdkmanager):")
        print()

        # Show recommended image based on detected ABI
        rec_image = f"\"system-images;android-34;google_apis;{preferred_abi}\""
        print(f"    # Install recommended (API 34, Google APIs, {preferred_abi}):")
        print(f"    sdkmanager {rec_image}")
        print()
        print("    # Or list all available images:")
        print("    sdkmanager --list | grep system-images")
        print()
        print("  Option 3 — Common images to install:")
        for api, tag in [("34", "google_apis"), ("33", "google_apis"), ("30", "google_apis")]:
            print(f"    sdkmanager \"system-images;android-{api};{tag};{preferred_abi}\"")
        print()
        print("  After installing, come back and press N again to create the AVD.")
        return

    # ── JALUR B: System images available → creation wizard ───────────────────

    # Step 1: Pick system image
    print()
    print("  Step 1 of 4 — Select system image")
    print("  (Use Google APIs for daily dev — fastest, no Play Store overhead)")
    print()

    img_labels = [img["label"] for img in images]
    selected_imgs = select_from_list(images, img_labels, "system image")
    if not selected_imgs:
        return
    chosen_image = selected_imgs[0]  # single select
    print(f"  ✓ Image: {chosen_image['label'].split('←')[0].strip()}")

    # Step 2: Pick device profile
    print()
    print("  Step 2 of 4 — Select device profile")
    print()

    dev_labels = [p[0] for p in DEVICE_PROFILES]
    selected_devs = select_from_list(DEVICE_PROFILES, dev_labels, "device profile")
    if not selected_devs:
        return
    chosen_dev = selected_devs[0]
    dev_display, dev_id, rec_ram = chosen_dev
    print(f"  ✓ Device: {dev_display.split('—')[0].strip()}")

    # Step 3: AVD name
    print()
    print("  Step 3 of 4 — AVD name")
    print("  (Letters, numbers, underscores and dashes only. No spaces.)")
    print()

    while True:
        try:
            avd_name = input("  AVD name (0=back): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Cancelled.")
            return
        if not avd_name or avd_name in ("0", "b", "back"):
            print("  Going back to menu.")
            return
        if not re.match(r'^[\w\-]+$', avd_name):
            print("  Invalid name. Use letters, numbers, _ or - only.\n")
            continue
        # Check duplicate
        existing = get_avd_list()
        if avd_name in existing:
            print(f"  AVD '{avd_name}' already exists. Choose a different name.\n")
            continue
        break

    print(f"  ✓ Name: {avd_name}")

    # Step 4: Hardware config with smart defaults
    print()
    print("  Step 4 of 4 — Hardware configuration")

    defaults = {
        "ram_mb":     rec_ram,
        "cpu_cores":  4,
        "storage_mb": 6144,
        "graphics":   "hardware",
    }
    config = prompt_avd_config(defaults)
    if config is None:
        print("  Going back to menu.")
        return

    # ── Summary before create ────────────────────────────────────────────────
    print()
    print("  ── Summary ───────────────────────────────────────────")
    print(f"  Name    : {avd_name}")
    print(f"  Image   : {chosen_image['path']}")
    print(f"  Device  : {dev_display.split('—')[0].strip()}")
    print(f"  RAM     : {config['ram_mb']} MB")
    print(f"  CPU     : {config['cpu_cores']} cores")
    print(f"  Storage : {config['storage_mb']} MB")
    print(f"  Graphics: {config['graphics']}")
    print()

    try:
        confirm = input("  Create AVD? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  Cancelled.")
        return
    if confirm == "n":
        print("  Cancelled.")
        return

    # ── Run avdmanager create avd ────────────────────────────────────────────
    print()
    print(f"  → Creating AVD '{avd_name}'...")

    cmd = [
        "avdmanager", "create", "avd",
        "--name",   avd_name,
        "--package", chosen_image["path"],
        "--device",  dev_id,
        "--force",
    ]

    try:
        # avdmanager sometimes asks "Do you wish to create a custom hardware profile? [no]"
        # pipe "no\n" to stdin to auto-answer
        proc = subprocess.run(
            cmd,
            input="no\n",
            capture_output=True,
            text=True,
            timeout=60
        )
        if proc.returncode != 0:
            print(f"  ✗ avdmanager error:\n{proc.stderr.strip()}")
            return
    except subprocess.TimeoutExpired:
        print("  ✗ Timeout creating AVD.")
        return
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return

    # ── Write hardware config overrides to AVD ini ────────────────────────────
    avd_dir = os.path.expanduser(f"~/.android/avd/{avd_name}.avd")
    config_file = os.path.join(avd_dir, "config.ini")
    if os.path.isfile(config_file):
        # Read existing config
        with open(config_file, "r") as f:
            lines = f.readlines()

        overrides = {
            "hw.ramSize":           str(config["ram_mb"]),
            "hw.cpu.ncore":         str(config["cpu_cores"]),
            "disk.dataPartition.size": f"{config['storage_mb']}M",
            "hw.gpu.enabled":       "yes" if config["graphics"] != "software" else "no",
            "hw.gpu.mode":          config["graphics"],
            "fastboot.chosenSnapshotFile": "",
            "fastboot.forceChosenSnapshotBoot": "no",
            "fastboot.forceColdBoot": "no",
            "fastboot.forceFastBoot": "yes",
        }

        # Update existing keys or append new ones
        existing_keys = {}
        new_lines = []
        for line in lines:
            if "=" in line:
                key = line.split("=")[0].strip()
                if key in overrides:
                    new_lines.append(f"{key} = {overrides[key]}\n")
                    existing_keys[key] = True
                    continue
            new_lines.append(line)

        # Append keys that didn't exist yet
        for key, val in overrides.items():
            if key not in existing_keys:
                new_lines.append(f"{key} = {val}\n")

        with open(config_file, "w") as f:
            f.writelines(new_lines)

    print(f"  ✓ AVD '{avd_name}' created successfully!")
    print()
    print("  Going back to menu. Press L to launch the new AVD.")
    print("  Animations will be disabled automatically after first boot.")


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
        print("  N - New AVD (create Android emulator)")
        print("  F - Refresh device list")
        print("  Q - Quit")
        print()

        try:
            choice = input("  Choose action [L/R/K/P/N/F/Q]: ").strip().upper()
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
        elif choice == "N":
            action_new_avd()
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
            print("\n  Invalid choice. Enter L, R, K, P, N, F, or Q.")

        if choice not in ("F",):
            input("\n  Press Enter to return to menu...")


if __name__ == "__main__":
    main()
