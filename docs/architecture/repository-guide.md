# Repository Guide

This document explains what each major module in the repository is for, what it can do today, and where future work should land.

## Active System Shape

1. A user-facing frontend captures text or audio intent.
2. The local service turns that input into an LLM request and validates the response.
3. Shared packages provide notation and humming-analysis capabilities.
4. The future plugin will apply structured score edits directly inside MuseScore.

## Module Responsibilities

### `apps/frontend-desktop`

- Hosts the current PyQt user interface.
- Supports typed messages, audio-preview UI, playback widgets, loading states, and conversation rendering.
- Currently acts as a frontend shell with a stubbed `on_prompt_submit` hook rather than a finished service integration.

### `apps/service`

- Hosts the current FastAPI backend.
- Exposes `/api/generate`, `/api/humming/start`, `/api/humming/stop`, and `/healthz`.
- Owns process-level configuration, OpenAI access, and wiring between HTTP requests and shared packages.
- Returns Python and MusicXML artifacts today; this is expected to evolve toward structured score actions later.

### `apps/plugin`

- Reserved for the real MuseScore integration.
- Will eventually consume `contracts/score-actions` and translate them into MuseScore API operations.
- Should remain the only place that knows MuseScore-specific runtime details.

### `packages/agent-core`

- Holds prompt-building logic, reference loading, generated-code safety rules, and helper routines for executing generated score code.
- Should stay independent of FastAPI request handling and MuseScore plugin details.

### `packages/maestroxml`

- Provides the score-writing abstraction used by the current generation flow.
- Supports MusicXML serialization and limited MusicXML-to-Python import.
- Is valuable as a reusable notation package even if the product contract later shifts away from MusicXML artifacts.

### `packages/humming-detector`

- Provides note extraction from recorded humming audio.
- Includes a small recorder/test utility in addition to the detector API itself.
- Should remain reusable outside the service process.

### `contracts/service-api`

- Defines the current HTTP payload shapes so frontend and service work do not depend on internal Python model layouts.

### `contracts/score-actions`

- Defines the future structured edit envelope between service and plugin.
- Exists now to stabilize the integration seam before the implementation is complete.

### `legacy`

- Preserves earlier experiments for reference.
- Exists to reduce merge risk during repository restructuring.

## Default Placement Rules

- New UI host code goes in `apps/frontend-desktop` or `apps/plugin`.
- New HTTP/bootstrap/runtime code goes in `apps/service`.
- New reusable domain logic goes in `packages/`.
- New interface payload definitions go in `contracts/`.
- Old experiments stay in `legacy/`.
