# Maestro Desktop Frontend

This app contains the current active PyQt desktop frontend that was promoted from `origin/main`.

## What It Can Do

- render a conversation-style desktop interface
- accept typed prompts
- show microphone and audio-preview UI elements
- play back recorded preview audio inside the window
- show loading states and staged AI responses
- act as the current visual shell for the broader Maestro product

## Current State

This app is the active frontend boundary, but it is not yet the finished product integration. The main window currently uses a stubbed `on_prompt_submit` hook, so it should be treated as the primary UI shell rather than a complete end-to-end client.

## Important Files

- `src/maestro_desktop/app.py`: the main PyQt application, widgets, and entrypoint
- `tests/test_import.py`: import smoke test for the promoted frontend package

## Boundaries

- Keep desktop UI widgets, animation behavior, and host-specific window logic here.
- Do not put FastAPI request handling here.
- Do not put MuseScore plugin runtime code here.
- Shared logic should move into `packages/` when it is no longer specific to this desktop app.
