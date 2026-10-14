# Troubleshooting

## No typing appears in the active app

Check the user daemon:

```bash
systemctl --user status hermeskey-ydotoold.service
ls -l /run/user/$UID/.ydotool_socket
```

Test typing directly:

```bash
ydotool type "hello"
```

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
