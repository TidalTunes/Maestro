# maestro-musescore-bridge

`maestro-musescore-bridge` is a Python package for editing a live MuseScore score by code.

It talks to the `Maestro Plugin` MuseScore plugin over a lightweight file protocol and exposes explicit action methods such as `add_note`, `add_dynamic`, `add_time_signature`, and many more.

## Documentation Map

- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [CLI Reference](docs/cli-reference.md)
- [Action Reference](docs/action-reference.md)
- [Protocol Reference](docs/protocol-reference.md)
- [Examples](docs/examples.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Lightweight Tester](testing/README.md)

## What You Get

- strongly explicit action interface for score edits
- single-action and batch workflows
- generated helper methods for all supported action kinds
- CLI for quick operational checks and JSON action files
- predictable error model (`BridgeTimeoutError`, `BridgeResponseError`)

## Requirements

- Python `>=3.10`
- MuseScore with plugin support
- Bridge plugin files installed in MuseScore plugin directory:
  - `apps/plugin/assets/maestro_python_bridge.qml`
  - `apps/plugin/assets/bridge_actions.js`
  - `apps/plugin/assets/score_operations.js`

## Quick Start

1. Install the package:

```bash
pip install -e packages/maestro-musescore-bridge
```

2. Open MuseScore and run:

- `Plugins > Maestro > Maestro Plugin`

3. Keep the plugin dialog open.

4. Run Python:

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()
print(client.ping())

batch = client.batch()
batch.append_measures(count=2)
batch.add_time_signature(numerator=4, denominator=4, tick=0, staff=0)
batch.add_key_signature(key="C", tick=0, staff=0)
batch.add_tempo(bpm=100, text="Andante", tick=0, staff=0)
batch.add_note(pitch="C4", duration="quarter", tick=0, staff=0, voice=0)
batch.add_note(pitch="D4", duration="quarter", tick=480, staff=0, voice=0)
print(client.apply_batch(batch))
```

## CLI Quick Use

```bash
maestro-musescore-bridge ping
maestro-musescore-bridge list-actions
maestro-musescore-bridge score-info
maestro-musescore-bridge read-score
maestro-musescore-bridge apply-json ./actions.json
```

`actions.json` can be either:

- an array of action objects
- an object with an `actions` array

## Safety Notes

- `add_harmony` is intentionally blocked in the plugin and returns a safe error.
  - Reason: adding chord symbols programmatically can crash MuseScore 4 plugin host in current API behavior.
- If you want partial success for large workloads, pass `fail_on_partial=False` to `apply_actions()` / `apply_batch()`.

## Testing Harness

For a minimal button-driven demo UI, use:

- [testing/lightweight_tester.py](testing/lightweight_tester.py)
- Instructions: [testing/README.md](testing/README.md)
