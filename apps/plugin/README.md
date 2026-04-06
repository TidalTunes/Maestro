# Maestro Plugin

This directory contains the MuseScore-side assets shipped with Maestro today.

## Current Contents

- `assets/maestro_python_bridge.qml`: the running bridge plugin dialog
- `assets/bridge_actions.js`: action-kind mapping and command translation
- `assets/score_operations.js`: shared MuseScore score-edit operations

The desktop app installer copies these three files into the user's MuseScore plugin directory on first run.

## Responsibility

- keep MuseScore plugin assets in one canonical location
- provide the user-facing plugin artifact named `Maestro Plugin`
- isolate MuseScore host specifics from the Python service and shared packages

## Boundaries

- Put shipped plugin assets and plugin-side notes here.
- Do not put OpenAI calls here.
- Do not put general-purpose score-planning logic here.
- Keep the transport contract in `packages/maestro-musescore-bridge` and `contracts/score-actions`.
