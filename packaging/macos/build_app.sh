#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
DIST_DIR="${DIST_DIR:-$ROOT_DIR/dist}"
BUILD_DIR="${BUILD_DIR:-$ROOT_DIR/build/pyinstaller}"
APP_NAME="Maestro"
RUNNER_NAME="maestro-runtime-runner"
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$ROOT_DIR/.pyinstaller/config}"
XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT_DIR/.pyinstaller/cache}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python interpreter not found at $PYTHON_BIN" >&2
  exit 1
fi

set_plist_value() {
  local plist_path="$1"
  local key="$2"
  local value="$3"
  if /usr/libexec/PlistBuddy -c "Print :$key" "$plist_path" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Set :$key $value" "$plist_path"
  else
    /usr/libexec/PlistBuddy -c "Add :$key string $value" "$plist_path"
  fi
}

export PYTHONPATH="$ROOT_DIR/apps/frontend-desktop/src:$ROOT_DIR/packages/agent-core/src:$ROOT_DIR/packages/maestroxml/src:$ROOT_DIR/packages/humming-detector/src:$ROOT_DIR/packages/maestro-musescore-bridge/src:$ROOT_DIR/Agent${PYTHONPATH:+:$PYTHONPATH}"
export PYINSTALLER_CONFIG_DIR
export XDG_CACHE_HOME

"$PYTHON_BIN" -m pip install --upgrade pyinstaller >/dev/null

rm -rf "$BUILD_DIR" "$DIST_DIR/$APP_NAME" "$DIST_DIR/$APP_NAME.app" "$DIST_DIR/$RUNNER_NAME" "$DIST_DIR/$RUNNER_NAME.app"
mkdir -p "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$PYINSTALLER_CONFIG_DIR" "$XDG_CACHE_HOME"

add_data_args=(
  "--add-data" "$ROOT_DIR/README.md:maestro_bundle"
  "--add-data" "$ROOT_DIR/Agent:maestro_bundle/Agent"
  "--add-data" "$ROOT_DIR/apps/plugin/assets:maestro_bundle/apps/plugin/assets"
  "--add-data" "$ROOT_DIR/images:maestro_bundle/images"
  "--add-data" "$ROOT_DIR/skills/maestroxml-sheet-music:maestro_bundle/skills/maestroxml-sheet-music"
  "--add-data" "$ROOT_DIR/packages/agent-core/src:maestro_bundle/packages/agent-core/src"
  "--add-data" "$ROOT_DIR/packages/humming-detector/src:maestro_bundle/packages/humming-detector/src"
  "--add-data" "$ROOT_DIR/packages/maestro-musescore-bridge/src:maestro_bundle/packages/maestro-musescore-bridge/src"
  "--add-data" "$ROOT_DIR/packages/maestroxml/src:maestro_bundle/packages/maestroxml/src"
  "--add-data" "$ROOT_DIR/packages/maestroxml/docs:maestro_bundle/packages/maestroxml/docs"
)

collect_args=(
  "--collect-all" "librosa"
  "--collect-all" "sounddevice"
  "--collect-all" "soundfile"
  "--collect-all" "numba"
  "--collect-all" "llvmlite"
)

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "$APP_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR/main" \
  --specpath "$BUILD_DIR/spec" \
  --osx-bundle-identifier "com.tidaltunes.maestro" \
  "${add_data_args[@]}" \
  "${collect_args[@]}" \
  "$ROOT_DIR/apps/frontend-desktop/src/maestro_desktop/app.py"

APP_PLIST="$DIST_DIR/$APP_NAME.app/Contents/Info.plist"
if [[ -f "$APP_PLIST" ]]; then
  set_plist_value "$APP_PLIST" "CFBundleDisplayName" "$APP_NAME"
  set_plist_value "$APP_PLIST" "CFBundleName" "$APP_NAME"
  set_plist_value "$APP_PLIST" "CFBundleShortVersionString" "0.1.0"
  set_plist_value "$APP_PLIST" "CFBundleVersion" "0.1.0"
  set_plist_value "$APP_PLIST" "LSMinimumSystemVersion" "13.0"
  set_plist_value "$APP_PLIST" "NSMicrophoneUsageDescription" "Maestro records humming so it can turn your melodic ideas into score edits."
fi

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --console \
  --onefile \
  --name "$RUNNER_NAME" \
  --distpath "$DIST_DIR" \
  --workpath "$BUILD_DIR/runner" \
  --specpath "$BUILD_DIR/spec" \
  --collect-all "maestroxml" \
  --collect-all "maestro_musescore_bridge" \
  "$ROOT_DIR/packages/agent-core/src/maestro_agent_core/runtime_runner.py"

cp "$DIST_DIR/$RUNNER_NAME" "$DIST_DIR/$APP_NAME.app/Contents/MacOS/$RUNNER_NAME"
chmod +x "$DIST_DIR/$APP_NAME.app/Contents/MacOS/$RUNNER_NAME"
codesign --force --deep --sign - "$DIST_DIR/$APP_NAME.app"

echo "Built $DIST_DIR/$APP_NAME.app"
