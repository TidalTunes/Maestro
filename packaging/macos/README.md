# macOS Packaging

This directory contains the scripts used to build, sign, notarize, and wrap the packaged Maestro macOS companion app for live MuseScore editing.

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

The build now relies on targeted PyInstaller hooks plus explicit exclusions instead of broad `--collect-all` packaging for the audio stack.

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

The current beta release remains intentionally unsigned and unnotarized unless you provide your own Apple credentials.

## DMG

```bash
./packaging/macos/make_dmg.sh
```
