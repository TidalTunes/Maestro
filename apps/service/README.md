# Maestro Service

This app contains the local FastAPI service for prompt orchestration, generated-code execution, and humming capture.

## What It Can Do

- expose a local HTTP API for generation and humming capture
- call OpenAI with the current Maestro prompting strategy
- load curated reference material before generation
- validate generated Python before it is executed
- execute generated score code against the `maestroxml` package
- return MusicXML plus the generated Python source to clients

## Current Endpoints

- `POST /api/generate`: accepts prompt input and optional hummed notes
- `POST /api/humming/start`: starts the recorder adapter
- `POST /api/humming/stop`: stops recording and returns detected notes
- `GET /healthz`: lightweight health check

## Important Files

- `src/maestro_service/api/app.py`: FastAPI app and endpoint definitions
- `src/maestro_service/bootstrap/generator.py`: OpenAI orchestration and generation flow
- `src/maestro_service/bootstrap/humming.py`: service-side humming adapter
- `src/maestro_service/bootstrap/config.py`: environment-driven runtime configuration
- `tests/test_service_app.py`: service endpoint tests

## Boundaries

- Keep HTTP wiring, process config, and OpenAI client calls here.
- Keep shared prompt logic, validation rules, and score-code execution helpers in `packages/agent-core`.
- Keep MuseScore plugin logic out of this app.
- The service returns MusicXML artifacts today, but the long-term plugin contract is expected to shift toward `contracts/score-actions`.
