# maestroxml

`maestroxml` is a Python-first score builder for MuseScore.

You still compose with the same `Score` / `Part` / `voice(...)` API, but the package now targets the local `maestro-musescore-bridge` package instead of emitting MusicXML. It can also import MusicXML into editable Python so an existing score can become a clean `maestroxml` script.

## What It Does

- builds score edits with a simple composition-oriented API
- turns those edits into `maestro-musescore-bridge` action payloads
- applies those actions to a live MuseScore score through the bridge plugin
- writes action-plan JSON for inspection or debugging
- imports supported MusicXML into editable Python using the same API

## Core Workflow

```python
from maestroxml import Score

score = Score(title="Miniature", composer="Example Composer")
flute = score.add_part("Flute", instrument="flute")

score.measure(1)
score.time_signature("4/4")
score.key_signature("D minor")
flute.tempo(84, text="Flowing")
flute.notes("quarter", ["A4", "C5", "D5", "F5"])

actions = score.to_actions()
result = score.apply()
```

`to_actions()` returns bridge action dictionaries.

`to_string()` returns those actions as pretty JSON.

`write(path)` writes that JSON action plan to disk.

`apply()` sends the action plan to MuseScore through `maestro-musescore-bridge`.

## MuseScore Setup

1. Install `maestro-musescore-bridge`.
2. Install the bridge plugin files in MuseScore.
3. Open MuseScore and run `Plugins > Maestro > Python Bridge`.
4. Keep that bridge dialog open while your Python code runs.

For best results, start from a MuseScore score whose first part matches the first `maestroxml` part. `maestroxml` appends later parts and measures through the bridge, but MuseScore still owns the live document structure.

## MusicXML Import

```python
from maestroxml import musicxml_to_python

code = musicxml_to_python("existing.musicxml")
print(code)
```

The importer keeps the subset that `maestroxml` can express and drops unsupported MusicXML details on purpose.

## Current Bridge Limits

The builder API still accepts more notation than the current MuseScore bridge can materialize. Today the backend skips or approximates:

- ties and slurs
- wedge spanners
- repeat start/end barlines and volta endings
- clef changes beyond the initial part presets
- some articulations and engraving-only nuances

Use `score.unsupported_features()` if you want a quick summary before calling `apply()`.

## Documentation

- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [Examples](docs/examples.md)

## Important Paths

- `src/maestroxml/core.py`: builder model and bridge action planning
- `src/maestroxml/importer.py`: MusicXML-to-Python import helpers
- `tests/test_maestroxml.py`: package behavior tests
- `tests/golden/`: MusicXML fixtures used for importer coverage

## Development

Run the package tests with:

```bash
.venv/bin/python -m unittest discover -s packages/maestroxml/tests
```
