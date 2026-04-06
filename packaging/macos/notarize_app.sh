#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PATH="${APP_PATH:-$ROOT_DIR/dist/Maestro.app}"
IDENTITY="${APPLE_CODESIGN_IDENTITY:-}"
TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_ID="${APPLE_ID:-}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"

if [[ -z "$IDENTITY" || -z "$TEAM_ID" || -z "$APPLE_ID" || -z "$APPLE_APP_PASSWORD" ]]; then
  echo "Set APPLE_CODESIGN_IDENTITY, APPLE_TEAM_ID, APPLE_ID, and APPLE_APP_PASSWORD first." >&2
  exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
  echo "App bundle not found at $APP_PATH" >&2
  exit 1
fi

codesign --force --deep --options runtime --timestamp \
  --entitlements "$ROOT_DIR/packaging/macos/maestro.entitlements" \
  --sign "$IDENTITY" \
  "$APP_PATH"

ZIP_PATH="${APP_PATH%.app}.zip"
/usr/bin/ditto -c -k --keepParent "$APP_PATH" "$ZIP_PATH"

xcrun notarytool submit "$ZIP_PATH" \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_APP_PASSWORD" \
  --team-id "$TEAM_ID" \
  --wait

xcrun stapler staple "$APP_PATH"

echo "Signed and notarized $APP_PATH"
