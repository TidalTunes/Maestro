# Migration Map

This repository is in a non-destructive migration from a flat experimental layout into a monorepo.

## Active Destinations

- `maestro_gui.py` -> `apps/frontend-desktop/src/maestro_desktop/app.py`
- `Agent/app/main.py` -> `apps/service/src/maestro_service/api/app.py`
- `Agent/app/agent.py` -> `apps/service/src/maestro_service/bootstrap/generator.py` and `packages/agent-core/src/maestro_agent_core/generation.py`
- `Agent/app/guard.py` -> `packages/agent-core/src/maestro_agent_core/guard.py`
- `Agent/app/context/*` -> `packages/agent-core/src/maestro_agent_core/context/*`
- `Agent/src/maestroxml/*` -> `packages/maestroxml/src/maestroxml/*`
- `Agent/tests/test_maestroxml.py` -> `packages/maestroxml/tests/test_maestroxml.py`
- `Agent/tests/golden/*` -> `packages/maestroxml/tests/golden/*`
- `Agent/detector/*` -> `packages/humming-detector/src/maestro_humming_detector/*`
- `Agent/detector/tests/*` -> `packages/humming-detector/tests/*`
- `Agent/app/static/*` -> `legacy/static-web-prototype/*`
- `pluginExperiment/live_swapper.qml` -> `legacy/plugin-experiment/live_swapper.qml`

## Transitional Rule

During this pass, old paths remain in place for compatibility and history preservation. New development should target `apps/`, `packages/`, and `contracts/`.
