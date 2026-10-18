# Installation

## Recommended target

HermesKey is currently best on KDE Plasma Wayland with PipeWire.

## System packages

### Fedora / Nobara

```bash
sudo dnf install \
  ffmpeg \
  wl-clipboard \
  libnotify \
  ydotool \
  python3 \
  python3-pip \
  python3-virtualenv \
  python3-pyside6 \
  qt6-qtwayland \
  plasma-workspace \
  pulseaudio-utils
```

### Arch / EndeavourOS

```bash
sudo pacman -S --needed \
  ffmpeg \
  wl-clipboard \
  libnotify \
  ydotool \
  python \
  python-pip \
  python-virtualenv \
  pyside6 \
  qt6-wayland \
  plasma-workspace \
  libpulse
```

### Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y \
  ffmpeg \
  wl-clipboard \
  libnotify-bin \
  ydotool \
  python3 \
  python3-pip \
  python3-venv \
  python3-pyside6.qtcore \
  python3-pyside6.qtgui \
  python3-pyside6.qtwidgets \
  qt6-wayland \
  pulseaudio-utils
```

Notes:

- `qdbus` normally comes from the KDE/Qt desktop stack.
- Optional: `kdotool` for active window detection. Without it, HermesKey uses a built-in KWin script that needs `python3-dbus` and `python3-gobject`.
- `paplay` is typically provided by `pulseaudio-utils`.
- Package names vary slightly across distros; if a package name differs, install the nearest equivalent.

## Install HermesKey

### One-line installer

Run this from your logged-in graphical session, **without sudo**. Bootstrap will:

1. Check bootstrap tools, download the release, and check system commands (`ffmpeg`, `wl-copy`, `notify-send`, `ydotool`, `ydotoold`, `pactl`), system Python's PySide6 overlay, the user systemd manager, and `/dev/uinput` access. Missing system packages or seat access stop the install with a diagnostic and a link to this guide; bootstrap does not install distro packages or change device permissions.
2. Create/reuse `~/venvs/stt` and install Python dependencies (unless `--skip-venv` is specified). If an existing config points `PYTHON_STT` to a deleted venv or one without `faster-whisper`, stop immediately with an actionable error rather than waiting for a service that will never start.
3. Refuse to upgrade while a recording is active. Use one canonical `~/.config/hermeskey/hermeskey.env` file for the app and services, even if your `XDG_CONFIG_HOME` is customized. An older custom-XDG config is copied privately and archived in its original directory (suffix `.pre-hermeskey-xdg-migration`); conflicting files stop installation rather than being overwritten. Review the [config-path policy](CONFIGURATION.md) before upgrading a customized setup. Copy the app and enable/restart the user services. The speech server downloads the configured model (`medium` by default) from Hugging Face on first use if it is not cached; public models do not require an HF token. Online startup may also check model metadata with a cached model. After acquiring a model, Settings → Speech can enable **Strict offline speech model** and restart the service; see [privacy and network behavior](PRIVACY.md).
4. Wait up to 10 minutes for the model and its socket. Transcribe a bundled, synthetic speech recording and check its result, then verify `ydotoold` is active. No microphone audio is recorded and nothing is typed into the active app by this test.

**Clipboard privacy:** typing mode defaults to `COPY_TO_CLIPBOARD=1` for reliable backups and Unicode paste. Dictated text can persist in KDE clipboard history or another clipboard-sync tool even after insertion. In Settings → Input, select **Privacy-first typing** to turn off new backups without changing the existing clipboard history; `ydotool` cannot insert non-ASCII text in that mode. Clipboard-only mode always copies. See [configuration](CONFIGURATION.md) and [privacy](PRIVACY.md).

Bootstrap exits with an error if validation fails **after** installing files; run `hermeskey-doctor` and `journalctl --user -u hermeskey.service -n 80 --no-pager` to diagnose it. A real microphone and application typing test remain necessary. Slow model downloads can use `HERMESKEY_MODEL_TIMEOUT=1200`; slow inference can use `HERMESKEY_SMOKE_TIMEOUT=300` (both in seconds). If you configured a nondefault `SOCK`, set `HERMESKEY_SMOKE_SOCKET` to that socket path. The sample WAV in `tests/smoke.wav` is synthesized with eSpeak NG and bundled in the release; customers do not need eSpeak installed. Do not pass `--skip-venv` unless your configured Python already has `requirements.txt` installed.

```bash
curl -fsSL https://raw.githubusercontent.com/graygarbage/HermesKey/main/scripts/bootstrap.sh | bash
```

The standard command selects the latest published release. If GitHub's release API is unavailable or the archive cannot be resolved, bootstrap **stops without installing** rather than silently substituting untagged `main` code. Retry later, or consciously opt into the current `main` branch instead:

```bash
curl -fsSL https://raw.githubusercontent.com/graygarbage/HermesKey/main/scripts/bootstrap.sh | bash -s -- --main
```

To test an unmerged PR with the same bootstrap checks and smoke test, check it out locally and run `bash scripts/bootstrap.sh --local` from the checkout. The normal `curl` command does **not** use the checkout; it downloads the latest published release. `--local` only skips the download/extraction step. If you previously installed HermesKey, confirm `~/.config/hermeskey/hermeskey.env` does not point `PYTHON_STT` at a removed venv; the installer preserves existing configuration.

To skip Python environment setup because you are managing it yourself:

```bash
curl -fsSL https://raw.githubusercontent.com/graygarbage/HermesKey/main/scripts/bootstrap.sh | bash -s -- --skip-venv
```

### Manual install

```bash
bash scripts/preflight.sh
python3 -m venv ~/venvs/stt
source ~/venvs/stt/bin/activate
pip install -U pip
pip install -r requirements.txt
./install.sh
python3 scripts/verify-install.py
```

Unlike bootstrap, `./install.sh` on its own only copies and starts the app; it does not install Python requirements or wait for the model.

## Bind the hotkey

Set your desktop shortcut target to:

```bash
~/.local/bin/hermeskey
```

For a KDE walkthrough, see [HOTKEYS.md](HOTKEYS.md).

## Verify services

```bash
systemctl --user status hermeskey.service
systemctl --user status hermeskey-ydotoold.service
```

## Desktop launchers

The installer adds one visible app-menu entry, **HermesKey Settings**. Its System page includes status, restart, logs, Doctor, and an advanced config-file action. Older desktop IDs are installed hidden for pinned-shortcut compatibility; CLI tools remain available. Upgrading an older install overwrites its visible helper launchers with hidden versions.

For actual dictation, keep binding your hotkey to:

```bash
~/.local/bin/hermeskey
```

## Run the doctor

```bash
hermeskey-doctor
```
