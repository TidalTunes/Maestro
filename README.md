# Maestro

Maestro is a Python monorepo for AI-assisted composition and live MuseScore editing. The current product is a packaged desktop app with a bundled MuseScore bridge plugin, backed by shared Python packages for prompting, score planning, humming transcription, and bridge transport.

## Current Product Shape

```text
prompt / humming
       |
       v
Maestro desktop app
       |
       +----------------------+
       |                      |
       v                      v
legacy compatibility      packaged resources
generator runtime         plugin assets + docs
       |                      |
       +----------+-----------+
                  |
                  v
         packages/agent-core
                  |
        +---------+---------+
        |                   |
        v                   v
packages/humming-      packages/maestroxml
detector                     |
                              v
               packages/maestro-musescore-bridge
                              |
                              v
                    apps/plugin/assets + MuseScore
```

## Repository Layout

| Path | Role |
| --- | --- |
| `apps/frontend-desktop` | Active PyQt desktop app and packaged entrypoint |
| `apps/service` | Active FastAPI service |
| `apps/plugin` | Canonical MuseScore plugin assets shipped with Maestro |
| `packages/agent-core` | Shared prompt construction, validation, and runtime execution helpers |
| `packages/maestroxml` | Score builder, delta planner, and MusicXML import support |
| `packages/humming-detector` | Hummed melody transcription |
| `packages/maestro-musescore-bridge` | Python client for the file-based MuseScore bridge |
| `contracts/` | Language-neutral interface contracts |
| `Agent/` | Minimal compatibility runtime used by the current desktop MVP |
| `docs/` | Repository-level architecture and integration notes |
| `packaging/macos` | macOS build, notarization, and DMG scripts |

## End-User Flow

The macOS packaging flow builds a single downloadable app:

```bash
./packaging/macos/build_app.sh
```

Optional release steps:

```bash
./packaging/macos/notarize_app.sh
./packaging/macos/make_dmg.sh
```

The packaged app bundles:

- the current `maestro_gui.py` UI runtime
- the compatibility generator runtime under `Agent/`
- the MuseScore plugin assets from `apps/plugin/assets`
- local reference material and package source trees required by the MVP runtime

On first launch, `Maestro.app` can install `Maestro Plugin` into the user's MuseScore plugin directory and verify bridge connectivity.

## Developer Setup

### Prerequisites

- Python 3.10 or newer
- `pip`
- MuseScore, if you want live score editing
- an OpenAI API key for OpenAI-backed generation

### Install Editable Components

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

## Running The Main Pieces

### Desktop App

```bash
python maestro_gui.py
```

`maestro_gui.py` is a thin wrapper around the packaged desktop entrypoint.

### Local Service

```bash
python -m uvicorn maestro_service.api.app:app --reload
```

Current endpoints:

- `POST /api/generate`
- `POST /api/humming/start`
- `POST /api/humming/stop`
- `GET /healthz`

### MuseScore Plugin

The canonical plugin assets live in:

- `apps/plugin/assets/maestro_python_bridge.qml`
- `apps/plugin/assets/bridge_actions.js`
- `apps/plugin/assets/score_operations.js`

For manual setup, copy those files into your MuseScore plugin directory, then in MuseScore:

1. Enable `Maestro Plugin` in the plugin manager.
2. Run `Plugins > Maestro > Maestro Plugin`.
3. Keep the bridge dialog open while Maestro or Python is sending actions.

Once the Python package is installed, verify connectivity with:

```bash
maestro-musescore-bridge ping
```

### Humming Tester

```bash
python -m maestro_humming_detector.humming_tester
```

## Configuration

The desktop live-edit path and service share these runtime knobs:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_MODEL` | `gpt-5.4` | Model used for generation |
| `OPENAI_REASONING_EFFORT` | `low` | Reasoning depth for OpenAI responses |
| `OPENAI_MAX_OUTPUT_TOKENS` | `20000` | Response token cap |
| `EXECUTION_TIMEOUT_SECONDS` | `20` | Timeout for generated code execution |
| `MAESTRO_SKILL_DIR` | bundled skill or `~/.codex/skills/maestroxml-sheet-music` | Override prompt skill directory |
| `MAESTRO_DOCS_DIR` | packaged or local docs directory | Override reference docs used by generation |
| `MAESTRO_MAESTROXML_SRC_DIR` | packaged or local `packages/maestroxml/src` | Override the `maestroxml` source tree used for execution |

The HTTP service expects an API key in the request payload. The desktop live-edit flow falls back to `OPENAI_API_KEY` from the environment.

## Tests

Run the repository smoke test after installing the relevant packages:

```bash
python -m unittest tests/test_monorepo_smoke.py
```

Package-specific tests and operational notes live in each subproject README.

## Read Next

- [Docs overview](docs/README.md)
- [Repository guide](docs/architecture/repository-guide.md)
- [Compatibility map](docs/architecture/migration-map.md)
- [Integration notes](docs/integration/README.md)
- [Desktop README](apps/frontend-desktop/README.md)
- [Plugin README](apps/plugin/README.md)
- [Service README](apps/service/README.md)
- [Bridge README](packages/maestro-musescore-bridge/README.md)
