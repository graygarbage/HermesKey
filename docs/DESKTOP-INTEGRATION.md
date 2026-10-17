# Desktop integration

HermesKey is primarily a hotkey-driven tool, but the installer also ships a few desktop launchers for convenience.

## Installed launchers

- **HermesKey Control Center** — one place for status, diagnostics, config, logs, and service restart
- **HermesKey Status** — shows runtime and service status
- **HermesKey Doctor** — runs diagnostics and shows the report
- **HermesKey Logs** — shows runtime and service logs
- **HermesKey Config** — opens `~/.config/hermeskey/hermeskey.env`
- **HermesKey Settings (preview)** — configure common settings and view live user-service status, restart services, inspect logs, or run Doctor

These launchers are installed into:

```bash
~/.local/share/applications/
```

The control-center launcher uses `kdialog` on KDE when available and falls back to `zenity` or plain terminal output. It can also open the settings preview. The settings window requires the system's PySide6 QtWidgets package (already used by the overlay) and can be launched with `~/.local/bin/hermeskey-settings.py`.

The settings preview edits **only `MODEL`, `STT_LANG`, `RECORD_SOURCE`, `INSERT_MODE`, `COPY_TO_CLIPBOARD`, `FOCUS_SAFE_MODE`, `OVERLAY_ENABLED`, and `SOUND_ENABLED`** in `~/.config/hermeskey/hermeskey.env`, the path the user systemd service reads. Save writes and closes; Apply writes and stays open; Cancel discards. Closing with unsaved changes asks first. The GUI preserves other settings and comments, refuses unsupported/duplicate managed assignments and external file changes, and validates before writing. After a model/language save it offers a speech-service restart; microphone and behavior-only changes take effect on the next hotkey invocation without restarting the service. Other settings still require the Config launcher. Alternate `XDG_CONFIG_HOME` paths are not yet used by the systemd unit, so the GUI warns and targets the canonical path.

The System page distinguishes systemd's *active* state from a speech model answering on its socket or a typing socket accepting connections. It refreshes while visible, and a successful `systemctl` restart is shown as **requested**, not immediately ready. Restart buttons confirm interruption risk and require you to save or discard pending edits first. Doctor and the bounded log excerpt open locally in a read-only viewer; they are not uploaded or automatically copied. Review logs before sharing, even though HermesKey's own speech-server logging is diagnostic-only.

## Why not a big GUI app?

HermesKey remains built around a fast hotkey loop. The small settings shell is a foundation for future controls, not a requirement for dictation.

## Hotkey binding

For actual dictation, bind your shortcut directly to:

```bash
~/.local/bin/hermeskey
```

See [HOTKEYS.md](HOTKEYS.md) for the KDE shortcut flow.
