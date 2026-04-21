# macOS Packaging

This directory contains the scripts used to build, sign, notarize, and wrap the packaged Maestro macOS release.

## Build

```bash
./packaging/macos/build_app.sh
```

The build script creates:

- `dist/Maestro.app`
- `dist/Maestro.app/Contents/MacOS/maestro-runtime-runner`

It bundles:

- the desktop frontend from `apps/frontend-desktop`
- the prompt-to-score shim under `agent/`
- the MuseScore plugin assets from `apps/plugin/assets`
- the package source trees needed by the MVP runtime

## Sign + Notarize

Set:

- `APPLE_CODESIGN_IDENTITY`
- `APPLE_TEAM_ID`
- `APPLE_ID`
- `APPLE_APP_PASSWORD`

Then run:

```bash
./packaging/macos/notarize_app.sh
```

## DMG

```bash
./packaging/macos/make_dmg.sh
```
