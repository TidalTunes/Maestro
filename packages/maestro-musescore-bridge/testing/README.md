# Lightweight Testing Harness

This folder is intentionally isolated from the rest of the repo and only depends on:

- `Plugins/maestro_python_bridge.qml`
- `packages/maestro-musescore-bridge`

## Files

- `lightweight_tester.py`: tiny Tkinter window with test buttons.

## What The Buttons Do

- `Ping`: checks plugin bridge connectivity.
- `Score Info`: fetches current score metadata.
- `Seed Basics`: appends measures and adds a short note pattern.
- `Add Markings`: adds dynamics/text/lyrics.
- `All Features`: runs every action kind one-by-one and logs the last attempted action to `last_action_attempt.json`.
- `Read Score`: dumps score events from the plugin.

## Setup (Lightweight)

1. Open MuseScore.
2. Ensure these plugin files are in your MuseScore plugin directory:
   - `maestro_python_bridge.qml`
   - `bridge_actions.js`
   - `score_operations.js`
3. In MuseScore, run `Plugins > Maestro > Maestro Plugin` and keep that dialog open.
4. In a terminal from repo root, install package editable:

```bash
pip install -e packages/maestro-musescore-bridge
```

5. Launch the tester:

```bash
python packages/maestro-musescore-bridge/testing/lightweight_tester.py
```

## Quick Test Flow

1. Click `Ping` (must return `pong`).
2. Click `Seed Basics`.
3. Click `Add Markings`.
4. Click `All Features`.
5. Click `Read Score` to inspect event output.

If MuseScore crashes during `All Features`, reopen this file for the last attempted action:

- `packages/maestro-musescore-bridge/testing/last_action_attempt.json`

If `Ping` fails, the plugin dialog is not running or cannot access `~/.maestro-musescore-bridge`.
