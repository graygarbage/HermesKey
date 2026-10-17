# Support

## First places to look

- [README.md](README.md)
- [docs/INSTALL.md](docs/INSTALL.md)
- [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- run `hermeskey-doctor`

## Before opening an issue

Please gather:

- distro name and version
- desktop environment / compositor
- `echo $XDG_SESSION_TYPE`
- whether `ydotool` works by itself
- `hermeskey-doctor` results, reviewed for anything personal before sharing
- relevant log or `systemctl --user status hermeskey.service` excerpts **for local review first**; share only the minimum needed after redacting paths, device/app names, URLs and other personal information. Never post recordings, dictated text, tokens, full config files or raw journals publicly. For a suspected vulnerability, follow [SECURITY.md](SECURITY.md) instead of posting details in an issue.

## Questions

If you are not sure whether something is a bug, open a discussion-style issue with enough context and repro steps.
