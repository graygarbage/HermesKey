# Changelog

All notable changes to HermesKey will be documented in this file.

## [Unreleased]

- TBD

## [0.6.3] - 2026-10-17

Privacy and runtime-state security maintenance release.

### Security

- recordings, PID/overlay state and speech sockets no longer use predictable shared `/tmp` paths when `XDG_RUNTIME_DIR` is absent. Runtime paths must be directly inside a private user-owned directory; unsafe files and symlinks are refused before recording, and stale recorder/overlay PIDs are checked against process start time before signaling
- fresh installs create the config directory as `0700` and user config as `0600`; upgrades tighten older permissions without replacing config values. The config opener also creates or tightens these modes and refuses symlinked config paths
- install verification no longer prints the transcription of a custom sample, including on failure; untrusted error messages and private sample paths are omitted from diagnostics

## [0.6.2] - 2026-10-17

Security maintenance release for Wayland typing socket trust.

### Security

- HermesKey no longer falls back to a shared `/tmp` `ydotool` socket. It accepts typing sockets only directly within an owner-only user runtime directory, owned by the current user, with owner-only permissions and no symlink; untrusted or unavailable sockets are refused before sending keystrokes
- when typing is refused, a transcript is left on the clipboard only if clipboard backup is enabled; otherwise no text is inserted or copied

## [0.6.1] - 2026-10-17

Privacy-focused maintenance release for local dictation and support diagnostics.

### Security

- dictated text and active-window metadata are passed to typing and matching helpers over standard input rather than process arguments; custom model IDs/paths are no longer placed in the long-lived speech-server command line. An older `ydotool` without safe stdin support now refuses direct typing rather than exposing private text
- Doctor no longer includes raw service journal/status snippets, local paths or audio-device lists; the speech server forwards only its own sanitized events through Python logging, not third-party model/network INFO messages

### Added

- a GitHub repository social-preview image and editable source, for optional manual upload in repository settings

## [0.6.0] - 2026-10-17

Settings GUI release: one window for day-to-day configuration and local support tools.

### Added

- native PySide6 Settings window with Speech, Input, Appearance, and System pages; safely edit model, spoken language, microphone, insertion and clipboard behavior, focus safety, overlay, and sound (#4–#8, #59)
- service readiness and restart actions, local Doctor and bounded log viewers, and an advanced config-file action in Settings (#8, #56)
- bootstrap checks for system dependencies and a working speech venv, waits for model readiness, and validates a synthetic-audio transcription after installing; Doctor now validates config values (#46, #47)

### Fixed

- Wayland `ydotool type` silently losing non-ASCII transcripts: use clipboard paste when backup is enabled, otherwise warn without copying or inserting text (#54, #55)
- speech-server error logging no longer includes raw exception messages or request content (#48)

### Changed

- Settings is the single visible KDE menu entry; legacy Status, Doctor, Logs, Config, and Control Center desktop IDs remain hidden for pinned shortcuts and their CLI helpers remain available (#56)
- Control Center launches Settings; AppStream points to the Settings desktop entry (#56)

## [0.5.2] - 2026-10-16

Reliability release for Wayland input and rapid hotkey presses.

### Fixed

- `hermeskey-ydotoold.service` now retries without exhausting systemd's start limit before the graphical login grants `/dev/uinput` access; retries are spaced 10 seconds apart (#43)
- rapid hotkey presses no longer overlap recording, transcription, or text insertion and lose results; presses during an active transition are ignored with a notification (#44)
- fresh installs no longer select PyAV 19, which is incompatible with `faster-whisper` 1.2.1 during WAV decoding

### Changed

- the doctor reports whether `/dev/uinput` is available to the current user, and troubleshooting guidance explains how to diagnose missing access (#43)
- audio troubleshooting documentation includes common recording issues (#41)

## [0.5.1] - 2026-10-14

Branding release.

### Added

- app icon (winged keycap) installed as `hermeskey` in the hicolor icon theme and used by the desktop launchers and AppStream metadata (#38)
- README hero banner and GitHub social preview image (#38)

## [0.5.0] - 2026-10-14

Active window detection, reliability, and faster typing.

### Fixed

- active window detection no longer opens KWin's interactive window picker (crosshair cursor) with `FOCUS_SAFE_MODE=1` (#28)
- the terminal paste fallback (`PASTE_FOR_APPS`) now works; before, it never triggered (#28)
- pressing the hotkey while the model is loading no longer starts a duplicate speech server (#27)
- upgrades restart the services so new code takes effect immediately (#29)
- `STT_LANG=` (empty) now enables language auto-detection as documented (#30)
- the clipboard is no longer wiped when nothing was captured; `COPY_TO_CLIPBOARD=0` is respected (#31)
- a custom venv location (`HERMESKEY_VENV`) is used by the service, doctor, and hotkey script (#32)
- Fedora/Nobara install instructions list `python3-pyside6` (the overlay needs PySide6, not PyQt6) (#33)

### Added

- `TYPE_KEY_DELAY` / `TYPE_KEY_HOLD` settings; typing is about 4x faster by default (#34)
- active window detection via `kdotool`, or a built-in KWin script when `kdotool` is not installed (#28)
- doctor checks for the venv's faster-whisper, the overlay's PySide6, the configured microphone, and the active window detection method

### Changed

- default `RECORD_SOURCE` is `default` instead of a specific USB microphone (#36)
- `PySide6` removed from `requirements.txt` (the overlay uses the system Python) (#33)
- `scripts/check.sh` checks every shell script; CI and `make check` use it (#35)

## [0.4.2] - 2026-10-14

Bug-fix and privacy release.

### Security

- voice recordings are no longer world-readable: audio is recorded into `$XDG_RUNTIME_DIR` with owner-only permissions and deleted after transcription (#18)
- the speech server socket is created with owner-only permissions from the start (#22)
- KWin window info is parsed as data instead of being `eval`'d / `source`d (hardening; #19)

### Fixed

- typing/paste failures now show the specific reason (e.g. "ydotoold not running") instead of a generic error (#25)

### Changed

- logs moved from `/tmp` to `~/.local/state/hermeskey/`; custom `LOG` / `WAV` settings are still honored
- new `KEEP_AUDIO` option (default `0`) to keep the last recording for debugging
- the installer removes leftover world-readable `/tmp` audio and log files from older versions

## [0.4.1] - 2026-10-13

Documentation and installer polish release.

### Changed

- simplified the README and moved detailed material into deep-dive docs
- cleaned installer output for bootstrap installs
- replaced temporary local doc paths with stable GitHub doc links

## [0.4.0] - 2026-10-13

Desktop utility polish release.

### Added

- HermesKey Control Center desktop helper
- desktop log viewer and service restart helper
- expanded local desktop launcher set and docs

### Changed

- improved installer integration for local application launchers
- strengthened desktop integration documentation and installed-file reporting

## [0.3.0] - 2026-10-13

Desktop integration and packaging-first release.

### Added

- desktop launcher helpers for status, doctor, and config access
- desktop entry templates and AppStream metadata scaffold
- packaging guidance and updated RPM / AUR starter files
- release helper script and CLI status plumbing improvements

### Changed

- improved installer output and installed-file reporting
- documented desktop integration and launcher behavior
- expanded README and install docs around integration and distribution

## [0.2.0] - 2026-10-13

Command-and-distribution polish release.

### Added

- `hermeskey --help`, `--version`, `--status`, and `--doctor`
- richer bootstrap installer output and post-install guidance
- release process documentation and helper script
- packaging direction docs and starter RPM / AUR scaffolding
- hotkey setup documentation

### Changed

- improved README install flow and distro quick-start presentation
- tightened the project’s packaging and release story

## [0.1.3] - 2026-10-13

Workflow maintenance release.

### Changed

- upgraded GitHub Actions workflow versions to current non-deprecated releases
- kept CI and release automation aligned with the latest toolchain expectations

## [0.1.2] - 2026-10-13

Maintenance release.

### Changed

- fixed CI unit verification for environments without `ydotoold` installed
- kept release automation and package build green on GitHub Actions

## [0.1.1] - 2026-10-13

Polish release focused on packaging, branding, and maintainability.

### Added

- branded SVG banner, mark, and workflow art
- `hermeskey-doctor` diagnostics command
- release packaging script and GitHub release workflow
- CODEOWNERS, CODE_OF_CONDUCT, SECURITY, SUPPORT, and Dependabot config
- expanded configuration, FAQ, install, troubleshooting, and architecture docs

### Changed

- upgraded README presentation and quick-start flow
- improved installer guidance and preflight checks
- tightened shell compatibility for CI and shellcheck

## [0.1.0] - 2026-10-13

Initial public release.

### Added

- prewarmed `faster-whisper` server
- one-key push-to-talk toggle workflow
- click-through recording/transcribing overlay
- soft start/stop tones
- direct typing into active app
- clipboard backup and terminal paste fallback
- user-level `ydotoold` service for Wayland
- install and uninstall scripts
- config file support
