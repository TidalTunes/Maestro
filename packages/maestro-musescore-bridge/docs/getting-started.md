# Getting Started

This guide gets you from zero to the first successful score edit through Python.

## 1. Prerequisites

- Python `>=3.10`
- MuseScore installed
- Access to this repository

## 2. Install Plugin Files In MuseScore

The bridge package depends on these plugin files:

- `Plugins/maestro_python_bridge.qml`
- `Plugins/bridge_actions.js`
- `Plugins/score_operations.js`

Copy these files into your MuseScore plugin directory.

If you are unsure where that directory is, open MuseScore Plugin Manager and use its plugin-folder navigation.

## 3. Enable And Run The Bridge Plugin

In MuseScore:

1. Enable `Maestro Plugin` in plugin manager.
2. Run `Plugins > Maestro > Maestro Plugin`.
3. Keep the bridge dialog open while your Python script runs.

The bridge watches:

- `~/.maestro-musescore-bridge/request.json`

and writes:

- `~/.maestro-musescore-bridge/response.json`

## 4. Install The Python Package

From repo root:

```bash
pip install -e packages/maestro-musescore-bridge
```

## 5. Verify Connectivity

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()
print(client.ping())
```

Expected: a result object containing `message: "pong"`.

## 6. First Score Edit

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()

batch = client.batch()
batch.append_measures(count=2)
batch.add_time_signature(numerator=4, denominator=4, tick=0, staff=0)
batch.add_key_signature(key="C", tick=0, staff=0)
batch.add_note(pitch="C4", duration="quarter", tick=0, staff=0, voice=0)
batch.add_note(pitch="D4", duration="quarter", tick=480, staff=0, voice=0)

result = client.apply_batch(batch)
print(result)
```

## 7. Run From CLI Instead

```bash
maestro-musescore-bridge ping
maestro-musescore-bridge score-info
```

## 8. Common Early Errors

- `BridgeTimeoutError`:
  - Bridge plugin dialog is not open.
  - Wrong bridge directory.
- `BridgeResponseError: No score is open`:
  - Open a score in MuseScore before score operations.
- `BridgeResponseError: One or more actions failed`:
  - One action in the request was invalid for current score state.

See [Troubleshooting](troubleshooting.md) for deeper diagnostics.
