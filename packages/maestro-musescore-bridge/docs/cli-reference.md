# CLI Reference

Executable name:

- `maestro-musescore-bridge`

## Global Options

- `--bridge-dir <path>`
  - Override bridge directory.
  - Default: `~/.maestro-musescore-bridge`
- `--timeout <seconds>`
  - Default: `10.0`
- `--poll-interval <seconds>`
  - Default: `0.05`

Global options can be passed before subcommand.

Example:

```bash
maestro-musescore-bridge --timeout 20 --poll-interval 0.1 ping
```

## Subcommands

### `ping`

Checks plugin bridge reachability.

```bash
maestro-musescore-bridge ping
```

### `list-actions`

Returns plugin-reported action specs.

```bash
maestro-musescore-bridge list-actions
```

### `score-info`

Returns score metadata.

```bash
maestro-musescore-bridge score-info
```

Requires an open score in MuseScore.

### `read-score`

Returns score events (chord/rest-like view from plugin reader).

```bash
maestro-musescore-bridge read-score
```

Requires an open score in MuseScore.

### `apply-json <path>`

Applies actions from JSON file.

```bash
maestro-musescore-bridge apply-json ./actions.json
```

Optional:

- `--allow-partial`
  - equivalent to `fail_on_partial=False`
  - command succeeds if request-level `ok=true` even with failed action entries

## JSON Input Shapes For `apply-json`

Accepted:

1. JSON array of action objects

```json
[
  {"kind": "add_note", "pitch": "C4", "duration": "quarter", "tick": 0, "staff": 0, "voice": 0}
]
```

2. Object containing `actions` array

```json
{
  "actions": [
    {"kind": "add_dynamic", "text": "mf", "tick": 0, "staff": 0}
  ]
}
```

## Exit Codes

- `0`: success
- `1`: bridge error, JSON load error, file I/O error, validation error
- `2`: argument parsing failure
