# Assets

| File | Use |
|---|---|
| `hermeskey-icon.svg` | App icon. Installed as `hermeskey` in the hicolor icon theme and used by the desktop launchers. |
| `hermeskey-banner.svg` | README hero banner. **Generated**: do not edit by hand. |
| `src/hermeskey-banner.src.svg` | Editable banner source (real text). |
| `hermeskey-social.png` | GitHub social preview, 1280x640. Upload it in **Settings → General → Social preview**; GitHub does not use the file from the repo automatically. |
| `src/hermeskey-social.src.svg` | Editable social preview source. |

The banner's text is converted to outlines so GitHub shows it the same no matter which fonts the viewer has. After editing the source, regenerate it with:

```bash
inkscape assets/src/hermeskey-banner.src.svg --export-text-to-path --export-plain-svg -o assets/hermeskey-banner.svg
```

The banner uses the Cantarell font when generating.

Regenerate the social preview with:

```bash
inkscape assets/src/hermeskey-social.src.svg -w 1280 -h 640 -o assets/hermeskey-social.png
```

## Palette

| Colour | Hex |
|---|---|
| Navy (tile, background) | `#0f172a` |
| Gold (Hermes wing) | `#f59e0b` |
| Blue (voice) | `#1d4ed8` |
| White / slate (keycap) | `#f8fafc` / `#94a3b8` |
