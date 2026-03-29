# Score Actions Contract

This directory is the future-facing contract boundary between the service and the MuseScore plugin.

For this restructuring pass, the live service still returns MusicXML and Python code. These schemas exist so the plugin integration has a stable destination when structured score edits replace the current artifact-based flow.

## What This Contract Is For

- describing score edits in a runtime-neutral way
- keeping MuseScore API details out of the service layer
- giving the plugin a versioned payload shape to consume
- allowing the service and plugin teams to work against a shared seam before the implementation is complete

## Minimal Envelope

- `schema_version`
- `request_id`
- `score_id`
- `actions`

Each action carries:

- `kind`
- `target`
- `payload`
- `metadata`

## Important Files

- `schemas/action-batch.json`: top-level batch envelope
- `schemas/action.json`: per-action payload shape
- `schemas/targets.json`: target-selection structure

## Current Status

These schemas are intentionally minimal. They are placeholders for the future plugin integration, not yet the live output of `apps/service`.
