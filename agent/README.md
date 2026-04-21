# Agent Score Generation Shim

This directory holds the small prompt-to-score generation shim still used by the desktop app's
`generate_code()` path.

## What Lives Here

- `generator.py`: OpenAI-backed prompt-to-score generation that returns Python `maestroxml` code
- `__init__.py`: public exports for the shim

## What It Uses

This shim intentionally reuses maintained shared components instead of carrying its own private
copies of them:

- reference loading from `packages/agent-core`
- curated skill material from `skills/maestroxml-sheet-music`
- score documentation from `packages/maestroxml/docs`

## Boundary

`agent/` is not a second product stack. It only preserves the desktop app's prompt-to-score
generation interface while the rest of Maestro continues to live in `apps/`, `packages/`, and
`contracts/`.
