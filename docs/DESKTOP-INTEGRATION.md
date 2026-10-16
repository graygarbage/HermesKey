# Desktop integration

HermesKey is primarily a hotkey-driven tool, but the installer also ships a few desktop launchers for convenience.

## Installed launchers

- **HermesKey Control Center** — one place for status, diagnostics, config, logs, and service restart
- **HermesKey Status** — shows runtime and service status
- **HermesKey Doctor** — runs diagnostics and shows the report
- **HermesKey Logs** — shows runtime and service logs
- **HermesKey Config** — opens `~/.config/hermeskey/hermeskey.env`
- **HermesKey Settings (preview)** — edit the speech model and language in a native PySide6 window; other sections are placeholders

These launchers are installed into:

```bash
~/.local/share/applications/
```

The control-center launcher uses `kdialog` on KDE when available and falls back to `zenity` or plain terminal output. It can also open the settings preview. The settings window requires the system's PySide6 QtWidgets package (already used by the overlay) and can be launched with `~/.local/bin/hermeskey-settings.py`.

The settings preview edits **only `MODEL` and `STT_LANG`** in `~/.config/hermeskey/hermeskey.env`, the path the user systemd service reads. Save writes and closes; Apply writes and stays open; Cancel discards. Closing with unsaved changes asks first. The GUI preserves other settings and comments, refuses unsupported/duplicate managed assignments and external file changes, and validates before writing. After a save it offers a speech-service restart; declining leaves saved changes pending until you restart the service. Other settings still require the Config launcher; richer controls are tracked in #6–#8. Alternate `XDG_CONFIG_HOME` paths are not yet used by the systemd unit, so the GUI warns and targets the canonical path.

## Why not a big GUI app?

HermesKey remains built around a fast hotkey loop. The small settings shell is a foundation for future controls, not a requirement for dictation.

## Hotkey binding

For actual dictation, bind your shortcut directly to:

```bash
~/.local/bin/hermeskey
```

See [HOTKEYS.md](HOTKEYS.md) for the KDE shortcut flow.
