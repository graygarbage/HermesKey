<p align="center">
  <img src="assets/hermeskey-banner.svg" alt="HermesKey: push-to-talk speech-to-text for Linux Wayland desktops" width="100%">
</p>

<p align="center">
  <a href="https://github.com/graygarbage/HermesKey/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/graygarbage/HermesKey/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://github.com/graygarbage/HermesKey/releases"><img alt="Release" src="https://img.shields.io/github/v/release/graygarbage/HermesKey?display_name=tag"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <img alt="Platform" src="https://img.shields.io/badge/platform-Linux%20Wayland-0f172a">
  <img alt="Desktop" src="https://img.shields.io/badge/tuned%20for-KDE%20Plasma-1d4ed8">
</p>

HermesKey is a local-first dictation tool built for a simple loop:

1. press one hotkey
2. speak
3. press the same hotkey again
4. keep moving

It keeps `faster-whisper` warm in a background service and sends the transcript back into the app you were already using.

## Install in 60 seconds

### 1. Install Linux packages

| Distro | Command |
| --- | --- |
| Fedora / Nobara | `sudo dnf install ffmpeg wl-clipboard libnotify ydotool python3 python3-pip python3-virtualenv python3-pyside6 qt6-qtwayland plasma-workspace pulseaudio-utils` |
| Arch / EndeavourOS | `sudo pacman -S --needed ffmpeg wl-clipboard libnotify ydotool python python-pip python-virtualenv pyside6 qt6-wayland plasma-workspace libpulse` |
| Ubuntu / Debian | `sudo apt-get update && sudo apt-get install -y ffmpeg wl-clipboard libnotify-bin ydotool python3 python3-pip python3-venv python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets qt6-wayland pulseaudio-utils` |

### 2. Run the installer

```bash
curl -fsSL https://raw.githubusercontent.com/graygarbage/HermesKey/main/scripts/bootstrap.sh | bash
```

Install from `main` instead of the latest tagged release:

```bash
curl -fsSL https://raw.githubusercontent.com/graygarbage/HermesKey/main/scripts/bootstrap.sh | bash -s -- --main
```

### 3. Bind your hotkey

Bind your desktop shortcut to:

```bash
~/.local/bin/hermeskey
```

### 4. Verify the setup

```bash
hermeskey --status
hermeskey-doctor
```

## Why HermesKey

- one-key start/stop workflow
- prewarmed `faster-whisper` for lower latency
- direct typing into the active app
- clipboard backup as a safety net
- paste fallback for terminals and terminal-like apps
- click-through overlay for `Recording` and `Transcribing`
- soft audio cues instead of harsh beeps
- Wayland-friendly typing through a user-owned `ydotoold` service
- desktop helpers for status, diagnostics, logs, and config access

## CLI

```bash
hermeskey --help
hermeskey --version
hermeskey --status
hermeskey --doctor
```

## Desktop integration

The installer also adds local desktop launchers for:

- HermesKey Control Center
- HermesKey Status
- HermesKey Doctor
- HermesKey Logs
- HermesKey Config
- HermesKey Settings (preview; edit model and language; other controls coming later)

For actual dictation, keep binding your hotkey directly to:

```bash
~/.local/bin/hermeskey
```

## Current target environment

HermesKey is currently tuned primarily for:

- Linux
- Wayland
- KDE Plasma
- PipeWire / PulseAudio-compatible audio

## Deep dive docs

Detailed documentation lives here:

- [docs/DEEP-DIVE.md](docs/DEEP-DIVE.md)
- [docs/INSTALL.md](docs/INSTALL.md)
- [docs/HOTKEYS.md](docs/HOTKEYS.md)
- [docs/DESKTOP-INTEGRATION.md](docs/DESKTOP-INTEGRATION.md)
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/PACKAGING.md](docs/PACKAGING.md)
- [docs/RELEASING.md](docs/RELEASING.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)

## Development

```bash
make check
make package
```

Cut a release tag:

```bash
./scripts/release.sh
```

## Contributing

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)
- [SUPPORT.md](SUPPORT.md)

## License

MIT — see [LICENSE](LICENSE).
