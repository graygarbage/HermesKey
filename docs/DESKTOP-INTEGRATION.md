# Desktop integration

HermesKey is primarily hotkey-driven. KDE's app menu has **one visible entry: HermesKey Settings**. The Settings window handles common configuration, service status, restarts, logs, Doctor and opening the advanced config file.

## Desktop compatibility

The old Control Center, Status, Doctor, Logs and Config desktop IDs are still installed with `NoDisplay=true`. They remain launchable from existing pinned shortcuts but do not clutter the app menu. `hermeskey-control-center` now opens the Settings window; the other CLI helper commands remain available for scripts and troubleshooting. Reinstalling upgrades previously visible entries to hidden ones without removing their desktop IDs. These files live in:

```bash
~/.local/share/applications/
```

Settings requires the system's PySide6 QtWidgets package (already used by the overlay) and can also be launched with `~/.local/bin/hermeskey-settings.py`. The AppStream launchable points to the visible Settings desktop ID.

The Settings window edits **only `MODEL`, `STT_LANG`, `HERMESKEY_OFFLINE`, `RECORD_SOURCE`, `INSERT_MODE`, `COPY_TO_CLIPBOARD`, `FOCUS_SAFE_MODE`, `OVERLAY_ENABLED`, and `SOUND_ENABLED`** in `~/.config/hermeskey/hermeskey.env`, the path the user systemd service reads. Save writes and closes; Apply writes and stays open; Cancel discards. Closing with unsaved changes asks first. The GUI preserves other settings and comments, refuses unsupported/duplicate managed assignments and external file changes, and validates before writing. After a model/language/offline save it offers a speech-service restart; microphone and behavior-only changes take effect on the next hotkey invocation without restarting the service. For other settings, use **Open advanced config file** on the System page. Save or discard any unsaved GUI changes before opening it; reopen Settings after editing the file externally. All installed entry points use the canonical path regardless of `XDG_CONFIG_HOME`; the installer privately archives older custom-XDG configs after migrating them. `HERMESKEY_CONFIG` remains a per-command CLI override, not a GUI/service override.

The System page distinguishes systemd's *active* state from a speech model answering on its socket or a typing socket accepting connections. It refreshes while visible, and a successful `systemctl` restart is shown as **requested**, not immediately ready. Restart buttons confirm interruption risk and require you to save or discard pending edits first. Doctor and the bounded log excerpt open locally in a read-only viewer; they are not uploaded or automatically copied. Review logs before sharing, even though HermesKey's own speech-server logging is diagnostic-only.

## Why not a big GUI app?

HermesKey remains built around a fast hotkey loop. The small settings shell is a foundation for future controls, not a requirement for dictation.

## Hotkey binding

For actual dictation, bind your shortcut directly to:

```bash
~/.local/bin/hermeskey
```

See [HOTKEYS.md](HOTKEYS.md) for the KDE shortcut flow.
