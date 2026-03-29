<<<<<<< HEAD
# Maestro

AI Compose Assistant for MuseScore 4

A floating overlay GUI panel for AI-assisted music composition.

## Features

- Floating, always-on-top window that matches MuseScore 4's aesthetic
- Classical serif typography (Palatino/Georgia)
- Wavy text input effect
- Animated music staff loading indicator with rippling notes
- Typewriter effect for AI responses
- Draggable window with minimize/close controls
=======
# maestroxml

`maestroxml` is a small, standard-library-only Python package for writing MusicXML 4.0 from Python code instead of manually assembling XML tags.

It can also translate an existing MusicXML file back into editable Python that uses the `maestroxml` API. Unsupported MusicXML details are intentionally skipped instead of being represented with raw XML escape hatches.

It is built around a stateful composition workflow:

- `Score` tracks the current measure and score-wide state such as time and key.
- `Part` writes the simple one-voice case directly.
- `voice(number, staff=...)` exposes explicit voice/staff cursors when you need piano notation or independent lines.
- The serializer converts those calls into `score-partwise` MusicXML with measures, attributes, directions, chords, ties, slurs, articulations, repeats, and multi-staff `<backup>` elements.
>>>>>>> 2bb576b (Initial agentic system module)

## Installation

```bash
<<<<<<< HEAD
pip install PyQt6
python maestro_gui.py
```

## Usage

1. Run the application
2. Type your composition request in the input field
3. Press Enter or click the arrow button to submit
4. Watch the music staff animation while processing
5. View the AI response in the summary area

## API

```python
# Override this method to connect your AI backend
def on_prompt_submit(self, prompt_text: str) -> str:
    # Your AI call here
    return summary_text

# Public methods
window.set_loading(True/False)  # Toggle loading animation
window.set_summary(text)        # Update summary display
window.get_prompt()             # Get current input text
window.clear_history()          # Clear conversation history
```

## License

MIT
=======
pip install -e .
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [Examples](docs/examples.md)

## Quick Example

```python
from maestroxml import Score

score = Score(title="My Piece", composer="Me")

violin1 = score.add_part("Violin I", instrument="violin")
violin2 = score.add_part("Violin II", instrument="violin")
viola = score.add_part("Viola", instrument="viola")
cello = score.add_part("Cello", instrument="cello")

score.measure(1)
score.time_signature("4/4")
score.key_signature("C major")

violin1.notes("quarter", ["C4", "E4", "G4"])
violin1.notes("eighth", ["A4", "B4"])
violin1.rest("quarter")

score.measure(2)
violin1.note("whole", "C5")

chord = ["G3", "B4", "D5"]
for measure_number in range(3, 9):
    score.measure(measure_number)
    cello.note("whole", chord[0])
    viola.note("whole", chord[1])
    violin2.note("whole", chord[2])

score.write("my_piece.musicxml")
```

## Import Existing MusicXML Into Python

```python
from maestroxml import musicxml_to_python

code = musicxml_to_python("existing.musicxml", output_path="edited.musicxml")
print(code)
```

The returned string is normal Python that creates a `score` object with the supported parts of the original file. This is intended as an editing workflow:

1. translate MusicXML to Python
2. edit the generated code
3. run it to produce the updated MusicXML

## Core Ideas

- Start each measure explicitly with `score.measure(...)`.
- Set time and key only when they change. They stay active until changed again.
- Use `Part.note`, `notes`, `rest`, and `chord` for the common monophonic case.
- Use `part.voice(number, staff=...)` when one part needs multiple voices or multiple staves.
- Use normal Python data structures, loops, and helper functions to generate repeated music.

## What The Package Supports

- score metadata: title, composer, lyricist, rights
- parts and part presets: violin, viola, cello, piano, flute, clarinet, voice
- measures with sticky time signatures and key signatures
- notes, rests, chords, dots, tuplets, ties, slurs, articulations, and beam tags
- tempo marks, text directions, dynamics, and wedges
- local clef changes
- repeat barlines and first/second endings
- multi-staff and multi-voice MusicXML output
- lossy MusicXML-to-Python translation for supported notation

## Current Limits

`maestroxml` is a writer, not a full engraving system. It does not currently support:

- reading or editing existing MusicXML files
- compressed `.mxl` output
- lyrics
- chord-symbol harmony objects
- grace notes
- transposing-instrument logic
- microtonal notation
- advanced layout/page engraving controls
- automatic measure-balance validation against the time signature
- perfect round-tripping of unsupported MusicXML details during import

## Development

Run the test suite with:

```bash
.venv/bin/python -m unittest discover -s tests
```
>>>>>>> 2bb576b (Initial agentic system module)
