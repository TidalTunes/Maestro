# Compatibility Map

This map shows the small number of historical entrypoints that still exist and where their maintained counterparts live.

## Desktop Entry

- `maestro_gui.py` -> thin wrapper around `apps/frontend-desktop/src/maestro_desktop/app.py`

## Score Generation Shim

- `agent/generator.py` -> prompt-to-score shim used by the desktop app
- maintained equivalents for new work:
  - `apps/service/src/maestro_service/bootstrap/generator.py`
  - `packages/agent-core/src/maestro_agent_core/generation.py`
  - `packages/agent-core/src/maestro_agent_core/guard.py`
  - `packages/agent-core/src/maestro_agent_core/context/`

## Prompt Reference Material

- `agent/generator.py` now loads maintained references from:
  - `skills/maestroxml-sheet-music/`
  - `packages/maestroxml/docs/`
  - `README.md`

## MuseScore Plugin Assets

- canonical source: `apps/plugin/assets/`
- runtime consumer: `packages/maestro-musescore-bridge`
- desktop installer: `apps/frontend-desktop/src/maestro_desktop/plugin_setup.py`
