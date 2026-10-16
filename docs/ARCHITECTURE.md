# Architecture

HermesKey has three runtime layers:

## 1. Hotkey entrypoint

`bin/hermeskey`

Responsibilities:

- toggle start/stop recording
- play soft audio cues
- show/hide overlay
- capture audio with `ffmpeg`
- send audio to the local STT server
- copy text to clipboard
- type or paste into the active app

This layer is intentionally a shell script because it is easy to debug in a live desktop environment.

Hotkey invocations are serialized with a nonblocking per-user `flock` lock.
The lock covers starting/stopping the recorder, transcription, and inserting
the result. A press while one of those transitions is in progress is ignored
(with a notification); it is not queued, since a queued press could immediately
stop a recording that just started. Once recording has started, the lock is
released so the next press can stop it. The recorder and speech server do not
inherit the lock.

## 2. Speech server

`bin/hermeskey-server.py`

Responsibilities:

- load `faster-whisper` once
- stay resident in memory
- serve transcription requests over a Unix domain socket

This avoids paying model startup cost on every dictation.

## 3. Overlay process

`bin/hermeskey-overlay.py`

Responsibilities:

- show a small visual status chip
- remain click-through
- avoid focus stealing

## Supporting services

### `hermeskey.service`

Keeps the speech model warm.

### `hermeskey-ydotoold.service`

Runs `ydotoold` as a **user service**, which is important for Wayland typing workflows.

## Design principles

- local-first
- fast startup
- minimal dependencies
- focus-safe behavior by default where practical
- no mandatory mouse interaction
