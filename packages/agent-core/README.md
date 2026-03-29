# Maestro Agent Core

This package contains prompt construction, reference loading, guardrails, and generated-code execution helpers shared by the Maestro service.

## What It Can Do

- build the current Maestro generation instructions
- shape model input from text prompts and optional hummed-note context
- load curated reference material from docs and skill files
- enforce safety and contract rules on generated Python
- execute validated generated code against a configured `maestroxml` source tree
- extract text safely from OpenAI response objects

## Important Modules

- `src/maestro_agent_core/generation.py`: prompt-building, output extraction, and generated-code execution
- `src/maestro_agent_core/guard.py`: AST-based safety and contract validation for generated Python
- `src/maestro_agent_core/context/loader.py`: curated reference-material loading
- `tests/test_generation.py`: unit tests for core behavior

## Boundaries

- Keep HTTP request handling out of this package.
- Keep OpenAI client instantiation out of this package when possible; the service should own that runtime concern.
- Keep MuseScore plugin specifics out of this package.
- This package should remain reusable even if the final product stops returning MusicXML artifacts directly.
