# Getting Started

`maestroxml` is now a bridge-backed MuseScore workflow:

1. Build a score in Python.
2. Convert it to bridge actions with `to_actions()`.
3. Apply those actions to a live MuseScore score with `apply()`.

For existing live scores, the pattern is slightly different: use imported `maestroxml` code as reference, build only the requested change plan, and export only the delta actions.

For the full method list, see [API Reference](api-reference.md). For longer examples, see [Examples](examples.md).

## 1. Create A Score

```python
from maestroxml import Score

score = Score(
    title="Miniature",
    composer="Example Composer",
    lyricist="Optional",
    rights="Optional",
)
```

`Score` stores score metadata and the current measure-level state.

## 2. Add Parts

```python
violin = score.add_part("Violin", instrument="violin")
viola = score.add_part("Viola", instrument="viola")
cello = score.add_part("Cello", instrument="cello")
```

Presets currently exist for:

- `violin`
- `viola`
- `cello`
- `piano`
- `flute`
- `clarinet`
- `voice`

Each preset fills in default staves and clefs for the builder model. On the MuseScore side, `maestroxml` uses these presets to choose bridge part setup when it can.

## 3. Select Measures Before Writing

```python
score.measure(1)
score.time_signature("4/4")
score.key_signature("G major")
```

Rules:

- Call `score.measure(...)` before adding notes, rests, chords, or directions.
- `score.measure()` with no argument advances to the next measure.
- Time and key signatures are sticky score-level state. Set them only when they change.

## 4. Add Notes, Rests, And Chords

For simple writing, use the `Part` methods directly. They target voice 1 on staff 1.

```python
score.measure(1)
score.time_signature("4/4")
score.key_signature("C major")

violin.note("quarter", "C5")
violin.notes("eighth", ["D5", "E5", "G5", "A5"])
violin.rest("quarter")
violin.chord("half", ["C5", "E5", "G5"])
```

You can also add rhythmic modifiers and notational intent:

```python
violin.note("quarter", "F#5", dots=1)
violin.note("eighth", "G5", tuplet=(3, 2))
violin.note("quarter", "A5", tie="start", slur="start")
violin.note("quarter", "A5", tie="stop", slur="stop", articulations=["accent"])
```

The builder accepts these values even when the current bridge backend can only approximate or skip some of them.

## 5. Add Tempo, Dynamics, And Text

```python
score.measure(1)
violin.tempo(88, text="Andante")
violin.dynamic("mp")
violin.text("dolce")
violin.wedge("crescendo")
```

Directions attach at the current cursor position in the active measure.

## 6. Use Multiple Voices Or Multiple Staves

Use `voice(number, staff=...)` when one part needs independent streams.

### Piano Example

```python
score = Score(title="Piano Sketch")
piano = score.add_part("Piano", instrument="piano")

right_hand = piano.voice(1, staff=1)
left_hand = piano.voice(1, staff=2)

score.measure(1)
score.time_signature("4/4")
score.key_signature("G major")

right_hand.notes("quarter", ["G4", "A4", "B4", "D5"])
left_hand.note("half", "G2")
left_hand.note("half", "D3")
```

### Two Voices On One Staff

```python
solo = score.add_part("Solo Violin", instrument="violin")
upper = solo.voice(1, staff=1)
lower = solo.voice(2, staff=1)

score.measure(1)
score.time_signature("2/4")
upper.notes("eighth", ["E5", "D5", "C5", "B4"])
lower.note("quarter", "A4")
lower.note("quarter", "G4")
```

## 7. Generate Patterns With Python

The package is most useful when you keep musical material in Python data structures.

```python
progression = {
    1: ("C2", "E3", "G3", "C4"),
    2: ("A1", "E3", "A3", "C4"),
    3: ("F2", "A3", "C4", "F4"),
    4: ("G2", "B3", "D4", "G4"),
}

for measure_number, pitches in progression.items():
    score.measure(measure_number)
    cello.note("whole", pitches[0])
    viola.note("whole", pitches[1])
    violin2.note("whole", pitches[2])
    violin1.note("whole", pitches[3])
```

## 8. Inspect Or Save The Action Plan

Use `to_actions()` when you want the raw bridge payloads:

```python
actions = score.to_actions()
```

Use `to_string()` when you want those actions as JSON text:

```python
json_text = score.to_string()
```

Use `write(path)` when you want that action plan on disk:

```python
score.write("miniature-actions.json")
```

`write()` returns the written `Path`.

## 9. Apply The Score To MuseScore

Start MuseScore and open the bridge plugin dialog first:

- `Plugins > Maestro > Maestro Plugin`

Then run:

```python
result = score.apply()
print(result["all_ok"])
```

`apply()` creates a default `MuseScoreBridgeClient` if you do not pass one.

If you already have a configured client:

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient(timeout=20.0)
score.apply(client, fail_on_partial=False)
```

## 10. Build Live Edit Deltas

When you already have a score open in MuseScore, do not recreate the whole score just to add one note or dynamic.

Use a shell cloned from the current score and emit only the new bridge actions:

```python
base_score = score_from_current_context
edit_score = base_score.clone_shell()

flute = edit_score.parts[0]
edit_score.measure(8)
flute.note("quarter", "G5")
flute.dynamic("mf")

actions = edit_score.to_delta_actions(base_score)
```

That keeps `maestroxml` in its natural role: score-shaped change planning that compiles into bridge actions.

## 11. Start From Existing MusicXML

The importer still accepts MusicXML and turns it into editable Python:

```python
from maestroxml import musicxml_to_python

code = musicxml_to_python(
    "existing.musicxml",
    output_path="existing-actions.json",
)

print(code)
```

The generated code rebuilds the supported score content with the `maestroxml` API. Unsupported MusicXML details are skipped.

`output_path` is optional. When provided, the generated code includes `score.write(...)`, which now writes the bridge action plan JSON rather than MusicXML.

## 12. Current Backend Limits

The builder API is a little broader than the current MuseScore bridge backend. Today these are not fully materialized:

- ties
- slurs
- wedge spanners
- repeat barlines and volta endings
- clef changes beyond initial preset setup
- some articulations and engraving-only details

Check `score.unsupported_features()` if you want a quick summary before calling `apply()`.
