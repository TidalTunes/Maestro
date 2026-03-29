# Examples

These examples show how to use `maestroxml` as a code-first composition tool. They favor loops, helper functions, and reusable data structures over repetitive note-by-note boilerplate.

For the underlying API, see [API Reference](api-reference.md). For the core workflow, see [Getting Started](getting-started.md).

## 1. Short Melody With Directions

Use this pattern when you want a single melodic line with tempo, dynamics, and notations.

```python
from maestroxml import Score

score = Score(title="Melody Study", composer="Example Composer")
flute = score.add_part("Flute", instrument="flute")

score.measure(1)
score.time_signature("4/4")
score.key_signature("D minor")
flute.tempo(84, text="Flowing")
flute.dynamic("mp")
flute.text("cantabile")
flute.wedge("crescendo")
flute.note("quarter", "A4", slur="start")
flute.note("eighth", "C5", tuplet=(3, 2), articulations=["staccato"])
flute.note("eighth", "D5", tuplet=(3, 2))
flute.note("eighth", "E5", tuplet=(3, 2))
flute.note("quarter", "F5", tie="start")
flute.note("quarter", "G5")

score.measure(2)
flute.note("quarter", "F5", tie="stop", slur="stop", articulations=["accent"])
flute.rest("quarter")
flute.note("half", "D5")
flute.wedge("stop")

score.write("melody-study.musicxml")
```

## 2. String Quartet With A Loop

Store each harmony as data, then loop over it.

```python
from maestroxml import Score

score = Score(title="Quartet Pulse", composer="Example Composer")
violin1 = score.add_part("Violin I", instrument="violin")
violin2 = score.add_part("Violin II", instrument="violin")
viola = score.add_part("Viola", instrument="viola")
cello = score.add_part("Cello", instrument="cello")

score.measure(1)
score.time_signature("4/4")
score.key_signature("G major")
violin1.notes("quarter", ["G4", "A4", "B4", "D5"])
violin2.rest("whole")
viola.rest("whole")
cello.note("whole", "G2")

progression = [
    (2, {"cello": "G2", "viola": "B3", "violin2": "D4", "violin1": "G4"}),
    (3, {"cello": "E2", "viola": "G3", "violin2": "B3", "violin1": "E4"}),
    (4, {"cello": "C2", "viola": "E3", "violin2": "G3", "violin1": "C4"}),
    (5, {"cello": "D2", "viola": "F#3", "violin2": "A3", "violin1": "D4"}),
]

for measure_number, chord in progression:
    score.measure(measure_number)
    cello.note("whole", chord["cello"])
    viola.note("whole", chord["viola"])
    violin2.note("whole", chord["violin2"])
    violin1.note("whole", chord["violin1"])

score.write("quartet-pulse.musicxml")
```

## 3. Piano Arpeggios Across Two Staves

Use explicit staff cursors for the right and left hand.

```python
from maestroxml import Score

score = Score(title="Broken Chords")
piano = score.add_part("Piano", instrument="piano")
right = piano.voice(1, staff=1)
left = piano.voice(1, staff=2)

score.measure(1)
score.time_signature("4/4")
score.key_signature("C major")

right_patterns = {
    1: ["C4", "E4", "G4", "C5"],
    2: ["A3", "C4", "E4", "A4"],
    3: ["F3", "A3", "C4", "F4"],
    4: ["G3", "B3", "D4", "G4"],
}
left_hand = {
    1: ["C2", "G2"],
    2: ["A1", "E2"],
    3: ["F2", "C3"],
    4: ["G1", "D2"],
}

for measure_number in range(1, 5):
    score.measure(measure_number)
    right.notes("quarter", right_patterns[measure_number])
    for pitch in left_hand[measure_number]:
        left.note("half", pitch)

score.write("broken-chords.musicxml")
```

## 4. Block Chords With A Helper Function

Use `chord(...)` for simultaneous pitches and wrap repeated harmonic gestures in a Python function.

```python
from maestroxml import Score

score = Score(title="Cadence Study")
choir = score.add_part("Choir Reduction", staves=2, clefs=["treble", "bass"])
upper = choir.voice(1, staff=1)
lower = choir.voice(1, staff=2)

score.measure(1)
score.time_signature("3/4")
score.key_signature("F major")

def cadence(measure_number, tonic, predominant, dominant):
    score.measure(measure_number)
    upper.chord("quarter", predominant)
    upper.chord("quarter", dominant)
    upper.chord("quarter", tonic)
    lower.note("half", tonic[0])
    lower.note("quarter", dominant[0])

cadence(1, ["F4", "A4", "C5"], ["Bb4", "D5", "F5"], ["C5", "E5", "G5"])
cadence(2, ["D4", "F4", "A4"], ["G4", "Bb4", "D5"], ["A4", "C#5", "E5"])

score.write("cadence-study.musicxml")
```

## 5. Independent Voices In One Part

Use separate voice numbers when one staff needs contrapuntal lines.

```python
from maestroxml import Score

score = Score(title="Two Voices")
violin = score.add_part("Solo Violin", instrument="violin")
upper = violin.voice(1, staff=1)
lower = violin.voice(2, staff=1)

score.measure(1)
score.time_signature("2/4")
score.key_signature("A minor")
upper.notes("eighth", ["E5", "D5", "C5", "B4"])
lower.note("quarter", "A4")
lower.note("quarter", "G4")

score.measure(2)
upper.notes("eighth", ["C5", "D5", "E5", "G5"])
lower.note("half", "A4")

score.write("two-voices.musicxml")
```

## 6. Repeats And First/Second Endings

The repeat helpers live on `Part`.

```python
from maestroxml import Score

score = Score(title="Binary Dance")
clarinet = score.add_part("Clarinet", instrument="clarinet")

score.measure(1)
score.time_signature("2/4")
score.key_signature("G major")
clarinet.repeat_start()
clarinet.notes("quarter", ["G4", "A4"])

score.measure(2)
clarinet.ending(1, "start")
clarinet.notes("quarter", ["B4", "D5"])

score.measure(3)
clarinet.notes("quarter", ["C5", "B4"])
clarinet.ending(1, "stop")
clarinet.repeat_end(times=2)

score.measure(4)
clarinet.ending(2, "start")
clarinet.notes("quarter", ["D5", "G5"])

score.measure(5)
clarinet.notes("quarter", ["F#5", "G5"])
clarinet.ending(2, "stop")

score.write("binary-dance.musicxml")
```

## 7. Helper-Driven Ostinato Generation

This is the kind of repetitive writing the library is meant to automate.

```python
from maestroxml import Score

score = Score(title="Ostinato Engine")
cello = score.add_part("Cello", instrument="cello")

score.measure(1)
score.time_signature("6/8")
score.key_signature("E minor")

def ostinato(part, pulse_pitch, leap_pitch):
    part.note("eighth", pulse_pitch)
    part.note("eighth", pulse_pitch)
    part.note("eighth", leap_pitch)
    part.note("eighth", pulse_pitch)
    part.note("eighth", pulse_pitch)
    part.note("eighth", leap_pitch)

pattern = {
    1: ("E2", "B2"),
    2: ("C2", "G2"),
    3: ("D2", "A2"),
    4: ("B1", "F#2"),
}

for measure_number, (pulse, leap) in pattern.items():
    score.measure(measure_number)
    ostinato(cello, pulse, leap)

score.write("ostinato-engine.musicxml")
```

## 8. Generated Melody Plus Chordal Accompaniment

Put the melody and harmony in dictionaries, then build the score from those structures.

```python
from maestroxml import Score

score = Score(title="Lead Sheet Skeleton")
melody = score.add_part("Melody", instrument="flute")
piano = score.add_part("Piano", instrument="piano")
right = piano.voice(1, staff=1)
left = piano.voice(1, staff=2)

score.measure(1)
score.time_signature("4/4")
score.key_signature("C major")

melody_cells = {
    1: ["E5", "G5", "A5", "G5"],
    2: ["F5", "E5", "D5", "C5"],
    3: ["G5", "A5", "G5", "E5"],
    4: ["D5", "C5", "B4", "C5"],
}
chords = {
    1: (["C4", "E4", "G4"], ["C2", "G2"]),
    2: (["F4", "A4", "C5"], ["F2", "C3"]),
    3: (["G4", "B4", "D5"], ["G2", "D3"]),
    4: (["C4", "E4", "G4"], ["C2", "G2"]),
}

for measure_number in range(1, 5):
    score.measure(measure_number)
    melody.notes("quarter", melody_cells[measure_number])
    right.chord("half", chords[measure_number][0])
    right.chord("half", chords[measure_number][0])
    for bass_pitch in chords[measure_number][1]:
        left.note("half", bass_pitch)

score.write("lead-sheet-skeleton.musicxml")
```

## 9. Custom Part Without A Preset

You can build parts with custom staves and clefs even if they are not covered by a preset.

```python
from maestroxml import Score

score = Score(title="Custom Ensemble")
manual = score.add_part(
    "Manuals",
    abbreviation="Man.",
    staves=2,
    clefs=["treble", "bass"],
)

upper = manual.voice(1, staff=1)
lower = manual.voice(1, staff=2)

score.measure(1)
score.time_signature("4/4")
score.key_signature("C major")
upper.chord("whole", ["C4", "E4", "G4", "C5"])
lower.note("whole", "C2")

score.write("custom-ensemble.musicxml")
```

## 10. Import A MusicXML File For Editing

Use the importer when the starting point is an existing MusicXML file instead of handwritten Python.

```python
from maestroxml import musicxml_to_python

code = musicxml_to_python(
    "input.musicxml",
    output_path="edited.musicxml",
)

print(code)
```

Typical workflow:

```python
from pathlib import Path
from maestroxml import musicxml_to_python

python_code = musicxml_to_python("input.musicxml")
Path("edit_score.py").write_text(python_code, encoding="utf-8")
```

Then edit `edit_score.py` and run it to produce a new MusicXML file.

## Example Design Tips

- Keep musical cells in lists and dictionaries.
- Use small helper functions for patterns like arpeggios, cadences, and ostinati.
- Use `chord(...)` only when pitches are truly simultaneous in one voice.
- Use separate voices or staves when rhythms differ independently.
- Let `score.measure()` and loops control form.
- If a request requires unsupported notation, document the limitation instead of inventing an API that does not exist.
