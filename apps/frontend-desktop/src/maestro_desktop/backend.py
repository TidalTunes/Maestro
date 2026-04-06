from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import os
from typing import Any, Mapping
from urllib import error as urllib_error
from urllib import request as urllib_request

from .runtime_support import (
    bootstrap_runtime_imports,
    maestroxml_docs_dir,
    maestroxml_src_dir as bundled_maestroxml_src_dir,
    runtime_root,
    skill_dir as bundled_skill_dir,
)

ROOT_DIR = runtime_root()
DEFAULT_SKILL_DIR = bundled_skill_dir()
DEFAULT_DOCS_DIR = maestroxml_docs_dir()
MAESTROXML_SRC = bundled_maestroxml_src_dir()
DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_OLLAMA_MODEL = "qwen3.5:cloud"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434/api"
DEFAULT_TICKS_PER_QUARTER = 480
DEFAULT_MEASURE_TICKS = DEFAULT_TICKS_PER_QUARTER * 4
LIVE_EDIT_STREAM_DELAY_SECONDS = 0.01


def bootstrap_local_imports() -> None:
    bootstrap_runtime_imports()


bootstrap_local_imports()

import app.agent as legacy_agent_module
from app.agent import GeneratedScoreCode
from app.config import get_settings as get_legacy_settings
from maestro_agent_core import (
    AgentError as CoreAgentError,
    build_edit_generation_instructions,
    build_edit_model_input,
    execute_generated_edit_code,
    extract_output_text,
    response_status_message,
)
from maestro_agent_core.context import ReferenceLoadError, load_reference_corpus
from maestro_musescore_bridge import BridgeError, MuseScoreBridgeClient
from maestroxml import musicxml_to_python


def _resolve_ollama_chat_endpoint(base_url: str) -> str:
    normalized = (base_url or DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")
    if normalized.endswith("/api"):
        return normalized + "/chat"
    return normalized + "/api/chat"


def _create_openai_client(api_key: str):
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LiveEditError(
            "The OpenAI Python SDK is not installed. Install the service dependencies first."
        ) from exc
    return OpenAI(api_key=api_key)


def _default_ollama_request(base_url: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    endpoint = _resolve_ollama_chat_endpoint(base_url)
    headers = {"Content-Type": "application/json"}
    ollama_api_key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if ollama_api_key and endpoint.startswith("https://ollama.com/api/"):
        headers["Authorization"] = f"Bearer {ollama_api_key}"

    request = urllib_request.Request(
        endpoint,
        data=json.dumps(dict(payload)).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib_request.urlopen(request, timeout=180.0) as response:
            body = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if detail:
            raise LiveEditError(f"Ollama request failed: {detail}") from exc
        raise LiveEditError(f"Ollama request failed with HTTP {exc.code}.") from exc
    except urllib_error.URLError as exc:
        raise LiveEditError(f"Ollama request failed: {exc.reason}") from exc
    except Exception as exc:
        raise LiveEditError(f"Ollama request failed: {exc}") from exc

    try:
        response_payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise LiveEditError("Ollama returned invalid JSON.") from exc

    if not isinstance(response_payload, Mapping):
        raise LiveEditError("Ollama returned a non-object response payload.")

    error_message = response_payload.get("error")
    if isinstance(error_message, str) and error_message.strip():
        raise LiveEditError(f"Ollama request failed: {error_message.strip()}")

    return response_payload


def _default_audio_transcriber(audio_path: str | Path) -> str:
    try:
        from maestro_humming_detector.api import transcribe_humming
    except ImportError as exc:
        raise HummingError(
            "Humming support is unavailable. Install dependencies for packages/humming-detector first."
        ) from exc
    return transcribe_humming(audio_path)


class HummingError(RuntimeError):
    """Raised when microphone recording or humming transcription fails."""


class LiveEditError(RuntimeError):
    """Raised when live score editing fails."""

    def __init__(self, message: str, python_code: str | None = None) -> None:
        super().__init__(message)
        self.python_code = python_code


@dataclass(frozen=True)
class CapturedHumming:
    notes: str
    audio_path: str
    duration_seconds: float


@dataclass(frozen=True)
class LiveEditResult:
    python_code: str
    action_count: int
    bridge_result: dict[str, object]
    hummed_notes: str


@dataclass(frozen=True)
class OpenAIProviderConfig:
    api_key: str = ""
    model: str = ""


@dataclass(frozen=True)
class OllamaProviderConfig:
    model: str = DEFAULT_OLLAMA_MODEL
    base_url: str = ""


@dataclass(frozen=True)
class ModelProviderConfig:
    provider: str
    openai: OpenAIProviderConfig | None = None
    ollama: OllamaProviderConfig | None = None

    @classmethod
    def for_openai(
        cls,
        *,
        api_key: str = "",
        model: str = "",
    ) -> ModelProviderConfig:
        return cls(
            provider="openai",
            openai=OpenAIProviderConfig(api_key=api_key, model=model),
        )

    @classmethod
    def for_ollama(
        cls,
        *,
        model: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = "",
    ) -> ModelProviderConfig:
        return cls(
            provider="ollama",
            ollama=OllamaProviderConfig(model=model, base_url=base_url),
        )


@dataclass(frozen=True)
class ResolvedModelProvider:
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""


@dataclass(frozen=True)
class LiveEditSettings:
    root_dir: Path
    maestro_skill_dir: Path
    maestro_docs_dir: Path
    maestroxml_src_dir: Path
    openai_model: str
    ollama_model: str
    ollama_base_url: str
    openai_reasoning_effort: str
    openai_max_output_tokens: int
    execution_timeout_seconds: int


def _resolve_path(value: str, default: Path) -> Path:
    if not value:
        return default.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path.resolve()


def get_live_edit_settings() -> LiveEditSettings:
    skill_dir = os.environ.get("MAESTRO_SKILL_DIR") or os.environ.get("MAESTRO_SKILL_PATH", "")
    docs_dir = os.environ.get("MAESTRO_DOCS_DIR", "")
    maestroxml_src_dir = os.environ.get("MAESTRO_MAESTROXML_SRC_DIR", "")
    return LiveEditSettings(
        root_dir=ROOT_DIR,
        maestro_skill_dir=_resolve_path(skill_dir, DEFAULT_SKILL_DIR),
        maestro_docs_dir=_resolve_path(docs_dir, DEFAULT_DOCS_DIR),
        maestroxml_src_dir=_resolve_path(maestroxml_src_dir, MAESTROXML_SRC),
        openai_model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
        ollama_model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        ollama_base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
        openai_reasoning_effort=os.environ.get("OPENAI_REASONING_EFFORT", "low"),
        openai_max_output_tokens=int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "20000")),
        execution_timeout_seconds=int(os.environ.get("EXECUTION_TIMEOUT_SECONDS", "20")),
    )


def get_default_provider_config() -> ModelProviderConfig:
    explicit_provider = (
        os.environ.get("MAESTRO_MODEL_PROVIDER", "")
        or os.environ.get("MAESTRO_PROVIDER", "")
    ).strip().lower()

    if explicit_provider == "openai":
        return ModelProviderConfig.for_openai(
            api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip(),
        )

    if explicit_provider == "ollama":
        return ModelProviderConfig.for_ollama(
            model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL,
            base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip(),
        )

    openai_api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if openai_api_key:
        return ModelProviderConfig.for_openai(
            api_key=openai_api_key,
            model=os.environ.get("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip(),
        )

    return ModelProviderConfig.for_ollama(
        model=os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL).strip() or DEFAULT_OLLAMA_MODEL,
        base_url=os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).strip(),
    )


def _resolve_model_provider(
    provider: ModelProviderConfig | None,
    *,
    api_key: str | None,
    settings: LiveEditSettings,
) -> ResolvedModelProvider:
    if provider is None and isinstance(api_key, str) and api_key.strip():
        provider = ModelProviderConfig.for_openai(api_key=api_key.strip())
    elif provider is None:
        provider = get_default_provider_config()

    provider_name = provider.provider.strip().lower()
    if provider_name == "openai":
        openai = provider.openai or OpenAIProviderConfig()
        resolved_api_key = (openai.api_key or api_key or os.environ.get("OPENAI_API_KEY", "")).strip()
        if not resolved_api_key:
            raise LiveEditError("OpenAI requires an API key. Set it in Settings or OPENAI_API_KEY.")
        resolved_model = (openai.model or settings.openai_model or DEFAULT_OPENAI_MODEL).strip()
        return ResolvedModelProvider(
            provider="openai",
            model=resolved_model or DEFAULT_OPENAI_MODEL,
            api_key=resolved_api_key,
        )

    if provider_name == "ollama":
        ollama = provider.ollama or OllamaProviderConfig()
        resolved_model = (ollama.model or settings.ollama_model or DEFAULT_OLLAMA_MODEL).strip()
        resolved_base_url = (ollama.base_url or settings.ollama_base_url or DEFAULT_OLLAMA_BASE_URL).strip()
        return ResolvedModelProvider(
            provider="ollama",
            model=resolved_model or DEFAULT_OLLAMA_MODEL,
            base_url=resolved_base_url or DEFAULT_OLLAMA_BASE_URL,
        )

    raise LiveEditError(f"Unsupported model provider: {provider.provider!r}")


_BASE_DURATION_SPECS: tuple[tuple[str, Fraction], ...] = (
    ("whole", Fraction(4, 1)),
    ("half", Fraction(2, 1)),
    ("quarter", Fraction(1, 1)),
    ("eighth", Fraction(1, 2)),
    ("16th", Fraction(1, 4)),
    ("32nd", Fraction(1, 8)),
    ("64th", Fraction(1, 16)),
)

_SUPPORTED_DURATION_SPECS: tuple[tuple[str, int, Fraction], ...] = tuple(
    sorted(
        (
            (
                name,
                dots,
                base * Fraction((2 ** (dots + 1)) - 1, 2**dots),
            )
            for name, base in _BASE_DURATION_SPECS
            for dots in range(3)
        ),
        key=lambda item: item[2],
        reverse=True,
    )
)


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _allocate_identifier(raw: str, used: set[str], fallback: str) -> str:
    lowered = "".join(char.lower() if char.isalnum() else "_" for char in raw).strip("_")
    if not lowered or lowered[0].isdigit():
        lowered = fallback

    candidate = lowered
    suffix = 2
    while candidate in used:
        candidate = f"{lowered}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _pitch_name_from_midi(value: object) -> str:
    pitch = _as_int(value, 60)
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    octave = (pitch // 12) - 1
    return f"{names[pitch % 12]}{octave}"


def _exact_duration_spec(duration: Fraction) -> tuple[str, int] | None:
    for name, dots, candidate in _SUPPORTED_DURATION_SPECS:
        if candidate == duration:
            return name, dots
    return None


def _closest_duration_spec(duration: Fraction) -> tuple[str, int]:
    name, dots, _candidate = min(
        _SUPPORTED_DURATION_SPECS,
        key=lambda item: abs(item[2] - duration),
    )
    return name, dots


def _split_duration(duration: Fraction) -> list[tuple[str, int]]:
    if duration <= 0:
        return []

    remaining = duration
    pieces: list[tuple[str, int]] = []
    while remaining > 0:
        exact = _exact_duration_spec(remaining)
        if exact is not None:
            pieces.append(exact)
            break

        candidate: tuple[str, int, Fraction] | None = None
        for spec in _SUPPORTED_DURATION_SPECS:
            if spec[2] <= remaining:
                candidate = spec
                break

        if candidate is None:
            pieces.append(_closest_duration_spec(remaining))
            break

        pieces.append((candidate[0], candidate[1]))
        remaining -= candidate[2]
        if remaining <= Fraction(1, 128):
            break

    return pieces


def _measure_starts_from_score_info(
    score_info: Mapping[str, object],
    event_ticks: list[int],
) -> list[int]:
    raw_starts = score_info.get("measure_starts")
    starts: list[int] = []
    if isinstance(raw_starts, list):
        for item in raw_starts:
            starts.append(_as_int(item, 0))
        starts = sorted(dict.fromkeys(starts))

    nmeasures = max(_as_int(score_info.get("nmeasures"), 0), len(starts))
    if starts:
        step = starts[-1] - starts[-2] if len(starts) >= 2 else DEFAULT_MEASURE_TICKS
        if step <= 0:
            step = DEFAULT_MEASURE_TICKS
        while len(starts) < nmeasures:
            starts.append(starts[-1] + step)
        return starts

    max_tick = max(event_ticks, default=0)
    if nmeasures <= 0:
        nmeasures = max(1, (max_tick // DEFAULT_MEASURE_TICKS) + 1)
    return [index * DEFAULT_MEASURE_TICKS for index in range(nmeasures)]


def _part_layout_from_score_info(score_info: Mapping[str, object]) -> list[dict[str, object]]:
    nstaves = max(1, _as_int(score_info.get("nstaves"), 1))
    raw_parts = score_info.get("parts")
    layout: list[dict[str, object]] = []

    if isinstance(raw_parts, list):
        for index, item in enumerate(raw_parts, start=1):
            if not isinstance(item, Mapping):
                continue
            start_track = max(0, _as_int(item.get("startTrack"), (index - 1) * 4))
            end_track = max(start_track + 4, _as_int(item.get("endTrack"), start_track + 4))
            start_staff = start_track // 4
            staff_count = max(1, (end_track - start_track) // 4)
            part_name = (
                _clean_text(item.get("partName"))
                or _clean_text(item.get("longName"))
                or _clean_text(item.get("shortName"))
                or f"Part {index}"
            )
            instrument_id = _clean_text(item.get("instrumentId"))
            abbreviation = _clean_text(item.get("shortName"))

            clefs: tuple[str, ...] | None = None
            if staff_count > 1 and instrument_id not in {
                "piano",
                "organ",
                "harpsichord",
                "accordion",
                "harp",
                "celesta",
            }:
                clefs = tuple("bass" if slot == staff_count - 1 else "treble" for slot in range(staff_count))

            layout.append(
                {
                    "name": part_name,
                    "instrument": instrument_id,
                    "abbreviation": abbreviation,
                    "staves": staff_count,
                    "start_staff": start_staff,
                    "clefs": clefs,
                }
            )

    if not layout:
        return [
            {
                "name": f"Staff {index + 1}",
                "instrument": "",
                "abbreviation": "",
                "staves": 1,
                "start_staff": index,
                "clefs": None,
            }
            for index in range(nstaves)
        ]

    layout.sort(key=lambda item: _as_int(item["start_staff"], 0))
    completed: list[dict[str, object]] = []
    expected_staff = 0
    for item in layout:
        start_staff = _as_int(item["start_staff"], 0)
        while expected_staff < min(start_staff, nstaves):
            completed.append(
                {
                    "name": f"Staff {expected_staff + 1}",
                    "instrument": "",
                    "abbreviation": "",
                    "staves": 1,
                    "start_staff": expected_staff,
                    "clefs": None,
                }
            )
            expected_staff += 1
        completed.append(item)
        expected_staff = max(expected_staff, start_staff + _as_int(item["staves"], 1))

    while expected_staff < nstaves:
        completed.append(
            {
                "name": f"Staff {expected_staff + 1}",
                "instrument": "",
                "abbreviation": "",
                "staves": 1,
                "start_staff": expected_staff,
                "clefs": None,
            }
        )
        expected_staff += 1

    return completed


def _bridge_snapshot_to_python(
    score_info: Mapping[str, object],
    score_snapshot: Mapping[str, object],
) -> str:
    raw_events = score_snapshot.get("events")
    if not isinstance(raw_events, list):
        raise LiveEditError("MuseScore did not return a readable live score snapshot.")

    measure_starts = _measure_starts_from_score_info(
        score_info,
        [_as_int(item.get("tick"), 0) for item in raw_events if isinstance(item, Mapping)],
    )
    tpq = max(1, _as_int(score_info.get("tpq"), DEFAULT_TICKS_PER_QUARTER))
    part_layout = _part_layout_from_score_info(score_info)

    used_identifiers = {"score"}
    title = _clean_text(score_info.get("title"))
    composer = _clean_text(score_info.get("composer"))
    score_kwargs: list[str] = []
    if title:
        score_kwargs.append(f"title={title!r}")
    if composer:
        score_kwargs.append(f"composer={composer!r}")

    lines = [
        "from maestroxml import Score",
        "",
        "# Approximate live-score snapshot from the MuseScore bridge.",
        "# Tuplets, complex notation, and some layout detail may be simplified.",
        f"score = Score({', '.join(score_kwargs)})" if score_kwargs else "score = Score()",
    ]

    staff_map: dict[int, tuple[dict[str, object], int]] = {}
    for index, item in enumerate(part_layout, start=1):
        part_var = _allocate_identifier(str(item["name"]), used_identifiers, f"part_{index}")
        item["var"] = part_var

        args = [repr(str(item["name"]))]
        instrument = _clean_text(item.get("instrument"))
        abbreviation = _clean_text(item.get("abbreviation"))
        staves = max(1, _as_int(item.get("staves"), 1))
        clefs = item.get("clefs")
        if instrument:
            args.append(f"instrument={instrument!r}")
        if abbreviation:
            args.append(f"abbreviation={abbreviation!r}")
        if staves > 1:
            args.append(f"staves={staves}")
        if clefs:
            args.append(f"clefs={tuple(clefs)!r}")

        lines.append(f"{part_var} = score.add_part({', '.join(args)})")
        start_staff = _as_int(item.get("start_staff"), 0)
        for local_staff in range(1, staves + 1):
            staff_map[start_staff + local_staff - 1] = (item, local_staff)

    grouped_events: dict[int, dict[tuple[int, int], list[dict[str, object]]]] = {}
    used_voice_keys: set[tuple[int, int]] = set()
    max_measure = max(1, _as_int(score_info.get("nmeasures"), len(measure_starts)), len(measure_starts))

    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            continue

        tick = _as_int(raw_event.get("tick"), 0)
        staff_idx = _as_int(raw_event.get("staffIdx"), 0)
        voice_idx = _as_int(raw_event.get("voice"), 0)
        measure_index = bisect_right(measure_starts, tick) - 1
        if measure_index < 0:
            measure_index = 0
        measure_number = measure_index + 1
        measure_start_tick = measure_starts[measure_index] if measure_starts else 0
        offset = Fraction(tick - measure_start_tick, tpq)
        duration = Fraction(
            4 * _as_int(raw_event.get("durN"), 0),
            max(1, _as_int(raw_event.get("durD"), 1)),
        )

        if duration <= 0:
            continue

        pitches = raw_event.get("pitches")
        normalized_pitches = (
            [_pitch_name_from_midi(pitch) for pitch in pitches]
            if isinstance(pitches, list)
            else []
        )

        event_payload = {
            "tick": tick,
            "offset": offset,
            "duration": duration,
            "type": _clean_text(raw_event.get("type")) or "rest",
            "pitches": normalized_pitches,
        }
        grouped_events.setdefault(measure_number, {}).setdefault((staff_idx, voice_idx), []).append(
            event_payload
        )
        used_voice_keys.add((staff_idx, voice_idx))
        max_measure = max(max_measure, measure_number)

    voice_vars: dict[tuple[int, int], str] = {}
    for staff_idx, voice_idx in sorted(used_voice_keys):
        part_info = staff_map.get(staff_idx)
        if part_info is None:
            continue
        part_item, local_staff = part_info
        fallback_name = (
            f"{part_item['var']}_staff_{local_staff}_voice_{voice_idx + 1}"
        )
        voice_var = _allocate_identifier(fallback_name, used_identifiers, fallback_name)
        voice_vars[(staff_idx, voice_idx)] = voice_var
        lines.append(f"{voice_var} = {part_item['var']}.voice({voice_idx + 1}, {local_staff})")

    for measure_number in range(1, max_measure + 1):
        lines.extend(["", f"score.measure({measure_number})"])
        voices = grouped_events.get(measure_number, {})
        for voice_key in sorted(voices):
            voice_var = voice_vars.get(voice_key)
            if voice_var is None:
                continue

            current_offset = Fraction(0)
            for event in sorted(voices[voice_key], key=lambda item: (item["offset"], item["tick"])):
                gap = event["offset"] - current_offset
                if gap > 0:
                    for duration_name, dots in _split_duration(gap):
                        rest_line = f"{voice_var}.rest({duration_name!r}"
                        if dots:
                            rest_line += f", dots={dots}"
                        rest_line += ")"
                        lines.append(rest_line)

                duration_spec = _exact_duration_spec(event["duration"])
                approximated = duration_spec is None
                if duration_spec is None:
                    duration_spec = _closest_duration_spec(event["duration"])
                duration_name, dots = duration_spec

                if approximated:
                    lines.append(
                        f"# Approximated live snapshot duration at tick {event['tick']}."
                    )

                if event["type"] == "chord" and len(event["pitches"]) > 1:
                    event_line = f"{voice_var}.chord({duration_name!r}, {event['pitches']!r}"
                elif event["type"] == "chord" and event["pitches"]:
                    event_line = f"{voice_var}.note({duration_name!r}, {event['pitches'][0]!r}"
                elif event["type"] == "rest":
                    event_line = f"{voice_var}.rest({duration_name!r}"
                elif event["pitches"]:
                    event_line = f"{voice_var}.note({duration_name!r}, {event['pitches'][0]!r}"
                else:
                    event_line = f"{voice_var}.rest({duration_name!r}"

                if dots:
                    event_line += f", dots={dots}"
                event_line += ")"
                lines.append(event_line)
                current_offset = event["offset"] + event["duration"]

    return "\n".join(lines) + "\n"


class DesktopHummingSession:
    """Record microphone audio, preserve the WAV, and transcribe it."""

    def __init__(
        self,
        *,
        recorder_factory,
        detector,
        wav_writer,
        sample_rate: int,
    ) -> None:
        self._recorder_factory = recorder_factory
        self._detector = detector
        self._wav_writer = wav_writer
        self._sample_rate = sample_rate
        self._recorder = None

    def start_recording(self) -> None:
        if self._recorder is not None:
            raise HummingError("Recording is already in progress.")

        recorder = self._recorder_factory()
        try:
            recorder.start()
        except Exception as exc:
            raise HummingError(str(exc)) from exc

        self._recorder = recorder

    def stop_recording(self) -> CapturedHumming:
        recorder = self._recorder
        if recorder is None:
            raise HummingError("Recording has not started.")

        self._recorder = None
        try:
            audio = recorder.stop()
        except Exception as exc:
            raise HummingError(str(exc)) from exc

        if getattr(audio, "size", 0) == 0:
            return CapturedHumming(notes="", audio_path="", duration_seconds=0.0)

        wav_path = self._wav_writer(audio, sample_rate=self._sample_rate)
        try:
            notes = self._detector(wav_path).strip()
        except Exception as exc:
            wav_path.unlink(missing_ok=True)
            raise HummingError(str(exc)) from exc

        duration_seconds = float(len(audio)) / float(self._sample_rate)
        return CapturedHumming(
            notes=notes,
            audio_path=str(wav_path),
            duration_seconds=duration_seconds,
        )


def _build_default_humming_session() -> DesktopHummingSession:
    try:
        from maestro_humming_detector.api import transcribe_humming
        from maestro_humming_detector.humming_tester import (
            MicrophoneRecorder,
            TARGET_SAMPLE_RATE,
            write_wav_file,
        )
    except ImportError as exc:
        raise HummingError(
            "Humming support is unavailable. Install dependencies for packages/humming-detector first."
        ) from exc

    return DesktopHummingSession(
        recorder_factory=lambda: MicrophoneRecorder(sample_rate=TARGET_SAMPLE_RATE),
        detector=transcribe_humming,
        wav_writer=write_wav_file,
        sample_rate=TARGET_SAMPLE_RATE,
    )


class DesktopAgentBackend:
    """Desktop runtime adapter for both legacy codegen and live score edits."""

    def __init__(
        self,
        *,
        humming_session: DesktopHummingSession | None = None,
        settings_factory=get_legacy_settings,
        live_settings_factory=get_live_edit_settings,
        bridge_client_factory=MuseScoreBridgeClient,
        audio_transcriber=_default_audio_transcriber,
        openai_client_factory=_create_openai_client,
        ollama_requester=_default_ollama_request,
    ) -> None:
        self._humming_session = humming_session
        self._settings_factory = settings_factory
        self._live_settings_factory = live_settings_factory
        self._bridge_client_factory = bridge_client_factory
        self._audio_transcriber = audio_transcriber
        self._openai_client_factory = openai_client_factory
        self._ollama_requester = ollama_requester

    def generate_code(
        self,
        prompt: str,
        api_key: str,
        hummed_notes: str = "",
    ) -> GeneratedScoreCode:
        return legacy_agent_module.generate_score_code_from_prompt(
            prompt,
            api_key,
            self._settings_factory(),
            hummed_notes,
        )

    def apply_live_score_edit(
        self,
        prompt: str,
        *,
        audio_path: str = "",
        api_key: str | None = None,
        provider: ModelProviderConfig | None = None,
    ) -> LiveEditResult:
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise LiveEditError("A text prompt is required to edit the score.")

        hummed_notes = self._transcribe_audio(audio_path)
        settings = self._live_settings_factory()
        resolved_provider = _resolve_model_provider(provider, api_key=api_key, settings=settings)
        bridge_client = self._bridge_client_factory()

        current_score_python = self._load_current_score_python(bridge_client)

        python_code = self._generate_live_edit_code(
            cleaned_prompt,
            resolved_provider,
            settings,
            current_score_python,
            hummed_notes,
        )

        try:
            actions = execute_generated_edit_code(
                python_code,
                current_score_python,
                maestroxml_src_root=settings.maestroxml_src_dir,
                execution_timeout_seconds=settings.execution_timeout_seconds,
            )
        except CoreAgentError as exc:
            raise LiveEditError(str(exc), python_code=python_code) from exc

        if not actions:
            raise LiveEditError(
                "The generated edit produced no bridge actions to apply.",
                python_code=python_code,
            )

        try:
            bridge_result = bridge_client.apply_actions_streamed(
                actions,
                delay_seconds=LIVE_EDIT_STREAM_DELAY_SECONDS,
            )
        except BridgeError as exc:
            raise LiveEditError(str(exc), python_code=python_code) from exc

        return LiveEditResult(
            python_code=python_code,
            action_count=len(actions),
            bridge_result=dict(bridge_result),
            hummed_notes=hummed_notes,
        )

    def start_humming(self) -> None:
        self._get_humming_session().start_recording()

    def stop_humming(self) -> CapturedHumming:
        return self._get_humming_session().stop_recording()

    def _get_humming_session(self) -> DesktopHummingSession:
        if self._humming_session is None:
            self._humming_session = _build_default_humming_session()
        return self._humming_session

    def _transcribe_audio(self, audio_path: str) -> str:
        cleaned_path = audio_path.strip()
        if not cleaned_path:
            return ""

        try:
            return self._audio_transcriber(Path(cleaned_path)).strip()
        except HummingError:
            raise
        except Exception as exc:
            raise HummingError(str(exc)) from exc

    def _export_current_score(self, bridge_client: MuseScoreBridgeClient) -> Path:
        try:
            export_result = bridge_client.export_musicxml()
        except BridgeError as exc:
            raise LiveEditError(str(exc)) from exc

        raw_path = export_result.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise LiveEditError("MuseScore did not return a MusicXML export path.")

        exported_path = Path(raw_path)
        if not exported_path.is_file():
            raise LiveEditError(
                f"MuseScore reported a MusicXML export at {exported_path}, but the file does not exist."
            )

        return exported_path

    def _load_current_score_python(self, bridge_client: MuseScoreBridgeClient) -> str:
        export_error = ""
        try:
            exported_path = self._export_current_score(bridge_client)
        except LiveEditError as exc:
            export_error = str(exc)
        else:
            try:
                return musicxml_to_python(exported_path)
            except Exception as exc:
                export_error = f"Failed to import the current MuseScore score: {exc}"
            finally:
                exported_path.unlink(missing_ok=True)

        try:
            return self._snapshot_current_score(bridge_client)
        except LiveEditError as exc:
            if export_error:
                raise LiveEditError(
                    f"{export_error} Live snapshot fallback also failed: {exc}"
                ) from exc
            raise

    def _snapshot_current_score(self, bridge_client: MuseScoreBridgeClient) -> str:
        try:
            score_info = bridge_client.score_info()
            score_snapshot = bridge_client.read_score()
        except BridgeError as exc:
            raise LiveEditError(str(exc)) from exc

        try:
            return _bridge_snapshot_to_python(score_info, score_snapshot)
        except LiveEditError:
            raise
        except Exception as exc:
            raise LiveEditError(
                f"Failed to build a live score snapshot from MuseScore: {exc}"
            ) from exc

    def _generate_live_edit_code(
        self,
        prompt: str,
        provider: ResolvedModelProvider,
        settings: LiveEditSettings,
        current_score_python: str,
        hummed_notes: str,
    ) -> str:
        try:
            reference_corpus = load_reference_corpus(
                settings.root_dir,
                settings.maestro_skill_dir,
                settings.maestro_docs_dir,
            )
        except ReferenceLoadError as exc:
            raise LiveEditError(str(exc)) from exc

        instructions = build_edit_generation_instructions(reference_corpus)
        model_input = build_edit_model_input(prompt, current_score_python, hummed_notes)
        return self._request_model_output(
            provider,
            settings=settings,
            instructions=instructions,
            model_input=model_input,
        )

    def _request_model_output(
        self,
        provider: ResolvedModelProvider,
        *,
        settings: LiveEditSettings,
        instructions: str,
        model_input: str,
    ) -> str:
        if provider.provider == "openai":
            client = self._openai_client_factory(provider.api_key)
            try:
                response = client.responses.create(
                    model=provider.model,
                    instructions=instructions,
                    input=model_input,
                    reasoning={"effort": settings.openai_reasoning_effort},
                    max_output_tokens=settings.openai_max_output_tokens,
                    store=False,
                    text={"verbosity": "low"},
                )
            except LiveEditError:
                raise
            except Exception as exc:
                raise LiveEditError(f"OpenAI request failed: {exc}") from exc

            status = getattr(response, "status", None)
            if status not in {None, "completed"}:
                raise LiveEditError(response_status_message(response))

            try:
                return extract_output_text(response)
            except CoreAgentError as exc:
                raise LiveEditError(str(exc)) from exc

        if provider.provider == "ollama":
            response = self._ollama_requester(
                provider.base_url,
                {
                    "model": provider.model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": model_input},
                    ],
                },
            )
            return self._extract_ollama_output_text(response)

        raise LiveEditError(f"Unsupported model provider: {provider.provider!r}")

    @staticmethod
    def _extract_ollama_output_text(response: Mapping[str, Any]) -> str:
        message = response.get("message")
        if isinstance(message, Mapping):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

        fallback = response.get("response")
        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip()

        raise LiveEditError("Ollama returned no text output.")
