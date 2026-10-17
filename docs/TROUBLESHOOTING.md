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
journal snippets**: they can include third-party network request URLs, process
arguments, device names or local paths. The speech server now forwards only its
own allowlisted diagnostic events from Python logging; it suppresses third-party
library logging in the service by default. Existing journal history and output
written directly by other programs may still contain private metadata. Inspect
logs only on your machine, and carefully redact them before any voluntary sharing.
Never post audio, transcripts, tokens, window titles, device names or personal
paths in a public issue. For a security-sensitive problem, follow
[SECURITY.md](../SECURITY.md); if private reporting is unavailable, request a
private contact channel without posting details publicly. This logging change
does **not** prevent a
model-library metadata request on restart; offline operation is tracked in
[issue #65](https://github.com/graygarbage/HermesKey/issues/65).

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
