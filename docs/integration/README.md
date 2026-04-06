# Integration Notes

This directory documents how the current Maestro components fit together.

## Live Integration Story

- `apps/frontend-desktop` is the user-facing app and packaged entrypoint.
- `apps/plugin/assets` provides the MuseScore plugin files installed into the user's plugin directory.
- `packages/maestro-musescore-bridge` talks to that plugin over the file-based bridge directory.
- `packages/maestroxml` turns score intent into bridge actions.
- `packages/agent-core` validates and executes generated score code.
- `apps/service` exposes the same generation stack over HTTP.

## Current Boundaries

- `contracts/service-api` documents the live HTTP service contract.
- `contracts/score-actions` documents the planned structured score-edit contract.

## Important Operational Notes

1. The desktop app and the manual Python workflow both require `Maestro Plugin` to be open in MuseScore.
2. The packaged desktop MVP still depends on the compatibility generator in `Agent/`.
3. The canonical plugin source is `apps/plugin/assets`, not the old top-level `Plugins/` layout.
