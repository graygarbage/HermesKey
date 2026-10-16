# Configuration

HermesKey reads configuration from:

```bash
~/.config/hermeskey/hermeskey.env
```

The installer copies a starter file there on first install. After changing it, run `hermeskey-doctor --config-only` (or `hermeskey-doctor`) to check model/language settings, insertion modes, flags, and numeric options before restarting the services. Invalid settings cause a nonzero exit status; unknown model aliases and custom Hugging Face IDs/paths are warnings because they cannot be verified offline. A valid model name is not a guarantee that its download will succeed.

## Core settings

```bash
MODEL=medium
STT_LANG=en
RECORD_SOURCE=default
```

- `MODEL`: any supported `faster-whisper` model name
- `STT_LANG`: spoken language code supported by faster-whisper; set empty for auto-detect (e.g. `en`, `zh`, `haw` or `yue`)
- `RECORD_SOURCE`: `default` follows the desktop's default input; to pin a specific mic, use a name from `pactl list short sources`

## Insertion behavior

```bash
INSERT_MODE=type
COPY_TO_CLIPBOARD=1
TYPE_BACKEND=auto
```

- `INSERT_MODE=type` types into the active app
- `INSERT_MODE=clipboard` only copies to clipboard
- `COPY_TO_CLIPBOARD=1` keeps a backup copy even when typing succeeds
- `TYPE_BACKEND` may be `auto`, `ydotool`, `wtype`, or `xdotool`

```bash
TYPE_KEY_DELAY=1
TYPE_KEY_HOLD=5
```

- typing speed in milliseconds: delay between keys, and how long each key is held
- ydotool's own default hold is 20 ms per key, so long dictations typed slowly; raise these if an app drops characters
- `TYPE_KEY_HOLD` is only passed to ydotool 1.0 and newer

## Overlay and sound

```bash
OVERLAY_ENABLED=1
SOUND_ENABLED=1
START_TONE_HZ=660
STOP_TONE_HZ=520
TONE_DURATION=0.035
TONE_VOLUME=0.20
```

## Focus safety

```bash
FOCUS_SAFE_MODE=0
```

If enabled, HermesKey checks that focus is still on the window you started recording in before inserting. If focus moved, the transcript goes to the clipboard instead.

This and the paste fallback below need active window detection (KDE Plasma). HermesKey uses `kdotool` if it is installed, and otherwise a small built-in KWin script, which needs `python3-dbus` and `python3-gobject` (usually already installed with Plasma). `hermeskey-doctor` shows which method is in use. Without either, text is always typed.

## Paste fallback

```bash
TERMINAL_APPS=org.wezfurlong.wezterm,org.kde.konsole,kitty,Alacritty,ghostty,foot,gnome-terminal,tilix,xfce4-terminal
PASTE_FOR_APPS=$TERMINAL_APPS
PASTE_SHORTCUT=auto
```

- `PASTE_FOR_APPS` is a comma-separated pattern list
- `PASTE_SHORTCUT=auto` picks `Ctrl+Shift+V` for terminal-like apps and `Ctrl+V` elsewhere
- the check uses the window that is focused when the text is inserted
- pasting needs the clipboard, so with `COPY_TO_CLIPBOARD=0` text is typed instead

## Runtime overrides

All settings can also be overridden via environment variables at launch time.
