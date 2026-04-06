# macOS Packaging

## Build

```bash
./packaging/macos/build_app.sh
```

The build script creates:

- `dist/Maestro.app`
- `dist/Maestro.app/Contents/MacOS/maestro-runtime-runner`

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
