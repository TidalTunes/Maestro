# Troubleshooting

## `BridgeTimeoutError`

Symptom:

- Python waits then raises timeout while calling `ping()` or any operation.

Checks:

1. Confirm MuseScore is open.
2. Confirm `Plugins > Maestro > Maestro Plugin` is running and dialog remains open.
3. Confirm client bridge directory matches plugin directory.
   - default is `~/.maestro-musescore-bridge`
   - override with `MuseScoreBridgeClient(bridge_dir=...)`
4. Check filesystem permissions for bridge directory.

## `BridgeResponseError: No score is open`

Symptom:

- `score_info`, `read_score`, or write operations fail with no-score error.

Fix:

- Open or create a score in MuseScore before running score-targeted calls.

## `BridgeResponseError: One or more actions failed`

Symptom:

- top-level request failed due to at least one action error.

How to inspect:

```python
from maestro_musescore_bridge import BridgeResponseError

try:
    client.apply_actions(actions)
except BridgeResponseError as exc:
    print(exc.response)
```

Alternative for diagnosis:

- run with `fail_on_partial=False`
- inspect `result["results"]` per action

## `Unsupported action kind: ...`

Cause:

- Python action kind is not listed in `ACTION_KINDS`.

Fix:

- use an existing action helper method on `client` or `batch`
- or check [Action Reference](action-reference.md)

## `add_harmony` Always Fails

Current behavior is expected.

`add_harmony` is deliberately blocked because MuseScore 4 plugin API can crash when inserting chord symbols programmatically.

## `score_info` Works But Edits Do Nothing

Possible causes:

- writing to a different score/staff/voice than expected
- tick values are outside current timeline
- edits are valid but not in visible measure location

Debug steps:

1. Call `read_score()` and inspect returned events.
2. Use small test actions first (`add_note`, `add_dynamic`) at `tick=0`, `staff=0`, `voice=0`.
3. Confirm required measures exist (`append_measures`).

## Tester Crash Investigation

If using `testing/lightweight_tester.py` and `All Features` crashes host:

- check `testing/last_action_attempt.json`
- it records the final action attempted before interruption
- rerun with that action removed to isolate host-side API limitation

## Cleaning Stale Bridge Files

If you suspect stale I/O:

```bash
rm -f ~/.maestro-musescore-bridge/request.json ~/.maestro-musescore-bridge/response.json
```

Then relaunch the bridge plugin dialog and retry.
