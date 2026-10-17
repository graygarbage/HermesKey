# Releasing HermesKey

## Release philosophy

HermesKey releases should feel deliberate:

- changelog updated
- docs updated
- CI green
- release artifact generated
- release notes written by a human, not just auto-generated

## Checklist

- [ ] update `VERSION`
- [ ] update `CHANGELOG.md` and write `docs/releases/v$VERSION.md` (published as the GitHub Release body; use absolute links)
- [ ] run `make check` and `make package`
- [ ] verify install docs still match reality
- [ ] test `bash scripts/bootstrap.sh --local` on a fresh KDE test install **and** an upgrade (confirm existing config is preserved, the Settings launcher is the sole visible menu entry, and pinned legacy shortcuts still work)
- [ ] confirm microphone dictation, Unicode insertion, Settings save/restart, and `hermeskey-doctor` on the test machine
- [ ] merge release-prep PR; on `main`, pull the merged commit and confirm `VERSION`, changelog date, and release notes before tagging
- [ ] tag/push the release from the verified `main` commit only (with approval)
- [ ] verify GitHub Actions published the `.tar.gz` archive and the handwritten release body; confirm the standard installer resolves the new release

## Helper commands

Check the repo:

```bash
make check
```

Build the release tarball:

```bash
make package
```

Cut a release using the helper script:

```bash
./scripts/release.sh
```

## Notes

- `scripts/release.sh` expects a clean git working tree.
- The release workflow publishes a `.tar.gz` archive when a `v*` tag is pushed.
- Hand-written release notes live under `docs/releases/`.
