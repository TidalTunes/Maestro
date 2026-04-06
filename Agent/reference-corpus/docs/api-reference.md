# API Reference

This document describes the current `maestroxml` API.

For workflow guidance, see [Getting Started](getting-started.md). For larger examples, see [Examples](examples.md).

## Public Imports

```python
from maestroxml import (
    Part,
    Score,
    VoiceCursor,
    musicxml_string_to_python,
    musicxml_to_python,
)
```

Most user code only needs `Score`.

## Import Helpers

### `musicxml_to_python(...)`

```python
musicxml_to_python(path, *, output_path=None)
```

Arguments:

- `path`: path to a MusicXML file
- `output_path`: optional path string to include in the generated `score.write(...)` call

Returns editable Python source that recreates the supported MusicXML content with the `maestroxml` API.

Supported input roots:

- `score-partwise`
- `score-timewise`

The importer is intentionally lossy. Unsupported MusicXML details are dropped instead of being represented as raw XML escape hatches.

### `musicxml_string_to_python(...)`

```python
musicxml_string_to_python(xml_text, *, output_path=None)
```

Same as `musicxml_to_python(...)`, but accepts MusicXML text directly.

## Score

### Constructor

```python
Score(*, title=None, composer=None, lyricist=None, rights=None)
```

Arguments:

- `title`: score title
- `composer`: composer metadata
- `lyricist`: lyricist metadata
- `rights`: rights/copyright metadata

### `add_part(...)`

```python
score.add_part(
    name,
    *,
    instrument=None,
    abbreviation=None,
    staves=None,
    clefs=None,
)
```

Creates and returns a `Part`.

Arguments:

- `name`: logical part name used by the builder
- `instrument`: optional preset key such as `"violin"` or `"piano"`
- `abbreviation`: optional stored abbreviation
- `staves`: optional staff count override
- `clefs`: optional iterable of clef names or `(sign, line)` tuples

Notes:

- Presets fill in default staves and clefs unless overridden.
- Parts added after measures already exist are backfilled with empty measure state so the score stays synchronized.

### `measure(...)`

```python
score.measure(number=None)
```

Selects the active measure and returns the `Score`.

Behavior:

- `score.measure(1)` selects measure 1.
- `score.measure()` advances by one measure.
- The first `score.measure()` with no argument starts at measure 1.

### `time_signature(...)`

```python
score.time_signature(signature, beat_type=None)
```

Accepted forms:

- `score.time_signature("4/4")`
- `score.time_signature("6, 8")`
- `score.time_signature((3, 8))`
- `score.time_signature([5, 4])`
- `score.time_signature(7, 8)`

Sticky score-level state: once set, it stays active until changed.

### `key_signature(...)`

```python
score.key_signature(signature, mode=None)
```

Accepted forms:

- `score.key_signature("C major")`
- `score.key_signature("A minor")`
- `score.key_signature(2, mode="major")`
- `score.key_signature(-3, mode="minor")`

Sticky score-level state: once set, it stays active until changed.

### `unsupported_features()`

```python
features = score.unsupported_features()
```

Returns a sorted list of notation features currently accepted by the builder but not fully written by the current MuseScore bridge backend.

Typical values include:

- `"ties"`
- `"slurs"`
- `"wedge spanners"`
- `"repeat start barlines"`
- `"repeat end barlines"`
- `"volta endings"`
- `"clef changes"`
- `"some articulations"`

### `to_actions(...)`

```python
actions = score.to_actions(
    *,
    include_structure=True,
    ignore_unsupported=True,
)
```

Returns a list of action dictionaries suitable for `maestro-musescore-bridge`.

Arguments:

- `include_structure`:
  - when `True`, include bridge actions that append later parts and extra measures
  - this assumes the open MuseScore score already has a first part matching the first `maestroxml` part
- `ignore_unsupported`:
  - when `True`, unsupported features are skipped or approximated
  - when `False`, `ValueError` is raised if unsupported features are present

### `to_batch(...)`

```python
batch = score.to_batch(
    *,
    include_structure=True,
    ignore_unsupported=True,
)
```

Builds and returns a `maestro_musescore_bridge.ActionBatch`.

Requires `maestro-musescore-bridge` to be importable.

### `to_string(...)`

```python
json_text = score.to_string(
    *,
    include_structure=True,
    ignore_unsupported=True,
)
```

Returns the bridge action plan as pretty-printed JSON text.

### `write(...)`

```python
path_obj = score.write(
    "piece-actions.json",
    include_structure=True,
    ignore_unsupported=True,
)
```

Writes the JSON action plan to disk and returns the resulting `Path`.

### `apply(...)`

```python
result = score.apply(
    client=None,
    *,
    fail_on_partial=True,
    include_structure=True,
    ignore_unsupported=True,
)
```

Applies the score to a live MuseScore score through `maestro-musescore-bridge`.

Arguments:

- `client`: optional `MuseScoreBridgeClient`; if omitted, `maestroxml` creates one
- `fail_on_partial`: passed through to `client.apply_actions(...)`
- `include_structure`: same meaning as in `to_actions(...)`
- `ignore_unsupported`: same meaning as in `to_actions(...)`

Returns the bridge result payload.

## Part

`Part` is the convenience API for the common case: voice 1 on staff 1.

### `measure(...)`

```python
part.measure(number=None)
```

Convenience wrapper around `score.measure(...)`.

### Note Entry Methods

```python
part.note(duration, pitch, **kwargs)
part.notes(duration, pitches, **kwargs)
part.rest(duration, **kwargs)
part.chord(duration, pitches, **kwargs)
```

These methods write to voice 1, staff 1.

### Direction Methods

```python
part.tempo(bpm, beat_unit="quarter", text=None, placement="above")
part.dynamic(mark, placement="below")
part.text(content, placement="above")
part.wedge(type, placement="below")
```

Supported wedge types:

- `"crescendo"`
- `"diminuendo"`
- `"stop"`

### Structure Methods

```python
part.clef(clef, staff=1)
part.repeat_start()
part.repeat_end(times=None)
part.ending(number, type)
part.voice(number, staff=1)
```

Supported ending types:

- `"start"`
- `"stop"`
- `"discontinue"`

## VoiceCursor

Use `part.voice(number, staff=...)` when a part needs independent voice or staff streams.

`VoiceCursor` supports the same note/rest/chord and direction methods as `Part`, but writes into the selected voice and staff.

## Shared Note Parameters

These keyword arguments are accepted by `note(...)` and `chord(...)`, and partly by `rest(...)`.

### Duration And Rhythm

- `dots=int`
- `tuplet=(actual, normal)`
- `tuplet=(actual, normal, normal_type)`

Supported duration names:

- `whole`
- `half`
- `quarter`
- `eighth`
- `16th`
- `32nd`
- `64th`

### Notation

- `tie="start" | "stop" | ("stop", "start")`
- `slur="start" | "stop" | ("stop", "start")`
- `articulations=[...]`
- `accidental="sharp" | "flat" | "natural" | ...`
- `beams=["begin", "continue", "end"]`

Supported pitch strings:

- `C4`
- `F#5`
- `Bb3`
- `Cn4`
- `E##5`
- `Gbb2`

## Current Bridge Limits

The builder still accepts more notation than the current MuseScore bridge/plugin can fully materialize. Today `maestroxml` does not promise exact bridge output for:

- ties and slurs
- wedge spanners
- repeat start/end barlines
- volta endings
- clef changes after the initial setup
- some articulations and engraving-only details

Those features remain useful in the builder model and importer output, but the bridge backend may skip or approximate them.
