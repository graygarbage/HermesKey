# Troubleshooting

## No typing appears in the active app

Check the user daemon:

```bash
systemctl --user status hermeskey-ydotoold.service
ls -l /run/user/$UID/.ydotool_socket
```

Test typing directly (focus a safe text field first):

```bash
YDOTOOL_SOCKET="/run/user/$UID/.ydotool_socket" ydotool type "hello"
```

### `ydotoold` says `failed to open uinput device: Permission denied`

`ydotoold` needs read/write access to `/dev/uinput`, even though its socket is
owned by your user. On systems using logind's `uaccess` ACL (including Nobara),
access may only appear after the graphical session becomes active. HermesKey's
service retries every 10 seconds so it can start after login; check with:

```bash
hermeskey-doctor
ls -l /dev/uinput
getfacl /dev/uinput
loginctl show-session "$XDG_SESSION_ID" -p Active -p Seat
systemctl --user status hermeskey-ydotoold.service
```

If the ACL now grants your user access but the service was stopped by an older
version's start limit, update HermesKey and run
`systemctl --user reset-failed hermeskey-ydotoold.service` followed by
`systemctl --user restart hermeskey-ydotoold.service`.

If access is still denied in an active graphical session, check that your
system has a `/dev/uinput` device and a distro udev rule tagging it `uaccess`.
Configure device access through your distro's udev/logind setup; do **not**
run the HermesKey user service as root or use `chmod 666 /dev/uinput` (that
would allow every local user to inject input).

### Accents, Chinese, or other Unicode text disappears when typing

`ydotool type` sends keyboard events, not Unicode text. It can report success
while dropping non-ASCII characters. With `COPY_TO_CLIPBOARD=1` (the default),
HermesKey copies a backup and uses the active app's paste shortcut for Unicode.
If the app cannot be identified or the paste shortcut fails, paste the backup
manually (`Ctrl+Shift+V` in most terminals, `Ctrl+V` in most GUI editors).
Alternatively set `INSERT_MODE=clipboard` for explicit copy-only behavior.
With `COPY_TO_CLIPBOARD=0` in type mode, HermesKey will warn but **will not
silently modify the clipboard** or attempt unsupported Unicode typing; enable
clipboard backup or clipboard-only mode if you need to insert Unicode text.
The model's language support and installed fonts are separate questions.
See [issue #54](https://github.com/graygarbage/HermesKey/issues/54).

## Transcription fails

Check the prewarmed server:

```bash
systemctl --user status hermeskey.service
journalctl --user -u hermeskey.service -n 100 --no-pager
```

And the local runtime log:

```bash
tail -n 100 ~/.local/state/hermeskey/hermeskey.log
```

Doctor shows service readiness but intentionally **omits raw service status and
journal snippets**: they can contain third-party request URLs, process arguments,
device names or local paths. The hotkey's local log records timestamps and fixed
status/failure categories, not transcripts, audio sizes, app IDs, window UUIDs,
device identifiers, user-configured backend names or runtime paths. It rotates at
256 KiB and retains at most one previous 256 KiB file (`hermeskey.log.1`);
previously created log files and journal history are not retroactively cleaned.
Errors from recorder/typing helpers and raw server responses are not appended to
the hotkey log. The speech service forwards its own allowlisted Python diagnostic
events and suppresses third-party Python logging by default. **Direct output from
systemd, native libraries or other programs may still appear in the journal**;
HermesKey does not control journald retention. Inspect all logs locally and redact
before sharing. To remove the hotkey's own local log history, delete
`~/.local/state/hermeskey/hermeskey.log` and `.log.1` on your machine (or use
your configured `LOG` path); the next hotkey use recreates the current log.
Never post audio, transcripts, tokens, window titles, device names, personal
paths or raw journals in a public issue. For a security-sensitive problem,
follow [SECURITY.md](../SECURITY.md); if private reporting is unavailable,
request a private contact channel without posting details publicly. To prevent
model metadata requests on restart, use a preloaded model and opt-in strict
offline mode as described in [PRIVACY.md](PRIVACY.md).

## No audio captured

Check if the configured recording source exists and test recording manually:

```bash
# Check if configured source exists
pactl list short sources | grep -i "$RECORD_SOURCE"

# List all available sources
pactl list short sources

# Test recording manually (record 5 seconds to test.wav)
ffmpeg -f pulse -i "$RECORD_SOURCE" -t 5 test.wav
```

## The wrong microphone is used

Find your microphone's exact source name and update the configuration:

```bash
# List all sources with details
pactl list sources | grep -A 10 "name"

# Or view a compact list
pactl list short sources
```

Then set `RECORD_SOURCE` in `~/.config/hermeskey/hermeskey.env`:

```bash
# Edit config
nano ~/.config/hermeskey/hermeskey.env
# Set RECORD_SOURCE=exact-source-name
```

## Permission denied / audio access issues

Check PulseAudio permissions and active audio inputs:

```bash
# Check active PulseAudio inputs
pactl list sink-inputs
```


## The overlay is distracting

Disable it:

```bash
OVERLAY_ENABLED=0
```

Restart your hotkey workflow after saving the config.
