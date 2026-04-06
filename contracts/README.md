# Contracts

This directory contains language-neutral interface definitions shared across application boundaries.

## Current Contracts

- `service-api`: the current HTTP interface exposed by the local service
- `score-actions`: the planned structured edit contract between the service and the MuseScore plugin

## Why This Exists

The frontend, backend, and plugin are expected to evolve independently. These contract files are the place to stabilize payload shape without forcing every boundary to learn each other’s internal code structure.
