# Getting Started

This guide shows the intended workflow for `maestroxml`: create a score, add parts, move through measures, write notes with normal Python code, and export MusicXML.

For the complete API, see [API Reference](api-reference.md). For larger worked examples, see [Examples](examples.md).

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

`Score` stores document-level metadata and score-wide state.

## 2. Add Parts

```python
violin = score.add_part("Violin", instrument="violin")
viola = score.add_part("Viola", instrument="viola")
cello = score.add_part("Cello", instrument="cello")
```

The `instrument=` argument selects built-in presets for:

- part abbreviation
- number of staves
- default clefs
- MusicXML instrument name

If you do not use a preset, the library falls back to one staff with a treble clef.

## 3. Start A Measure Before Writing Music

```python
score.measure(1)
score.time_signature("4/4")
score.key_signature("G major")
```

Important rules:

- You must call `score.measure(...)` before adding notes, rests, chords, or directions.
- `score.measure()` with no argument advances to the next measure.
- Time signatures and key signatures are sticky. Set them only when they change.

Example:

```python
score.measure(1)
score.time_signature("3/4")
score.key_signature("D minor")

score.measure(2)
# still 3/4 and D minor

score.measure(3)
score.time_signature("4/4")
# key stays D minor until changed
```

## 4. Write Notes, Rests, And Chords

For simple writing, use the `Part` methods directly. They write to voice 1 on staff 1.

```python
score.measure(1)
score.time_signature("4/4")
score.key_signature("C major")

violin.note("quarter", "C5")
violin.notes("eighth", ["D5", "E5", "G5", "A5"])
violin.rest("quarter")
violin.chord("half", ["C5", "E5", "G5"])
```

You can also add rhythmic and notational details. Each line below is an independent example:

```python
violin.note("quarter", "F#5", dots=1)
violin.note("eighth", "G5", tuplet=(3, 2))
violin.note("quarter", "A5", tie="start", slur="start")
violin.note("quarter", "A5", tie="stop", slur="stop", articulations=["accent"])
```

## 5. Add Tempo, Dynamics, And Text

Directions attach to the current position in the active measure.

```python
score.measure(1)
violin.tempo(88, text="Andante")
violin.dynamic("mp")
violin.text("dolce")
violin.wedge("crescendo")
```

Later, stop the wedge when needed:

```python
score.measure(2)
violin.wedge("stop")
```

## 6. Use Multiple Voices Or Multiple Staves

Use `voice(number, staff=...)` when a part needs independent lines or piano notation.

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

The serializer emits the MusicXML `<backup>` elements automatically.

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

## 7. Use Loops And Helpers

The package is most useful when you treat musical material as Python data.

### Loop Over A Progression

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

### Wrap A Repeated Pattern In A Helper

```python
def ostinato(part, pulse_pitch, leap_pitch):
    part.note("eighth", pulse_pitch)
    part.note("eighth", pulse_pitch)
    part.note("eighth", leap_pitch)
    part.note("eighth", pulse_pitch)
    part.note("eighth", pulse_pitch)
    part.note("eighth", leap_pitch)

score.measure(1)
ostinato(cello, "E2", "B2")

score.measure(2)
ostinato(cello, "C2", "G2")
```

## 8. Export MusicXML

Use `to_string()` if you want the XML as a string:

```python
xml_text = score.to_string()
```

Use `write(path)` if you want a file:

```python
score.write("miniature.musicxml")
```

`write()` returns a `Path` object pointing to the file it created.

## 9. Import Existing MusicXML Into Python

You can also start from an existing MusicXML file and ask `maestroxml` to generate editable Python.

```python
from maestroxml import musicxml_to_python

code = musicxml_to_python(
    "existing.musicxml",
    output_path="edited.musicxml",
)

print(code)
```

What this does:

- reads the MusicXML file
- keeps the parts of the score that `maestroxml` knows how to express
- returns Python code that builds a `score` object
- optionally adds `score.write(...)` to the generated code when `output_path` is provided

What it does not do:

- preserve unsupported MusicXML details
- preserve every engraving nuance exactly
- expose raw XML fragments in the generated code

The generated code is meant to be a clean editing starting point, not a lossless serializer for every MusicXML feature.

## 10. Complete Example

```python
from maestroxml import Score

score = Score(title="Short Duet", composer="Example Composer")
flute = score.add_part("Flute", instrument="flute")
clarinet = score.add_part("Clarinet", instrument="clarinet")

score.measure(1)
score.time_signature("3/4")
score.key_signature("F major")
flute.tempo(96, text="Lightly")
flute.notes("quarter", ["A4", "C5", "D5"])
clarinet.note("half", "F3")
clarinet.note("quarter", "C4")

score.measure(2)
flute.note("quarter", "E5", tie="start")
flute.note("quarter", "F5")
flute.note("quarter", "G5")
clarinet.chord("half", ["F3", "A3", "C4"])
clarinet.rest("quarter")

score.measure(3)
flute.note("half", "E5", tie="stop", articulations=["tenuto"])
flute.rest("quarter")
clarinet.dynamic("mp")
clarinet.note("half", "F3")
clarinet.note("quarter", "C4")

score.write("short-duet.musicxml")
```

## Common Pitfalls

- Do not add notes before calling `score.measure(...)`.
- Do not assume the library balances each measure to the time signature for you.
- Do not use `Part.note(...)` when you actually need a second voice or a second staff; use `voice(...)` instead.
- Do not set time signatures or key signatures in every measure unless they actually change.
- Do not hand-build MusicXML fragments unless you are extending the library itself.
