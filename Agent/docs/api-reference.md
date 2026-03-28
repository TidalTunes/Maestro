# API Reference

This document describes the current public API of `maestroxml`.

For workflow guidance, see [Getting Started](getting-started.md). For larger scores and generation patterns, see [Examples](examples.md).

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

Returns a Python source string that recreates the supported parts of the MusicXML file using the `maestroxml` API.

Supported input roots:

- `score-partwise`
- `score-timewise`

The importer is intentionally lossy. Unsupported notation is ignored instead of being expressed as raw XML.

### `musicxml_string_to_python(...)`

```python
musicxml_string_to_python(xml_text, *, output_path=None)
```

Like `musicxml_to_python(...)`, but accepts MusicXML text directly instead of reading a file.

## Score

### Constructor

```python
Score(*, title=None, composer=None, lyricist=None, rights=None)
```

Arguments:

- `title`: score title; written to both `<work-title>` and `<movement-title>`
- `composer`: written as a MusicXML creator with `type="composer"`
- `lyricist`: written as a MusicXML creator with `type="lyricist"`
- `rights`: written to `<rights>`

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

- `name`: displayed part name
- `instrument`: optional preset key such as `"violin"` or `"piano"`
- `abbreviation`: optional override for the printed part abbreviation
- `staves`: optional staff count override
- `clefs`: optional iterable of clef names or `(sign, line)` tuples

Notes:

- If `instrument` matches a preset, the preset fills in abbreviation, staff count, clefs, and instrument name unless you override them.
- If you add a part after measures already exist, empty measures are created automatically so all parts stay synchronized.

### `measure(...)`

```python
score.measure(number=None)
```

Selects the active measure and returns the `Score`.

Behavior:

- `score.measure(1)` selects measure 1.
- `score.measure()` advances by one measure.
- The first call to `score.measure()` with no argument starts at measure 1.

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

This is score-level sticky state. Once set, it stays active until changed.

### `key_signature(...)`

```python
score.key_signature(signature, mode=None)
```

Accepted forms:

- `score.key_signature("C major")`
- `score.key_signature("A minor")`
- `score.key_signature(2, mode="major")`
- `score.key_signature(-3, mode="minor")`

This is score-level sticky state. Once set, it stays active until changed.

### `to_string()`

```python
xml_text = score.to_string()
```

Returns the full MusicXML document as a string, including:

- XML declaration
- MusicXML 4.0 doctype
- `<score-partwise version="4.0">`

Raises `ValueError` if the score has no parts or no measures.

### `write(path)`

```python
path_obj = score.write("piece.musicxml")
```

Writes the MusicXML document to disk and returns a `Path`.

## Part

`Part` is the ergonomic API for the common case: voice 1 on staff 1.

### `measure(...)`

```python
part.measure(number=None)
```

Convenience wrapper around `score.measure(...)`. It returns the `Part`.

### `note(...)`

```python
part.note(duration, pitch, **kwargs)
```

Adds one note to voice 1, staff 1.

### `notes(...)`

```python
part.notes(duration, pitches, **kwargs)
```

Adds a sequence of single notes with the same duration and options.

### `rest(...)`

```python
part.rest(duration, **kwargs)
```

Adds a rest to voice 1, staff 1.

### `chord(...)`

```python
part.chord(duration, pitches, **kwargs)
```

Adds a simultaneous chord to voice 1, staff 1.

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

### `clef(...)`

```python
part.clef(clef, staff=1)
```

Changes the clef for the active measure on the selected staff.

Accepted values:

- preset names: `"treble"`, `"bass"`, `"alto"`, `"tenor"`, `"percussion"`
- explicit tuples: `("G", 2)`, `("F", 4)`, `("C", 3)`

### Repeat Methods

```python
part.repeat_start()
part.repeat_end(times=None)
part.ending(number, type)
```

Supported ending types:

- `"start"`
- `"stop"`
- `"discontinue"`

### `voice(...)`

```python
cursor = part.voice(number, staff=1)
```

Returns a `VoiceCursor` for the given voice/staff stream.

Use it for:

- piano right and left hands
- polyphonic writing in a single staff
- staff-specific directions

## VoiceCursor

`VoiceCursor` exposes the same note/chord/rest and direction methods as `Part`, but writes into a specific voice/staff stream.

Example:

```python
piano = score.add_part("Piano", instrument="piano")
right = piano.voice(1, staff=1)
left = piano.voice(1, staff=2)

right.notes("quarter", ["C4", "E4", "G4", "C5"])
left.note("half", "C2")
left.note("half", "G2")
```

## Common Note And Chord Keyword Arguments

These kwargs are accepted by `VoiceCursor.note(...)` and `VoiceCursor.chord(...)`. The `Part` methods forward directly to the same implementation.

### `dots`

```python
part.note("quarter", "C5", dots=1)
```

Adds one or more dots to the base duration.

### `tuplet`

```python
part.note("eighth", "C5", tuplet=(3, 2))
part.note("16th", "D5", tuplet=(5, 4, "16th"))
```

Accepted forms:

- `(actual_notes, normal_notes)`
- `(actual_notes, normal_notes, normal_type)`

### `tie`

```python
part.note("quarter", "A4", tie="start")
part.note("quarter", "A4", tie="stop")
part.note("quarter", "A4", tie=("stop", "start"))
part.note("quarter", "A4", tie="continue")
```

`"continue"` is shorthand for `("stop", "start")`.

### `slur`

```python
part.note("quarter", "A4", slur="start")
part.note("quarter", "A4", slur="stop")
part.note("quarter", "A4", slur=("stop", "start"))
part.note("quarter", "A4", slur="continue")
```

`"continue"` is shorthand for `("stop", "start")`.

### `articulations`

```python
part.note("quarter", "C5", articulations=["staccato", "accent"])
```

Supported articulations:

- `accent`
- `strong-accent`
- `staccato`
- `tenuto`
- `detached-legato`
- `staccatissimo`
- `spiccato`
- `scoop`
- `plop`
- `doit`
- `falloff`
- `breath-mark`
- `caesura`
- `stress`
- `unstress`
- `soft-accent`

### `accidental`

```python
part.note("quarter", "F5", accidental="natural")
```

This controls the explicit MusicXML `<accidental>` element. It is separate from pitch parsing and is passed through as written.

### `beams`

```python
part.note("eighth", "C5", beams=["begin"])
part.note("eighth", "D5", beams=["continue"])
part.note("eighth", "E5", beams=["end"])
```

Beam tags are passed through in order as MusicXML `<beam number="...">` elements.

## Rest Keyword Arguments

`rest(...)` accepts:

- `dots`
- `tuplet`
- `beams`

Example:

```python
part.rest("quarter", dots=1)
part.rest("eighth", tuplet=(3, 2))
```

## Supported Pitch Syntax

Pitch strings are parsed as:

- step letter: `A` through `G`
- optional accidental markers: `#`, `##`, `b`, `bb`, or `n`
- octave number

Examples:

- `C4`
- `F#5`
- `Bb3`
- `Cn4`
- `E##5`
- `Gbb2`

## Supported Duration Names

- `whole`
- `half`
- `quarter`
- `eighth`
- `8th`
- `16th`
- `sixteenth`
- `32nd`
- `thirty-second`
- `64th`
- `sixty-fourth`

## Instrument Presets

Preset keys and defaults:

| preset | abbreviation | staves | clefs |
| --- | --- | ---: | --- |
| `violin` | `Vln.` | 1 | `treble` |
| `viola` | `Vla.` | 1 | `alto` |
| `cello` | `Vc.` | 1 | `bass` |
| `piano` | `Pno.` | 2 | `treble`, `bass` |
| `flute` | `Fl.` | 1 | `treble` |
| `clarinet` | `Cl.` | 1 | `treble` |
| `voice` | `V.` | 1 | `treble` |

## Supported Dynamic Tags

The package emits MusicXML dynamic tags for the following values:

- `pppppp`
- `ppppp`
- `pppp`
- `ppp`
- `pp`
- `p`
- `mp`
- `mf`
- `f`
- `ff`
- `fff`
- `ffff`
- `fffff`
- `ffffff`
- `fp`
- `fz`
- `sf`
- `sfp`
- `sfpp`
- `sfz`
- `sffz`
- `rf`
- `rfz`
- `sfzp`
- `pf`

If you pass another dynamic string, it is emitted as `<other-dynamics>`.

## MusicXML Behavior Notes

- Measures are serialized for every part from 1 through the highest measure number used anywhere in the score.
- Empty measures are still emitted.
- `<attributes>` are only emitted in measure 1 and whenever time, key, or clef changes.
- `<backup>` is emitted automatically when multiple streams must share the same measure timeline.
- Divisions are computed automatically from the rhythmic material present in the score.

## Current Limits

`maestroxml` currently does not provide:

- MusicXML parsing or round-tripping
- `.mxl` packaging
- lyric handling
- harmony/chord-symbol objects
- grace notes
- transposing instrument support
- microtonal notation
- advanced page or system layout controls
- validation that each measure adds up to the current time signature

Importer-specific limitations:

- unsupported MusicXML elements are skipped
- imported code aims for a simple editable representation, not exact source preservation
- score-wide time/key are inferred from the first available measure-level values
- measure numbers may be normalized when the source numbering cannot be represented cleanly
