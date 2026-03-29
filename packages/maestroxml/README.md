# maestroxml

`maestroxml` is a small, standard-library-only Python package for writing MusicXML 4.0 from Python code instead of manually assembling XML tags.

It can also translate an existing MusicXML file back into editable Python that uses the `maestroxml` API. Unsupported MusicXML details are intentionally skipped instead of being represented with raw XML escape hatches.

## What It Can Do

- build score-partwise MusicXML from Python objects and method calls
- support common part setup such as title, composer, parts, key, and time
- write notes, rests, chords, tuplets, ties, slurs, articulations, and directions
- handle multi-staff and multi-voice score output
- import supported MusicXML back into editable Python that uses the `maestroxml` API

## What It Is Not

- not a full engraving engine
- not the final long-term product contract between the service and plugin
- not a MuseScore plugin integration layer

## Documentation

- `docs/getting-started.md`
- `docs/api-reference.md`
- `docs/examples.md`

## Important Paths

- `src/maestroxml/core.py`: score model and XML serialization logic
- `src/maestroxml/importer.py`: MusicXML-to-Python import helpers
- `tests/test_maestroxml.py`: package-level behavior tests
- `tests/golden/`: golden MusicXML fixtures

## Boundaries

- Keep notation serialization logic here.
- Do not put OpenAI prompting logic here.
- Do not put FastAPI or frontend runtime code here.
- If the product moves from MusicXML artifacts to score actions, this package can still remain a useful internal tool or standalone library.

## Development

Run the package tests with:

```bash
.venv/bin/python -m unittest packages/maestroxml/tests/test_maestroxml.py
```
