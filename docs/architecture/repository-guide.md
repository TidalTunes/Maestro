# Repository Guide

This document explains where code should live in the current Maestro repository.

## Active Runtime Shape

1. The desktop UI collects prompt text and optional humming input.
2. The desktop runtime either calls the service or uses the prompt-to-score shim that still powers desktop score generation.
3. Shared packages handle prompt shaping, code validation, score planning, bridge transport, and humming transcription.
4. The MuseScore plugin assets apply bridge requests inside MuseScore.

## Module Responsibilities

### `apps/frontend-desktop`

- Hosts the active PyQt user interface.
- Packages the current `maestro_gui.py` experience inside `Maestro.app`.
- Owns desktop-only concerns such as windowing, plugin installation, and bundled resource lookup.

### `apps/service`

- Hosts the FastAPI app.
- Owns HTTP request handling, service bootstrap, and OpenAI client wiring for the service path.

### `apps/plugin`

- Holds the canonical MuseScore plugin assets shipped with Maestro.
- Is the source of truth for `Maestro Plugin` files copied into MuseScore.

### `packages/agent-core`

- Holds reusable prompt-building, reference-loading, guard, and runtime-runner logic.
- Should stay decoupled from any single host process.

### `packages/maestroxml`

- Provides the score builder and delta-action planning layer.
- Supports MusicXML import into editable Python.

### `packages/humming-detector`

- Provides humming transcription and the standalone recorder utility.

### `packages/maestro-musescore-bridge`

- Provides the Python client for the file-based MuseScore bridge.
- Owns bridge protocol handling and action submission helpers.

### `contracts/`

- Stores language-neutral interface definitions.
- `service-api` describes the live HTTP service.
- `score-actions` describes the planned structured plugin boundary.

### `agent/`

- Keeps only the small prompt-to-score generation shim still imported by the desktop app.
- Reuses maintained references from `skills/maestroxml-sheet-music` and `packages/maestroxml/docs`.
- Should not become a second home for shared product logic.

## Placement Rules

- Put UI host code in `apps/frontend-desktop`.
- Put service/bootstrap code in `apps/service`.
- Put MuseScore plugin assets in `apps/plugin`.
- Put reusable logic in `packages/`.
- Put interface schemas in `contracts/`.
- Put prompt-to-score shim code in `agent/` only when the desktop generation path still depends on it.
