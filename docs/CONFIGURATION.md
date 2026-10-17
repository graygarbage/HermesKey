# Configuration

HermesKey reads configuration from:

```bash
~/.config/hermeskey/hermeskey.env
```

The installer copies a starter file there on first install. The Settings GUI can load and save `MODEL`, `STT_LANG`, `RECORD_SOURCE`, `INSERT_MODE`, `COPY_TO_CLIPBOARD`, `FOCUS_SAFE_MODE`, `OVERLAY_ENABLED`, and `SOUND_ENABLED`; it leaves other lines, comments, and unknown settings untouched. It supports simple literal model IDs/paths without spaces or shell syntax. Configurations with duplicate or complex `MODEL` / `STT_LANG` assignments must be edited manually. Saves are validated, atomic, and made owner-only (mode `0600`); if the file changed since opening Settings, reload instead of overwriting someone else's edit. No backups or values are written to logs. For other fields, use **Open advanced config file** on the Settings System page.

After changing settings, run `hermeskey-doctor --config-only` (or `hermeskey-doctor`) to check model/language settings, insertion modes, flags, and numeric options before restarting the services. Invalid settings cause a nonzero exit status; unknown model aliases and custom Hugging Face IDs/paths are warnings because they cannot be verified offline. A valid model name is not a guarantee that its download will succeed. `MODEL` and `STT_LANG` changes need a restart of `hermeskey.service`, which the GUI offers after saving but never performs without permission. The GUI targets `~/.config/hermeskey/hermeskey.env` even if `XDG_CONFIG_HOME` or `HERMESKEY_CONFIG` is set, because the systemd service currently hard-codes that path.

## Core settings

```bash
MODEL=medium
STT_LANG=en
RECORD_SOURCE=default
```

- `MODEL`: choose a common preset or enter a custom ID/path. An existing custom model stays selected and is not replaced when you save unrelated settings. Choosing a model does not download it; loading/downloading begins when you explicitly restart the speech service.
- `STT_LANG`: choose the **language you speak**, or Auto-detect (saves an empty value); enter another Whisper language code if needed. For example, if you speak English, select English or Auto-detect, not French as an output language. HermesKey transcribes speech; this option does not translate into the chosen language. Existing custom codes stay visible (e.g. `en`, `zh`, `haw` or `yue`).
- `RECORD_SOURCE`: `default` follows the desktop's default input; the Settings microphone picker displays friendly descriptions and saves the source's internal name (not its transient numeric index). Monitor sources are hidden unless requested. An unplugged saved device stays selected and is shown as unavailable. Changing only the microphone does not restart the speech service; the next recording uses the new source.

## Insertion behavior

```bash
INSERT_MODE=type
COPY_TO_CLIPBOARD=1
TYPE_BACKEND=auto
```

- `INSERT_MODE=type` types into the active app
- `INSERT_MODE=clipboard` only copies to clipboard
- `COPY_TO_CLIPBOARD=1` allows clipboard backup and paste. On Wayland, `ydotool type` can silently drop non-ASCII characters even with exit status 0; HermesKey therefore sends a paste shortcut for non-ASCII transcripts when the active app is identifiable. If the app is unknown or the shortcut fails, the transcript stays on the clipboard for manual paste. With `COPY_TO_CLIPBOARD=0` in type mode, HermesKey will **not** silently change your clipboard: unsupported Unicode or other typing failures produce an explicit warning without inserting or copying text. Clipboard-only mode always copies even when the backup option is disabled; the GUI preserves your backup preference when you return to typing mode.
- `TYPE_BACKEND` may be `auto`, `ydotool`, `wtype`, or `xdotool`. Direct typing sends text through the backend's standard input, not process arguments. If an older `ydotool` lacks stdin (`--file=-`) support, HermesKey refuses unsafe typing: a backup remains available for manual paste only when `COPY_TO_CLIPBOARD=1`; otherwise it does not insert or copy the text. The ydotool socket must be owned by your user and live directly in your private `XDG_RUNTIME_DIR` (or `/run/user/$UID` when unset); even explicit `YDOTOOL_SOCKET_PATH` overrides outside this directory are refused. HermesKey never falls back to a shared `/tmp` typing socket.

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

If enabled, HermesKey checks that focus is still on the window you started recording in before inserting. If focus moved, the transcript goes to the clipboard **only when `COPY_TO_CLIPBOARD=1`**; otherwise a notification explains why nothing was inserted or copied.

This and the paste fallback below need active window detection (KDE Plasma). HermesKey uses `kdotool` if it is installed, and otherwise a small built-in KWin script, which needs `python3-dbus` and `python3-gobject` (usually already installed with Plasma). `hermeskey-doctor` shows which method is in use. Without either, text is always typed.

Behavior controls (`INSERT_MODE`, `COPY_TO_CLIPBOARD`, `FOCUS_SAFE_MODE`, `OVERLAY_ENABLED`, `SOUND_ENABLED`) are read on the next hotkey invocation; changing only those settings does **not** restart the speech model. If window detection is unavailable, focus safety cannot guarantee protection; run `hermeskey-doctor` to confirm support. Tone timing, typing speed, and paste patterns still require manual config editing.

## Paste fallback

```bash
TERMINAL_APPS=org.wezfurlong.wezterm,org.kde.konsole,kitty,Alacritty,ghostty,foot,gnome-terminal,tilix,xfce4-terminal
PASTE_FOR_APPS=$TERMINAL_APPS
PASTE_SHORTCUT=auto
```

- `PASTE_FOR_APPS` is a comma-separated pattern list
- `PASTE_SHORTCUT=auto` picks `Ctrl+Shift+V` for terminal-like apps and `Ctrl+V` elsewhere
- the check uses the window that is focused when the text is inserted
- pasting needs the clipboard; with `COPY_TO_CLIPBOARD=0`, printable ASCII is typed instead, while non-ASCII with ydotool is not inserted and triggers a notification. Paste is never attempted if the configured focus-safety check detects that the active window changed.

## Runtime overrides

All settings can also be overridden via environment variables at launch time.
