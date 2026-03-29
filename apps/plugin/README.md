# Maestro Plugin

This directory is the stable destination for the MuseScore plugin code once it lands in this repository.

## Intended Responsibility

- own MuseScore-specific score reads and writes
- consume the future `contracts/score-actions` schemas
- keep MuseScore API details out of the service and shared core packages

`pluginExperiment/` remains preserved as a legacy experiment during the transition.

## What This Module Will Eventually Be Capable Of

- receiving structured edit plans from the service layer
- translating those plans into MuseScore API operations
- applying edits directly to the live score
- acting as the authoritative bridge between repository code and the MuseScore runtime

## Boundaries

- Put MuseScore host integration here.
- Do not put OpenAI calls here.
- Do not put general-purpose score-planning logic here.
- Use `contracts/score-actions` as the interface seam instead of directly depending on service internals.
