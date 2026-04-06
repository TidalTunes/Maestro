from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

ACTION_KINDS: tuple[str, ...] = (
    "add_note",
    "add_chord",
    "add_rest",
    "write_sequence",
    "modify_note",
    "modify_chord",
    "append_measures",
    "add_part",
    "set_header_text",
    "set_meta_tag",
    "add_time_signature",
    "add_key_signature",
    "add_clef",
    "add_tempo",
    "add_dynamic",
    "add_articulation",
    "add_fermata",
    "add_arpeggio",
    "add_staff_text",
    "add_system_text",
    "add_rehearsal_mark",
    "add_expression_text",
    "add_lyrics",
    "write_lyrics",
    "add_harmony",
    "add_fingering",
    "add_breath",
    "add_tuplet",
    "add_layout_break",
    "add_spacer",
    "modify_measure",
)

CANONICAL_DURATION_NAMES: dict[str, str] = {
    "whole": "whole",
    "half": "half",
    "quarter": "quarter",
    "eighth": "eighth",
    "8th": "eighth",
    "16th": "16th",
    "sixteenth": "16th",
    "32nd": "32nd",
    "thirty-second": "32nd",
    "thirty second": "32nd",
    "64th": "64th",
    "sixty-fourth": "64th",
    "sixty fourth": "64th",
}


@dataclass(frozen=True, slots=True)
class ScoreAction:
    """Immutable score action payload sent to the MuseScore plugin."""

    kind: str
    fields: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {"kind": self.kind}
        payload.update(dict(self.fields))
        return payload


class ActionBatch:
    """Builder for score actions that can be submitted in one bridge request."""

    def __init__(self, actions: Iterable[dict[str, Any] | ScoreAction] | None = None) -> None:
        self._actions: list[dict[str, Any]] = []
        if actions is not None:
            self.extend(actions)

    def add_action(self, kind: str, **fields: Any) -> "ActionBatch":
        if kind not in ACTION_KINDS:
            raise ValueError(f"Unsupported action kind: {kind}")
        action: dict[str, Any] = {"kind": kind}
        action.update(fields)
        self._actions.append(_normalize_duration_fields(action))
        return self

    def extend(self, actions: Iterable[dict[str, Any] | ScoreAction]) -> "ActionBatch":
        for action in actions:
            if isinstance(action, ScoreAction):
                self._actions.append(_normalize_duration_fields(action.to_dict()))
            elif isinstance(action, Mapping):
                payload = dict(action)
                if "kind" not in payload:
                    raise ValueError("Action dictionaries must include a 'kind' key")
                if payload["kind"] not in ACTION_KINDS:
                    raise ValueError(f"Unsupported action kind: {payload['kind']}")
                self._actions.append(_normalize_duration_fields(payload))
            else:
                raise TypeError(f"Unsupported action type: {type(action)!r}")
        return self

    def clear(self) -> None:
        self._actions.clear()

    def to_list(self) -> list[dict[str, Any]]:
        return [dict(action) for action in self._actions]

    def __iter__(self):
        return iter(self._actions)

    def __len__(self) -> int:
        return len(self._actions)


def _install_action_batch_helpers() -> None:
    for kind in ACTION_KINDS:

        def _method(self: ActionBatch, _kind: str = kind, **fields: Any) -> ActionBatch:
            return self.add_action(_kind, **fields)

        _method.__name__ = kind
        _method.__qualname__ = f"ActionBatch.{kind}"
        _method.__doc__ = (
            f"Append one `{kind}` action to the batch. "
            "Fields are passed through directly to the plugin action payload."
        )
        setattr(ActionBatch, kind, _method)


_install_action_batch_helpers()


def _normalize_duration_name(value: str) -> str:
    candidate = value.strip().lower()
    canonical = CANONICAL_DURATION_NAMES.get(candidate)
    if canonical is None:
        canonical = CANONICAL_DURATION_NAMES.get(candidate.replace("-", " "))
    if canonical is None:
        raise ValueError(f"Unsupported duration name: {value!r}")
    return canonical


def _parse_duration_spec(duration: str, dots: int = 0) -> tuple[str, int]:
    normalized = " ".join(duration.strip().lower().replace("-", " ").split())
    total_dots = int(dots or 0)
    if total_dots < 0:
        raise ValueError("Dots must be a non-negative integer")

    dotted_prefixes = (
        ("single dotted ", 1),
        ("double dotted ", 2),
        ("triple dotted ", 3),
        ("dotted ", 1),
    )
    for prefix, implied_dots in dotted_prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            total_dots += implied_dots
            break

    return _normalize_duration_name(normalized), total_dots


def _normalize_duration_payload_fields(payload: dict[str, Any]) -> dict[str, Any]:
    duration = payload.get("duration")
    if isinstance(duration, str):
        duration_name, total_dots = _parse_duration_spec(duration, payload.get("dots", 0))
        payload["duration"] = duration_name
        if total_dots > 0:
            payload["dots"] = total_dots
        else:
            payload.pop("dots", None)
    return payload


def _normalize_duration_fields(action: dict[str, Any]) -> dict[str, Any]:
    kind = action.get("kind")
    normalized = dict(action)
    if kind in {"add_note", "add_chord", "add_rest"}:
        return _normalize_duration_payload_fields(normalized)
    if kind == "write_sequence":
        events = []
        for event in normalized.get("events", []):
            if isinstance(event, Mapping):
                events.append(_normalize_duration_payload_fields(dict(event)))
            else:
                events.append(event)
        normalized["events"] = events
    return normalized
