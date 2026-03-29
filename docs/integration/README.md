# Integration Notes

This directory is reserved for integration-specific documentation as the frontend, service, and plugin codebases converge.

Near-term shared boundaries:

- `contracts/service-api`
- `contracts/score-actions`

## Current Integration Story

- `apps/frontend-desktop` is the active UI shell.
- `apps/service` is the active backend boundary.
- `apps/plugin` is the future destination for direct MuseScore integration.

## Expected Long-Term Flow

1. Frontend captures a text prompt and optionally audio context.
2. Service interprets the request and produces a structured plan.
3. Plugin consumes the plan and applies score edits through MuseScore.

The repository still contains older artifact-based behavior, especially around MusicXML generation. Those pieces remain useful during the transition, but the integration direction is now centered on contracts rather than direct cross-module assumptions.
