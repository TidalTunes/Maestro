# API Reference

## Public Exports

From `maestro_musescore_bridge`:

- `MuseScoreBridgeClient`
- `ActionBatch`
- `ScoreAction`
- `ACTION_KINDS`
- `PROTOCOL_VERSION`
- `BridgeError`
- `BridgeTimeoutError`
- `BridgeResponseError`

## MuseScoreBridgeClient

```python
MuseScoreBridgeClient(
    bridge_dir: str | pathlib.Path | None = None,
    *,
    timeout: float = 10.0,
    poll_interval: float = 0.05,
)
```

### Constructor Parameters

- `bridge_dir`:
  - Bridge filesystem directory.
  - Defaults to `~/.maestro-musescore-bridge`.
- `timeout`:
  - Seconds to wait for plugin response before raising `BridgeTimeoutError`.
- `poll_interval`:
  - Sleep interval between response checks.

### Connection/Read Methods

- `ping() -> Mapping[str, Any]`
- `list_actions() -> Mapping[str, Any]`
- `score_info() -> Mapping[str, Any]`
- `read_score() -> Mapping[str, Any]`

### Write Methods

- `apply_actions(actions, *, fail_on_partial=True) -> Mapping[str, Any]`
  - `actions` may contain dictionaries or `ScoreAction` objects.
- `apply_batch(batch, *, fail_on_partial=True) -> Mapping[str, Any]`
- `apply_commands(commands, *, fail_on_partial=True) -> Mapping[str, Any]`
  - Sends raw plugin command format directly.

### Low-Level Request

- `request(operation: str, **payload) -> Mapping[str, Any]`

### Batch Factory

- `MuseScoreBridgeClient.batch() -> ActionBatch`

### Generated Single-Action Methods

`MuseScoreBridgeClient` dynamically gets one method for each action kind in `ACTION_KINDS`.

Example:

```python
client.add_note(pitch="C4", duration="quarter", tick=0, staff=0, voice=0)
client.add_dynamic(text="mf", tick=0, staff=0)
```

Each helper sends one action via `apply_actions([action])`.

## ActionBatch

`ActionBatch` accumulates actions for one bridge request.

### Constructor

```python
ActionBatch(actions: Iterable[dict[str, Any] | ScoreAction] | None = None)
```

### Core Methods

- `add_action(kind: str, **fields) -> ActionBatch`
- `extend(actions) -> ActionBatch`
- `clear() -> None`
- `to_list() -> list[dict[str, Any]]`

### Generated Action Methods

Like the client, `ActionBatch` has one method per action kind:

```python
batch.add_note(...)
batch.add_tempo(...)
batch.add_lyrics(...)
```

## ScoreAction

```python
ScoreAction(kind: str, fields: Mapping[str, Any] = {})
```

Methods:

- `to_dict() -> dict[str, Any]`

Use when you want immutable action objects before submission.

## Exceptions

### BridgeError

Base class for package-specific runtime failures.

### BridgeTimeoutError

Raised when no matching response arrives before timeout.

### BridgeResponseError

Raised when plugin responds with `ok=false`.

Properties:

- `.response`: full response payload from plugin for diagnostics.

## Return Payload Shape

`MuseScoreBridgeClient` methods return the plugin `result` object on success.

For `apply_actions` / `apply_batch`, typical result shape is:

```json
{
  "command_count": 3,
  "all_ok": true,
  "results": [
    {"ok": true},
    {"ok": true},
    {"ok": true}
  ]
}
```

If `fail_on_partial=False`, response may still contain failed items in `results` without raising, as long as plugin-level `ok=true`.
