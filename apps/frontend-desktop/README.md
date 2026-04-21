# Maestro Desktop Frontend

This app contains the current active PyQt desktop frontend that was promoted from `origin/main`.

## What It Can Do

- render a conversation-style desktop interface
- preserve the current `maestro_gui.py` live-edit experience inside the packaged app
- accept typed prompts plus optional hummed input
- show microphone and audio-preview UI elements
- play back recorded preview audio inside the window
- show loading states and live-edit results
- install and verify the bundled MuseScore plugin for the macOS app build
- persist non-secret provider settings locally and store an OpenAI API key in macOS Keychain when available
- write local structured logs and copy sanitized diagnostics from the UI

## Current State

This app is the active desktop boundary and now wraps the current `maestro_gui.py` runtime rather than the earlier simplified shell. The packaged entrypoint delegates to `gui_runtime.py`, while the root `maestro_gui.py` file remains a thin local/dev wrapper.

## Important Files

- `src/maestro_desktop/app.py`: packaged entrypoint wrapper
- `src/maestro_desktop/gui_runtime.py`: current Maestro UI and live-edit workflow
- `src/maestro_desktop/runtime_support.py`: repo-vs-bundled resource and path resolution
- `src/maestro_desktop/settings_store.py`: provider settings persistence and macOS Keychain-backed key storage
- `src/maestro_desktop/diagnostics.py`: local log file handling and clipboard diagnostics export
- `src/maestro_desktop/plugin_setup.py`: bundled MuseScore plugin installer and bridge checks
- `tests/test_import.py`: import smoke test for the promoted frontend package

## Boundaries

- Keep desktop UI widgets, animation behavior, and host-specific window logic here.
- Do not put FastAPI request handling here.
- Do not put MuseScore plugin runtime code here.
- Shared logic should move into `packages/` when it is no longer specific to this desktop app.
