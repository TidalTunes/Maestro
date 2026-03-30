# Maestro

Maestro is a Python monorepo for AI-assisted music authoring and live MuseScore editing. It combines a desktop UI, a local FastAPI service, score-planning libraries, humming transcription, and a MuseScore bridge that can apply generated edits to an open score.

The repository is mid-migration. `apps/frontend-desktop` and `apps/service` are the active application boundaries, `apps/plugin` is the planned long-term home for the MuseScore plugin app, and today's live-edit path is powered by `packages/maestro-musescore-bridge` plus the plugin files in `Plugins/`.

## What Exists Today

- A PyQt desktop frontend for prompt-driven composition and score-edit workflows
- A local FastAPI service that generates Python and MusicXML from prompts and hummed notes
- Shared packages for prompt construction, guardrails, notation planning, and humming transcription
- A working Python-to-MuseScore bridge for applying score actions to a live MuseScore session
- Versioned contracts for the current service API and the future score-action boundary

The service still returns Python and MusicXML artifacts today. The long-term direction is a structured score-action flow between the service and the eventual dedicated plugin app.

## System Shape

```text
typed prompt / hummed melody
            |
            v
desktop UI or HTTP client
            |
            +----------------------+
            |                      |
            v                      v
    apps/frontend-desktop     apps/service
            |                      |
            +----------+-----------+
                       |
                       v
              packages/agent-core
                       |
             +---------+---------+
             |                   |
             v                   v
  packages/humming-detector   packages/maestroxml
                                  |
                                  v
                  packages/maestro-musescore-bridge
                                  |
                                  v
                             Plugins/ + MuseScore
```

## Repository Layout

| Path | Role | Current state |
| --- | --- | --- |
| `apps/frontend-desktop` | Active PyQt desktop app | Current UI shell with prompt, audio, and live-edit backend plumbing |
| `apps/service` | Active FastAPI backend | Exposes generation and humming endpoints |
| `apps/plugin` | Future MuseScore host app | Reserved landing zone for the long-term plugin runtime |
| `packages/agent-core` | Shared LLM and execution logic | Builds prompts, loads references, validates code, and executes generated edits |
| `packages/maestroxml` | Shared notation layer | Builds score plans and delta actions; can import MusicXML into Python |
| `packages/humming-detector` | Shared audio analysis | Transcribes hummed melodies into note-duration strings |
| `packages/maestro-musescore-bridge` | Active MuseScore bridge package | Talks to the MuseScore plugin over a file-based protocol |
| `contracts/service-api` | Current interface contract | Schemas for the running HTTP service |
| `contracts/score-actions` | Future interface contract | Schemas for structured score-edit payloads |
| `Plugins/` | MuseScore plugin files | The bridge plugin code used by the current live-edit workflow |
| `docs/` | Repository architecture and integration docs | Explains layout, migration, and system boundaries |
| `Agent/` and `legacy/` | Transitional and historical paths | Preserved intentionally while development moves into `apps/`, `packages/`, and `contracts/` |

## Quick Start

### Prerequisites

- Python 3.10 or newer
- `pip`
- MuseScore, if you want live score editing
- An OpenAI API key, if you want generation features

This repo does not yet have a single top-level package manifest. Install the components you need in editable mode.

### Install The Active Components

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  -e packages/maestro-musescore-bridge \
  -e packages/maestroxml \
  -e packages/agent-core \
  -e packages/humming-detector \
  -e apps/service \
  -e apps/frontend-desktop
```

If you only need the backend, you can skip `apps/frontend-desktop`.

## Running The Main Pieces

### Local Service

Start the FastAPI app:

```bash
python -m uvicorn maestro_service.api.app:app --reload
```

Current endpoints:

- `POST /api/generate`
- `POST /api/humming/start`
- `POST /api/humming/stop`
- `GET /healthz`

`POST /api/generate` accepts a text prompt, an `api_key`, and optional `hummed_notes`, then returns a generated filename, Python source, and MusicXML.

### Desktop Frontend

Run the PyQt app:

```bash
python -m maestro_desktop.app
```

The desktop app is the current user-facing shell. It also contains the bridge-backed live-edit backend used to inspect an open MuseScore score, generate delta actions, and stream those actions back to MuseScore.

### MuseScore Bridge

For live score editing, install the bridge plugin files into your MuseScore plugin directory:

- `Plugins/maestro_python_bridge.qml`
- `Plugins/bridge_actions.js`
- `Plugins/score_operations.js`

Then in MuseScore:

1. Enable `Maestro Python Bridge` in the plugin manager.
2. Run `Plugins > Maestro > Python Bridge`.
3. Keep the bridge dialog open while Python or the desktop app is sending actions.

Once the package is installed, you can verify connectivity with:

```bash
maestro-musescore-bridge ping
```

If you use the desktop live-edit flow directly, set `OPENAI_API_KEY` in your shell first.

### Humming Tester

To test humming capture outside the service:

```bash
python -m maestro_humming_detector.humming_tester
```

## Configuration

The service and desktop live-edit backend share the same runtime knobs:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_MODEL` | `gpt-5.4` | Model used for generation |
| `OPENAI_REASONING_EFFORT` | `low` | Reasoning depth for OpenAI responses |
| `OPENAI_MAX_OUTPUT_TOKENS` | `20000` | Response token cap |
| `EXECUTION_TIMEOUT_SECONDS` | `20` | Timeout for generated code execution |
| `MAESTRO_SKILL_DIR` | repo skill or `~/.codex/skills/maestroxml-sheet-music` | Override prompt skill directory |
| `MAESTRO_DOCS_DIR` | `packages/maestroxml/docs` | Override local docs used as reference material |
| `MAESTRO_MAESTROXML_SRC_DIR` | `packages/maestroxml/src` | Override the `maestroxml` source tree used for execution |

The HTTP service expects an API key in the request payload. The desktop live-edit path falls back to `OPENAI_API_KEY` from the environment.

## Development

Run the repository smoke test after installing the relevant packages:

```bash
python -m unittest tests/test_monorepo_smoke.py
```

Deeper package-specific tests and usage guides live in the subproject READMEs.

## Read Next

- [Repository guide](docs/architecture/repository-guide.md)
- [Migration map](docs/architecture/migration-map.md)
- [Integration notes](docs/integration/README.md)
- [Service README](apps/service/README.md)
- [Desktop README](apps/frontend-desktop/README.md)
- [maestroxml README](packages/maestroxml/README.md)
- [maestro-musescore-bridge README](packages/maestro-musescore-bridge/README.md)

## Migration Notes

The old top-level `Agent/`, `maestro_gui.py`, and `legacy/` paths remain on purpose during the monorepo transition. New work should land in `apps/`, `packages/`, and `contracts/` unless there is a clear compatibility reason to extend an older path.
