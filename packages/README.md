# Packages

This directory contains reusable modules that should stay decoupled from any single runtime host.

## Current Packages

- `agent-core`: shared LLM-system logic and generated-code safety helpers
- `maestroxml`: score builder, action planning, and MusicXML import helpers
- `humming-detector`: hummed melody transcription support
- `maestro-musescore-bridge`: Python client for the MuseScore bridge plugin

## Ownership Rule

Put code here when it should be reusable by more than one app, or when it is easier to test independently from FastAPI, PyQt, or MuseScore plugin hosts.
