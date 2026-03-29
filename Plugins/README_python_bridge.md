# Maestro Python Bridge Plugin

`maestro_python_bridge.qml` is a non-demo plugin intended for script-driven score editing.

## Purpose

- receive explicit score edit actions from Python
- map each action kind to concrete MuseScore API commands
- execute actions inside one undoable command block
- return per-command success or failure

## Files

- `maestro_python_bridge.qml`: bridge runtime and polling loop
- `bridge_actions.js`: action-kind mapping and command translation
- `score_operations.js`: shared MuseScore operation executor

## Action Interface

The bridge supports these request operations:

- `ping`
- `list_actions`
- `score_info`
- `read_score`
- `apply_actions`
- `apply_commands`

`apply_actions` expects action objects with a `kind` key (snake_case). Each kind maps to an explicit score operation, for example:

- `add_note`
- `add_dynamic`
- `add_tempo`
- `add_time_signature`
- `add_key_signature`
- `add_lyrics`
- and other kinds listed by `list_actions`

Safety behavior:
- `add_harmony` is currently blocked with a safe error because chord-symbol insertion can crash MuseScore 4 from plugin API.

## Transport

The bridge reads requests from:

- `~/.maestro-musescore-bridge/request.json`

It writes responses to:

- `~/.maestro-musescore-bridge/response.json`

Keep the plugin dialog open while running Python scripts.
