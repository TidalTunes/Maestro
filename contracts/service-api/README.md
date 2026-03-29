# Service API Contract

This directory contains the current HTTP contract for the running local Maestro service.

## What It Defines

- request payload shape for prompt generation
- response payload shape for MusicXML/code generation
- humming start/stop payloads
- the basic healthcheck response

## Important Files

- `openapi.yaml`: top-level API description
- `schemas/generate-request.json`: prompt submission payload
- `schemas/generate-response.json`: successful generation response
- `schemas/error-response.json`: service-side error payload
- `schemas/humming-start-response.json`: recorder start response
- `schemas/humming-stop-response.json`: recorder stop/transcription response

## Current Scope

This contract describes the service as it works today: it returns generated Python and MusicXML. It does not yet describe the future plugin-facing score-action contract.
