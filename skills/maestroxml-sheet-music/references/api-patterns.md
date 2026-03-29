# API Patterns

## Mental Model

`maestroxml` is a score-shaped planning layer over `maestro-musescore-bridge`.

- `to_actions()` is for full score plans or append-only plans.
- `to_delta_actions(base_score)` is for live edits against an existing score.
- Imported MusicXML or bridge snapshots exist to help the model understand the current score as code.

## New Score Pattern

```python
from maestroxml import Score

score = Score(title="Miniature")
flute = score.add_part("Flute", instrument="flute")

score.measure(1)
score.time_signature("4/4")
flute.note("quarter", "C5")
flute.note("quarter", "D5")

actions = score.to_actions()
```

## Live Edit Pattern

```python
base_score = score_from_current_context
edit_score = base_score.clone_shell()

flute = edit_score.parts[0]
edit_score.measure(4)
flute.note("quarter", "G5")
flute.dynamic("mf")

actions = edit_score.to_delta_actions(base_score)
```

Key rule: the edit score is a blank change plan, not a replay of the existing score.

## Writing Rules

- Always call `score.measure(...)` before note or direction entry.
- Use named part and voice globals from the current score context when they exist.
- Use `part.note(...)` for single pitches and `part.chord(...)` for simultaneous pitches.
- Use `part.rest(...)` for silence.
- Add measures or parts only when the user explicitly asks for them or when the requested change needs them.
- Preserve existing musical material by omission. Do not rewrite it.

## Avoid

- Recreating the entire current score inside `apply_changes(score)`.
- Calling `score.apply()`, `score.write()`, `score.to_actions()`, or `score.to_string()` from generated edit code.
- Importing extra modules.
- Inventing unsupported duration labels.
