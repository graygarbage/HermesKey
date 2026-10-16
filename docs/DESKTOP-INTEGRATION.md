# Desktop integration

HermesKey is primarily a hotkey-driven tool, but the installer also ships a few desktop launchers for convenience.

## Installed launchers

- **HermesKey Control Center** — one place for status, diagnostics, config, logs, and service restart
- **HermesKey Status** — shows runtime and service status
- **HermesKey Doctor** — runs diagnostics and shows the report
- **HermesKey Logs** — shows runtime and service logs
- **HermesKey Config** — opens `~/.config/hermeskey/hermeskey.env`
- **HermesKey Settings (preview)** — a native PySide6 window shell with Speech, Input, Appearance, and System sections

These launchers are installed into:

```bash
~/.local/share/applications/
```

The control-center launcher uses `kdialog` on KDE when available and falls back to `zenity` or plain terminal output. It can also open the settings preview. The settings window requires the system's PySide6 QtWidgets package (already used by the overlay) and can be launched with `~/.local/bin/hermeskey-settings.py`.

The settings shell is deliberately **read-only**: Save and Apply are disabled until config load/save wiring is implemented in #5. Cancel or closing the window makes no changes. Continue using the Config launcher to edit settings for now.

## Why not a big GUI app?

HermesKey remains built around a fast hotkey loop. The small settings shell is a foundation for future controls, not a requirement for dictation.

## Hotkey binding

For actual dictation, bind your shortcut directly to:

```bash
~/.local/bin/hermeskey
```

See [HOTKEYS.md](HOTKEYS.md) for the KDE shortcut flow.
