from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any, Iterable, Mapping
from uuid import uuid4

from .actions import ACTION_KINDS, ActionBatch, ScoreAction

PROTOCOL_VERSION = "maestro.bridge.v1"
DEFAULT_BRIDGE_DIRNAME = ".maestro-musescore-bridge"


class BridgeError(RuntimeError):
    """Base error for bridge client failures."""


class BridgeTimeoutError(BridgeError):
    """Raised when the bridge plugin does not answer in time."""


class BridgeResponseError(BridgeError):
    """Raised when the bridge plugin returns ok=false."""

    def __init__(self, message: str, response: Mapping[str, Any]) -> None:
        super().__init__(message)
        self.response = dict(response)


class MuseScoreBridgeClient:
    """
    File-based client for the `maestro_python_bridge.qml` plugin.

    The plugin must be open inside MuseScore and left running.
    """

    def __init__(
        self,
        bridge_dir: str | Path | None = None,
        *,
        timeout: float = 10.0,
        poll_interval: float = 0.01,
    ) -> None:
        base = Path.home() / DEFAULT_BRIDGE_DIRNAME if bridge_dir is None else Path(bridge_dir)
        self.bridge_dir = base
        self.timeout = float(timeout)
        self.poll_interval = float(poll_interval)

        self.request_path = self.bridge_dir / "request.json"
        self.response_path = self.bridge_dir / "response.json"
        self.bridge_dir.mkdir(parents=True, exist_ok=True)

    def ping(self) -> Mapping[str, Any]:
        return self.request("ping")

    def list_actions(self) -> Mapping[str, Any]:
        return self.request("list_actions")

    def score_info(self) -> Mapping[str, Any]:
        return self.request("score_info")

    def read_score(self) -> Mapping[str, Any]:
        return self.request("read_score")

    def export_musicxml(self) -> Mapping[str, Any]:
        result = self.request("export_musicxml")
        exported_path = result.get("path")
        if not isinstance(exported_path, str) or not exported_path.strip():
            raise BridgeResponseError(
                "Bridge did not return a MusicXML export path.",
                {
                    "ok": False,
                    "error": "Missing export path",
                    "result": dict(result),
                },
            )
        return result

    def apply_actions(
        self,
        actions: Iterable[Mapping[str, Any] | ScoreAction],
        *,
        fail_on_partial: bool = True,
    ) -> Mapping[str, Any]:
        payload_actions = [self._normalize_action(action) for action in actions]
        return self.request(
            "apply_actions",
            actions=payload_actions,
            fail_on_partial=fail_on_partial,
        )

    def apply_actions_streamed(
        self,
        actions: Iterable[Mapping[str, Any] | ScoreAction],
        *,
        delay_seconds: float = 0.01,
        fail_on_partial: bool = True,
    ) -> Mapping[str, Any]:
        payload_actions = [self._normalize_action(action) for action in actions]
        if not payload_actions:
            return {
                "command_count": 0,
                "all_ok": True,
                "results": [],
            }

        delay = max(0.0, float(delay_seconds))
        aggregated_results: list[Any] = []

        for index, action in enumerate(payload_actions):
            try:
                result = self.request(
                    "apply_actions",
                    actions=[action],
                    fail_on_partial=False,
                )
            except BridgeError as exc:
                if aggregated_results:
                    raise BridgeResponseError(
                        "Streaming actions to the MuseScore bridge failed.",
                        {
                            "ok": False,
                            "error": str(exc),
                            "result": {
                                "command_count": len(aggregated_results),
                                "all_ok": False,
                                "results": aggregated_results,
                            },
                        },
                    ) from exc
                raise

            per_action_results = result.get("results", [])
            if isinstance(per_action_results, list):
                aggregated_results.extend(per_action_results)
            else:
                aggregated_results.append(
                    {
                        "ok": False,
                        "error": "Bridge returned invalid streamed action results.",
                    }
                )

            latest_ok = bool(aggregated_results[-1].get("ok")) if aggregated_results else False
            if not latest_ok and fail_on_partial:
                raise BridgeResponseError(
                    "One or more actions failed",
                    {
                        "ok": False,
                        "error": "One or more actions failed",
                        "result": {
                            "command_count": len(aggregated_results),
                            "all_ok": False,
                            "results": aggregated_results,
                        },
                    },
                )

            if delay > 0.0 and index < len(payload_actions) - 1:
                time.sleep(delay)

        return {
            "command_count": len(aggregated_results),
            "all_ok": all(
                isinstance(item, Mapping) and item.get("ok") is True for item in aggregated_results
            ),
            "results": aggregated_results,
        }

    def apply_commands(
        self,
        commands: Iterable[Mapping[str, Any]],
        *,
        fail_on_partial: bool = True,
    ) -> Mapping[str, Any]:
        return self.request(
            "apply_commands",
            commands=[dict(command) for command in commands],
            fail_on_partial=fail_on_partial,
        )

    def apply_batch(self, batch: ActionBatch, *, fail_on_partial: bool = True) -> Mapping[str, Any]:
        return self.apply_actions(batch.to_list(), fail_on_partial=fail_on_partial)

    @staticmethod
    def batch() -> ActionBatch:
        return ActionBatch()

    def request(self, operation: str, **payload: Any) -> Mapping[str, Any]:
        request_id = str(uuid4())

        request_data: dict[str, Any] = {
            "protocol": PROTOCOL_VERSION,
            "request_id": request_id,
            "operation": operation,
        }
        request_data.update(payload)

        self._safe_unlink(self.response_path)
        self._write_request(request_id, request_data)
        return self._wait_for_response(request_id)

    def _write_request(self, request_id: str, request_data: Mapping[str, Any]) -> None:
        temp_path = self.bridge_dir / f"request-{request_id}.tmp"
        temp_path.write_text(json.dumps(request_data, indent=2), encoding="utf-8")
        os.replace(temp_path, self.request_path)

    def _wait_for_response(self, request_id: str) -> Mapping[str, Any]:
        deadline = time.monotonic() + self.timeout

        while time.monotonic() < deadline:
            if not self.response_path.exists():
                time.sleep(self.poll_interval)
                continue

            raw_response = self.response_path.read_text(encoding="utf-8")
            try:
                response = json.loads(raw_response)
            except json.JSONDecodeError:
                time.sleep(self.poll_interval)
                continue

            response_id = response.get("request_id", "")
            if response_id != request_id:
                # Stale response from a previous request.
                self._safe_unlink(self.response_path)
                time.sleep(self.poll_interval)
                continue

            self._safe_unlink(self.response_path)

            if response.get("ok") is not True:
                raise BridgeResponseError(response.get("error", "Bridge request failed"), response)

            result = response.get("result", {})
            if isinstance(result, Mapping):
                return result
            raise BridgeResponseError("Bridge returned a non-object result payload", response)

        raise BridgeTimeoutError(
            "Timed out waiting for MuseScore bridge response. "
            "Make sure the 'Maestro Python Bridge' plugin dialog is open."
        )

    @staticmethod
    def _normalize_action(action: Mapping[str, Any] | ScoreAction) -> dict[str, Any]:
        if isinstance(action, ScoreAction):
            payload = action.to_dict()
        elif isinstance(action, Mapping):
            payload = dict(action)
        else:
            raise TypeError(f"Unsupported action type: {type(action)!r}")

        kind = payload.get("kind")
        if not isinstance(kind, str):
            raise ValueError("Each action must include a string 'kind'")
        if kind not in ACTION_KINDS:
            raise ValueError(f"Unsupported action kind: {kind}")

        return payload

    @staticmethod
    def _safe_unlink(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return


def _install_client_action_helpers() -> None:
    for kind in ACTION_KINDS:

        def _method(self: MuseScoreBridgeClient, _kind: str = kind, **fields: Any) -> Mapping[str, Any]:
            payload = {"kind": _kind}
            payload.update(fields)
            return self.apply_actions([payload])

        _method.__name__ = kind
        _method.__qualname__ = f"MuseScoreBridgeClient.{kind}"
        _method.__doc__ = (
            f"Apply one `{kind}` action immediately. "
            "Fields are passed through directly to the plugin action payload."
        )
        setattr(MuseScoreBridgeClient, kind, _method)


_install_client_action_helpers()
