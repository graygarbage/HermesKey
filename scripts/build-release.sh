#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"

# Archives are published assets: refuse uncommitted changes and unknown files.
# Do not include local caches, recordings, .env files or build artifacts.
if [[ -n "$(git -C "$ROOT" status --porcelain --untracked-files=normal)" ]]; then
  printf 'Release archive requires a clean Git checkout; commit/review changes first.\n' >&2
  exit 1
fi
VERSION="$(git -C "$ROOT" show HEAD:VERSION | tr -d '[:space:]')"
NAME="hermeskey-$VERSION"
ARCHIVE="$DIST/$NAME.tar.gz"

mkdir -p "$DIST"
tmp="$(mktemp "$DIST/.${NAME}.XXXXXX")"
trap 'rm -f -- "$tmp"' EXIT
# Git stores only reviewed tracked files and their executable modes. Stable
# commit metadata and gzip -n make repeated builds of a commit byte-identical.
git -C "$ROOT" archive --format=tar HEAD | gzip -n >"$tmp"
mv -f -- "$tmp" "$ARCHIVE"

echo "$ARCHIVE"
