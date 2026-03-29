# Protocol Reference

The package and MuseScore plugin communicate through JSON files in a bridge directory.

Default bridge directory:

- `~/.maestro-musescore-bridge`

Files:

- request: `request.json`
- response: `response.json`

## Request Envelope

```json
{
  "protocol": "maestro.bridge.v1",
  "request_id": "<uuid>",
  "operation": "apply_actions",
  "actions": [
    {
      "kind": "add_note",
      "pitch": "C4",
      "duration": "quarter",
      "tick": 0,
      "staff": 0,
      "voice": 0
    }
  ],
  "fail_on_partial": true
}
```

## Supported Operations

- `ping`
- `list_actions`
- `score_info`
- `read_score`
- `apply_actions`
- `apply_commands`

### `apply_actions`

Input:

- `actions`: array of action objects (`kind` + fields)
- optional `fail_on_partial` (default `true`)

Behavior:

- plugin maps action kinds to MuseScore commands
- runs all mapped commands in one command group
- returns per-command result objects

### `apply_commands`

Input:

- `commands`: array of low-level command objects (`op` + fields)
- optional `fail_on_partial` (default `true`)

Use when bypassing action mapping for direct command payloads.

## Response Envelope

```json
{
  "protocol": "maestro.bridge.v1",
  "request_id": "<uuid>",
  "ok": true,
  "result": {
    "command_count": 1,
    "all_ok": true,
    "results": [
      { "ok": true }
    ]
  },
  "error": "",
  "received_at": "2026-03-29T00:00:00.000Z",
  "responded_at": "2026-03-29T00:00:00.050Z"
}
```

If `ok` is `false`, `error` contains a top-level message.

## Partial Failure Semantics

- `fail_on_partial=true`:
  - any failed action => request `ok=false`
  - Python client raises `BridgeResponseError`
- `fail_on_partial=false`:
  - request may still return `ok=true` with failed per-action entries
  - inspect `result.results` for each action status

## Concurrency Model

- The package sends one request at a time per client call.
- The plugin polls every 200ms.
- If stale response files exist, the client removes them before sending the next request.
- The plugin deletes `request.json` after reading.

## File I/O Guarantees

Client-side:

- request written via temp file + `os.replace` for atomic swap
- response file removed after successful read

Plugin-side:

- reads full request text
- writes full response JSON in one `write()` call

## Versioning

Current protocol version:

- `maestro.bridge.v1`

If plugin and client protocol versions mismatch, plugin returns an error.
