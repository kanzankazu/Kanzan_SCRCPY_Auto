# Contributing to Kanzan SCRCPY Auto

Thanks for your interest in contributing! This tool helps automate scrcpy device mirroring across macOS, Linux, and Windows. Contributions that improve usability, add device support, or fix bugs are very welcome.

---

## What You Can Contribute

- **Fix bugs** — incorrect device detection, broken launch logic, or edge cases
- **Improve cross-platform support** — macOS, Linux, Windows compatibility
- **Add new features** — new scrcpy options, device filters, UI improvements
- **Improve documentation** — clearer README, better usage examples
- **Report issues** — broken behavior, missing scrcpy flags, ADB edge cases

---

## Ground Rules

- Keep scripts simple and readable — **comment non-obvious logic**
- Test on the platform you're changing (macOS, Linux, or Windows)
- One pull request per concern — don't mix unrelated changes
- English for code and comments; discussion in any language is fine

---

## Setup for Development

```bash
# Fork & clone
git clone https://github.com/<your-username>/Kanzan_SCRCPY_Auto.git
cd Kanzan_SCRCPY_Auto

# Prerequisites
# - Python 3.8+
# - scrcpy installed (https://github.com/Genymobile/scrcpy)
# - ADB in PATH

# macOS/Linux — run directly
chmod +x scrcpy.sh
./scrcpy.sh

# macOS — double-click launcher
open scrcpy.command

# Windows — double-click or run
scrcpy.bat

# Python launcher
python scrcpy_launcher.py
```

---

## Workflow

1. Fork this repository
2. Create a branch: `git checkout -b fix/device-detection` or `feat/add-wireless-adb`
3. Make your changes
4. Test on your platform
5. Commit with a clear message (see below)
6. Push and open a Pull Request

---

## Commit Message Format

```
type: short description

Examples:
fix: handle missing adb in PATH on Windows
feat: add wireless ADB auto-connect option
docs: update README scrcpy installation steps
chore: clean up unused variables in launcher
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`

---

## Pull Request Checklist

Before submitting, please make sure:

- [ ] Script runs without errors on your platform
- [ ] No hardcoded paths or personal credentials
- [ ] Logic is commented where non-obvious
- [ ] PR description explains what changed and why

---

## Reporting Issues

Please include:
- What you expected to happen
- What actually happened
- Steps to reproduce
- OS and Python version (`python --version`)
- scrcpy version (`scrcpy --version`)
- ADB version (`adb version`)

---

## Questions?

Open a GitHub Discussion or reach out via email: **kanzankazu46@gmail.com**
