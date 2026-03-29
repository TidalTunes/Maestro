# Examples

These examples show the intended `maestroxml` workflow after the bridge refactor: build music in Python, inspect the action plan if useful, then apply it to a live MuseScore score.

For live edits to an already-open score, use the same score-shaped API on a cloned shell and export only `to_delta_actions(base_score)` instead of replaying the whole imported score.

For the full method list, see [API Reference](api-reference.md). For the step-by-step workflow, see [Getting Started](getting-started.md).

## 1. Short Melody With Action Inspection

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
flute.note("quarter", "A4")
flute.note("eighth", "C5", tuplet=(3, 2), articulations=["staccato"])
flute.note("eighth", "D5", tuplet=(3, 2))
flute.note("eighth", "E5", tuplet=(3, 2))
flute.note("quarter", "F5")
flute.note("quarter", "G5")

print(score.to_string())
```

## 2. Apply A Quartet Built From Loop Data

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

score.apply()
```

## 3. Piano Writing Across Two Staves

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

score.write("broken-chords-actions.json")
```

## 4. Block Chords And Helper Functions

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
```

## 5. Independent Voices In One Part

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

actions = score.to_actions()
```

## 6. Repeat Helpers And Bridge-Limit Detection

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

print(score.unsupported_features())
print(score.to_string())
```

The builder keeps the repeat information, but the current bridge backend can only preserve a repeat-count hint, not full repeat barline or volta notation.

## 7. Save A Reusable Action Plan

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

score.write("ostinato-actions.json")
```

## 8. Import MusicXML Into Editable Python

```python
from maestroxml import musicxml_to_python

python_code = musicxml_to_python(
    "input.musicxml",
    output_path="input-actions.json",
)

print(python_code)
```

The generated code rebuilds the supported score content with `Score`, `Part`, and `voice(...)`. Unsupported MusicXML detail is skipped to keep the result editable.
