---
name: maestroxml-sheet-music
description: Use the local maestroxml package as a score-shaped planning API for MuseScore bridge actions. Prefer it when existing scores should be understood as code and when live edits should be expressed as note, rest, chord, direction, measure, and part changes.
---

# MaestroXML Sheet Music

Use `maestroxml` as an opinionated abstraction over MuseScore score edits.

- For new scores, build the whole score in Python and export bridge actions with `to_actions()`.
- For existing live scores, treat imported `maestroxml` code as reference context, clone the score shell, add only the requested changes, and export `to_delta_actions(base_score)`.

## Quick Workflow

1. Import `Score` from `maestroxml`.
2. Create or load score-shaped context with `Score`, `Part`, and `voice(...)`.
3. Call `score.measure(...)` before writing notes, rests, chords, or directions.
4. Use `time_signature(...)` and `key_signature(...)` only when they change.
5. For live edits, build only the requested change plan and do not replay the existing score.

## Live Edit Rules

- The current score code is reference context for names, measures, part layout, and musical material.
- The runtime edit score is a blank change plan with matching existing parts, staves, voices, and measures.
- Add only the requested notes, rests, chords, directions, time signatures, key signatures, measures, or parts.
- Do not recreate existing notes, rests, chords, directions, parts, or measures unless the user explicitly asks to change them.
- Reuse named globals from the current score context when available.
- Prefer naturals and single sharps/flats over double-sharp or double-flat spellings unless the user explicitly asks for them.
- Dotted duration phrases such as `dotted quarter` or `double dotted eighth` are supported.
- Use `part.voice(number, staff=...)` for multi-staff or multi-voice work.

## Supported API Shape

- `Score(title=..., composer=..., lyricist=..., rights=...)`
- `score.add_part(name, instrument=..., abbreviation=..., staves=..., clefs=...)`
- `score.measure(number=None)`
- `score.time_signature(...)`
- `score.key_signature(...)`
- `part.note(...)`, `part.notes(...)`, `part.rest(...)`, `part.chord(...)`
- `part.tempo(...)`, `part.dynamic(...)`, `part.text(...)`, `part.wedge(...)`
- `score.clone_shell()`
- `score.to_actions(...)`
- `score.to_delta_actions(base_score)`

## Limits

- `maestroxml` is not a raw MusicXML escape hatch.
- Live-edit delta planning is additive for existing content; it does not remove existing parts or measures.
- Unsupported bridge features should be simplified instead of invented.

## References

- Open [references/api-patterns.md](references/api-patterns.md) for the edit contract and API surface.
- Open [references/examples.md](references/examples.md) for score-building and live-edit examples.
