# Agent Compatibility Runtime

This directory holds the minimal legacy runtime that the current desktop frontend still imports for prompt-to-code generation.

## What Stays Here

- `app/agent.py`: compatibility wrapper around the original generation flow
- `app/config.py`: runtime settings for the compatibility path
- `app/context/`: legacy reference-corpus loading
- `app/guard.py`: generated-code validation used by the compatibility generator
- `reference-corpus/`: prompt reference material consumed by the compatibility generator

## What Was Removed

- duplicated `maestroxml` source copies
- duplicated legacy tests
- old FastAPI/demo app code
- old detector copies and their test harnesses

## Boundary

This directory exists only for compatibility with the current MVP runtime. New product work should land in `apps/`, `packages/`, and `contracts/`.
