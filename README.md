# Maestro Monorepo

Maestro is being restructured into a merge-safe monorepo for three major areas of work:

- `apps/frontend-desktop`: the current PyQt desktop frontend promoted from `origin/main`
- `apps/service`: the local FastAPI service for prompt orchestration, humming capture, and OpenAI calls
- `apps/plugin`: the future home for the MuseScore plugin integration

Shared code now lives under `packages/`, and cross-language contracts live under `contracts/`.

## What The Project Is Trying To Become

The long-term product shape is:

- a frontend that lets a composer type or record musical intent
- a local service that turns that intent into safe, structured music-edit plans
- a MuseScore plugin that applies those edits directly through the MuseScore API

The current codebase is in a transition phase. Some pieces are already active, some are still placeholders, and some legacy experiments are preserved for reference.

## Repository Map

| Path | Role | Current Capability |
| --- | --- | --- |
| `apps/frontend-desktop` | Active desktop UI shell | PyQt conversation-style interface with text input, audio preview widgets, loading states, and a stubbed AI response hook |
| `apps/service` | Active local backend | FastAPI endpoints for generation, humming start/stop, OpenAI orchestration, and generated-code execution |
| `apps/plugin` | Future MuseScore integration | Reserved destination for the real plugin that will consume score-action contracts and perform score edits |
| `packages/agent-core` | Shared LLM/domain logic | Prompt construction, reference loading, output validation, filename sanitization, and generated-code execution helpers |
| `packages/maestroxml` | Shared notation library | MusicXML writing and MusicXML-to-Python import support |
| `packages/humming-detector` | Shared audio analysis package | Pitch tracking and coarse rhythm extraction for hummed melodies |
| `contracts/service-api` | Current interface contract | OpenAPI and JSON Schema definitions for the running HTTP service |
| `contracts/score-actions` | Future interface contract | Versioned schema stubs for structured score-edit actions |
| `legacy` | Preserved experiments | Old static UI and plugin experiments kept to avoid destructive cleanup during migration |

## Where To Read Next

- Repository structure and ownership: `docs/architecture/repository-guide.md`
- Old-to-new path mapping: `docs/architecture/migration-map.md`
- Integration boundary notes: `docs/integration/README.md`

## Transitional Paths

The old top-level `Agent/`, `maestro_gui.py`, and `pluginExperiment/` paths are intentionally preserved during this migration. They should be treated as compatibility or legacy paths while active development moves into the new app/package layout.
