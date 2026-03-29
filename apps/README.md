# Apps

This directory contains end-user entrypoints and runtime-specific application shells.

## Current Apps

- `frontend-desktop`: the active PyQt UI shell
- `service`: the active FastAPI backend
- `plugin`: the reserved landing zone for the real MuseScore plugin

## Ownership Rule

Put code here when it is tied to a runtime host:

- desktop UI concerns
- FastAPI process/bootstrap concerns
- MuseScore plugin concerns

Do not put cross-app business logic here if it can live in `packages/`.
