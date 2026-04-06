from __future__ import annotations

from collections import Counter
import json
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable

from .instruments import resolve_instrument_choice

if TYPE_CHECKING:
    from maestro_musescore_bridge import ActionBatch, MuseScoreBridgeClient

DEFAULT_TICKS_PER_QUARTER = 480

CANONICAL_DURATION_NAMES = {
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

DURATION_VALUES = {
    "whole": Fraction(4, 1),
    "half": Fraction(2, 1),
    "quarter": Fraction(1, 1),
    "eighth": Fraction(1, 2),
    "16th": Fraction(1, 4),
    "32nd": Fraction(1, 8),
    "64th": Fraction(1, 16),
}

CLEF_PRESETS = {
    "treble": ("G", 2),
    "bass": ("F", 4),
    "alto": ("C", 3),
    "tenor": ("C", 4),
    "percussion": ("percussion", 2),
}

INSTRUMENT_PRESETS = {
    "violin": {
        "abbreviation": "Vln.",
        "staves": 1,
        "clefs": ["treble"],
        "instrument_name": "Violin",
        "bridge_instrument_id": "violin",
    },
    "viola": {
        "abbreviation": "Vla.",
        "staves": 1,
        "clefs": ["alto"],
        "instrument_name": "Viola",
        "bridge_instrument_id": "viola",
    },
    "cello": {
        "abbreviation": "Vc.",
        "staves": 1,
        "clefs": ["bass"],
        "instrument_name": "Cello",
        "bridge_instrument_id": "violoncello",
    },
    "piano": {
        "abbreviation": "Pno.",
        "staves": 2,
        "clefs": ["treble", "bass"],
        "instrument_name": "Piano",
        "bridge_instrument_id": "piano",
    },
    "flute": {
        "abbreviation": "Fl.",
        "staves": 1,
        "clefs": ["treble"],
        "instrument_name": "Flute",
        "bridge_instrument_id": "flute",
    },
    "clarinet": {
        "abbreviation": "Cl.",
        "staves": 1,
        "clefs": ["treble"],
        "instrument_name": "Clarinet",
        "bridge_instrument_id": "clarinet",
    },
    "voice": {
        "abbreviation": "V.",
        "staves": 1,
        "clefs": ["treble"],
        "instrument_name": "Voice",
        "bridge_instrument_id": "soprano",
    },
}

MAJOR_KEY_FIFTHS = {
    "cb": -7,
    "gb": -6,
    "db": -5,
    "ab": -4,
    "eb": -3,
    "bb": -2,
    "f": -1,
    "c": 0,
    "g": 1,
    "d": 2,
    "a": 3,
    "e": 4,
    "b": 5,
    "f#": 6,
    "c#": 7,
}

MINOR_KEY_FIFTHS = {
    "ab": -7,
    "eb": -6,
    "bb": -5,
    "f": -4,
    "c": -3,
    "g": -2,
    "d": -1,
    "a": 0,
    "e": 1,
    "b": 2,
    "f#": 3,
    "c#": 4,
    "g#": 5,
    "d#": 6,
    "a#": 7,
}

SUPPORTED_DYNAMIC_TAGS = {
    "pppppp",
    "ppppp",
    "pppp",
    "ppp",
    "pp",
    "p",
    "mp",
    "mf",
    "f",
    "ff",
    "fff",
    "ffff",
    "fffff",
    "ffffff",
    "fp",
    "fz",
    "sf",
    "sfp",
    "sfpp",
    "sfz",
    "sffz",
    "rf",
    "rfz",
    "sfzp",
    "pf",
}

SUPPORTED_ARTICULATIONS = {
    "accent",
    "strong-accent",
    "staccato",
    "tenuto",
    "detached-legato",
    "staccatissimo",
    "spiccato",
    "scoop",
    "plop",
    "doit",
    "falloff",
    "breath-mark",
    "caesura",
    "stress",
    "unstress",
    "soft-accent",
}

BRIDGE_ARTICULATION_SYMBOLS = {
    "accent": "articAccentAbove",
    "strong-accent": "articMarcatoAbove",
    "staccato": "articStaccatoAbove",
    "tenuto": "articTenutoAbove",
    "staccatissimo": "articStaccatissimoAbove",
    "stress": "articStressAbove",
    "unstress": "articUnstressAbove",
    "soft-accent": "articSoftAccentAbove",
}

BRIDGE_ACCIDENTAL_TYPES = {
    "flat": 1,
    "natural": 2,
    "sharp": 3,
    "double-sharp": 4,
    "double-flat": 5,
    "flat-flat": 5,
}

BRIDGE_BEAM_MODES = {
    "begin": 1,
    "continue": 2,
    "end": 3,
    "none": 4,
    "forward hook": 5,
    "backward hook": 6,
}

DEFAULT_TIME_SIGNATURE = (4, 4)
STEP_TO_PITCH_CLASS = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}
SHARP_SPELLINGS = {
    0: ("C", None),
    1: ("C", 1),
    2: ("D", None),
    3: ("D", 1),
    4: ("E", None),
    5: ("F", None),
    6: ("F", 1),
    7: ("G", None),
    8: ("G", 1),
    9: ("A", None),
    10: ("A", 1),
    11: ("B", None),
}
FLAT_SPELLINGS = {
    0: ("C", None),
    1: ("D", -1),
    2: ("D", None),
    3: ("E", -1),
    4: ("E", None),
    5: ("F", None),
    6: ("G", -1),
    7: ("G", None),
    8: ("A", -1),
    9: ("A", None),
    10: ("B", -1),
    11: ("B", None),
}


@dataclass(frozen=True)
class Clef:
    sign: str
    line: int


@dataclass(frozen=True)
class Pitch:
    step: str
    octave: int
    alter: int | None = None


@dataclass(frozen=True)
class TupletSpec:
    actual_notes: int
    normal_notes: int
    normal_type: str | None = None


@dataclass
class MeasureBarline:
    repeat: str | None = None
    times: int | None = None
    ending_number: str | None = None
    ending_type: str | None = None


@dataclass
class NoteEvent:
    sequence: int
    offset: Fraction
    duration: Fraction
    duration_name: str
    voice: int
    staff: int
    pitches: tuple[Pitch, ...] = ()
    is_rest: bool = False
    dots: int = 0
    tuplet: TupletSpec | None = None
    ties: tuple[str, ...] = ()
    slurs: tuple[str, ...] = ()
    articulations: tuple[str, ...] = ()
    accidental: str | None = None
    beams: tuple[str, ...] = ()


@dataclass
class DirectionEvent:
    sequence: int
    offset: Fraction
    voice: int
    staff: int
    kind: str
    placement: str | None
    data: dict[str, object]


Event = NoteEvent | DirectionEvent


@dataclass
class StreamTimeline:
    events: list[Event] = field(default_factory=list)
    offset: Fraction = Fraction(0)


@dataclass
class MeasureState:
    number: int
    clefs: dict[int, Clef] = field(default_factory=dict)
    streams: dict[tuple[int, int], StreamTimeline] = field(default_factory=dict)
    left_barline: MeasureBarline = field(default_factory=MeasureBarline)
    right_barline: MeasureBarline = field(default_factory=MeasureBarline)


def _normalize_duration_name(duration: str) -> str:
    candidate = duration.strip().lower()
    canonical = CANONICAL_DURATION_NAMES.get(candidate)
    if canonical is None:
        canonical = CANONICAL_DURATION_NAMES.get(candidate.replace("-", " "))
    if canonical is None:
        raise ValueError(f"Unsupported duration name: {duration!r}")
    return canonical


def _parse_duration_spec(duration: str, dots: int = 0) -> tuple[str, int]:
    cleaned = duration.strip().lower()
    normalized = " ".join(cleaned.replace("-", " ").split())
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

    duration_name = _normalize_duration_name(normalized)
    return duration_name, total_dots


def _coerce_sequence(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _normalize_tie_or_slur(
    value: str | Iterable[str] | None, label: str
) -> tuple[str, ...]:
    raw_values = _coerce_sequence(value)
    result: list[str] = []
    for item in raw_values:
        lowered = item.strip().lower()
        if lowered == "continue":
            result.extend(["stop", "start"])
            continue
        if lowered not in {"start", "stop"}:
            raise ValueError(f"Unsupported {label} type: {item!r}")
        result.append(lowered)
    return tuple(result)


def _normalize_articulations(value: str | Iterable[str] | None) -> tuple[str, ...]:
    articulations = _coerce_sequence(value)
    normalized: list[str] = []
    for articulation in articulations:
        lowered = articulation.strip().lower()
        if lowered not in SUPPORTED_ARTICULATIONS:
            raise ValueError(f"Unsupported articulation: {articulation!r}")
        normalized.append(lowered)
    return tuple(normalized)


def _parse_pitch(value: str) -> Pitch:
    stripped = value.strip()
    if len(stripped) < 2:
        raise ValueError(f"Invalid pitch: {value!r}")

    step = stripped[0].upper()
    if step not in {"A", "B", "C", "D", "E", "F", "G"}:
        raise ValueError(f"Invalid pitch step: {value!r}")

    index = 1
    accidental = ""
    while index < len(stripped) and stripped[index] in {"#", "b", "n"}:
        accidental += stripped[index]
        index += 1

    octave_text = stripped[index:]
    if not octave_text or not octave_text.lstrip("-").isdigit():
        raise ValueError(f"Invalid pitch octave: {value!r}")

    alter_map = {
        "": None,
        "#": 1,
        "##": 2,
        "b": -1,
        "bb": -2,
        "n": 0,
    }
    if accidental not in alter_map:
        raise ValueError(f"Unsupported accidental in pitch: {value!r}")

    return Pitch(step=step, alter=alter_map[accidental], octave=int(octave_text))


def _duration_fraction(
    duration: str, dots: int = 0, tuplet: TupletSpec | None = None
) -> Fraction:
    base = DURATION_VALUES[_normalize_duration_name(duration)]
    total = base
    current = base
    for _ in range(dots):
        current /= 2
        total += current
    if tuplet is not None:
        total *= Fraction(tuplet.normal_notes, tuplet.actual_notes)
    return total


def _parse_tuplet(
    tuplet: tuple[int, int] | tuple[int, int, str] | None, duration_name: str
) -> TupletSpec | None:
    if tuplet is None:
        return None
    if len(tuplet) not in {2, 3}:
        raise ValueError(
            "Tuplets must be (actual_notes, normal_notes) or (actual_notes, normal_notes, normal_type)"
        )
    actual_notes, normal_notes = int(tuplet[0]), int(tuplet[1])
    if actual_notes <= 0 or normal_notes <= 0:
        raise ValueError("Tuplet note counts must be positive integers")
    normal_type = (
        _normalize_duration_name(tuplet[2]) if len(tuplet) == 3 else duration_name
    )
    return TupletSpec(
        actual_notes=actual_notes, normal_notes=normal_notes, normal_type=normal_type
    )


def _parse_clef(value: str | tuple[str, int]) -> Clef:
    if isinstance(value, tuple):
        sign, line = value
        return Clef(sign=str(sign), line=int(line))

    normalized = value.strip().lower()
    if normalized not in CLEF_PRESETS:
        raise ValueError(f"Unsupported clef: {value!r}")
    sign, line = CLEF_PRESETS[normalized]
    return Clef(sign=sign, line=line)


def _parse_time_signature(
    signature: str | tuple[int, int] | list[int] | int, beat_type: int | None = None
) -> tuple[int, int]:
    if isinstance(signature, str):
        cleaned = signature.replace(",", "/")
        beats_text, beat_type_text = [piece.strip() for piece in cleaned.split("/", 1)]
        return int(beats_text), int(beat_type_text)
    if isinstance(signature, (tuple, list)):
        beats, beat = signature
        return int(beats), int(beat)
    if beat_type is None:
        raise ValueError(
            "beat_type is required when the time signature numerator is given directly"
        )
    return int(signature), int(beat_type)


def _parse_key_signature(
    signature: str | int, mode: str | None = None
) -> tuple[int, str]:
    if isinstance(signature, str):
        tokens = signature.strip().split()
        if len(tokens) != 2:
            raise ValueError("Key signatures must look like 'C major' or 'A minor'")
        tonic, mode_text = tokens
        mode_normalized = mode_text.lower()
        tonic_normalized = tonic.lower()
        table = (
            MAJOR_KEY_FIFTHS
            if mode_normalized == "major"
            else MINOR_KEY_FIFTHS
            if mode_normalized == "minor"
            else None
        )
        if table is None or tonic_normalized not in table:
            raise ValueError(f"Unsupported key signature: {signature!r}")
        return table[tonic_normalized], mode_normalized

    mode_normalized = (mode or "major").strip().lower()
    if mode_normalized not in {"major", "minor"}:
        raise ValueError(f"Unsupported key mode: {mode!r}")
    fifths = int(signature)
    if fifths < -7 or fifths > 7:
        raise ValueError("MusicXML key signatures use fifths in the range -7..7")
    return fifths, mode_normalized


def _pitch_to_string(pitch: Pitch) -> str:
    pitch = _simplify_pitch(pitch)
    accidental_map = {
        None: "",
        -2: "bb",
        -1: "b",
        1: "#",
        2: "##",
    }
    accidental = accidental_map.get(pitch.alter)
    if accidental is None:
        raise ValueError(f"Unsupported pitch alteration for bridge output: {pitch.alter}")
    return f"{pitch.step}{accidental}{pitch.octave}"


def _simplify_pitch(pitch: Pitch) -> Pitch:
    alter = 0 if pitch.alter is None else pitch.alter
    if alter in {-1, 0, 1}:
        return Pitch(step=pitch.step, octave=pitch.octave, alter=None if alter == 0 else alter)

    midi = (pitch.octave + 1) * 12 + STEP_TO_PITCH_CLASS[pitch.step] + alter
    pitch_class = midi % 12
    step, simplified_alter = (
        SHARP_SPELLINGS[pitch_class] if alter > 0 else FLAT_SPELLINGS[pitch_class]
    )
    simple_pitch_class = STEP_TO_PITCH_CLASS[step] + (simplified_alter or 0)
    octave = ((midi - simple_pitch_class) // 12) - 1
    return Pitch(step=step, octave=octave, alter=simplified_alter)


def _ticks_from_quarter_fraction(value: Fraction) -> int:
    ticks = value * DEFAULT_TICKS_PER_QUARTER
    if ticks.denominator != 1:
        raise ValueError(
            "This rhythm cannot be represented exactly with the MuseScore bridge "
            f"tick grid ({value} quarter-notes)."
        )
    return int(ticks)


def _measure_length_ticks(beats: int, beat_type: int) -> int:
    return _ticks_from_quarter_fraction(Fraction(4 * beats, beat_type))


def _duration_name_from_fraction(value: Fraction) -> str:
    for duration_name, fraction in DURATION_VALUES.items():
        if fraction == value:
            return duration_name
    raise ValueError(f"Unsupported duration fraction for bridge output: {value}")


def _tuplet_total_duration_name(tuplet: TupletSpec) -> str:
    normal_type = tuplet.normal_type or "quarter"
    total_duration = DURATION_VALUES[normal_type] * tuplet.normal_notes
    return _duration_name_from_fraction(total_duration)


def _direction_text(kind: str) -> str | None:
    if kind == "crescendo":
        return "cresc."
    if kind == "diminuendo":
        return "dim."
    return None


def _bridge_import_error(name: str, error: ImportError) -> RuntimeError:
    bridge_error = RuntimeError(
        f"{name} requires the `maestro-musescore-bridge` package to be importable. "
        "Install it alongside `maestroxml` or add it to PYTHONPATH."
    )
    bridge_error.__cause__ = error
    return bridge_error


class Score:
    def __init__(
        self,
        *,
        title: str | None = None,
        composer: str | None = None,
        lyricist: str | None = None,
        rights: str | None = None,
    ) -> None:
        self.title = title
        self.composer = composer
        self.lyricist = lyricist
        self.rights = rights
        self.parts: list[Part] = []
        self.current_measure: int | None = None
        self._max_measure = 0
        self._time_changes: dict[int, tuple[int, int]] = {}
        self._key_changes: dict[int, tuple[int, str]] = {}

    def add_part(
        self,
        name: str,
        *,
        instrument: str | None = None,
        abbreviation: str | None = None,
        staves: int | None = None,
        clefs: Iterable[str | tuple[str, int]] | None = None,
    ) -> Part:
        instrument_key = (instrument or name).strip().lower()
        preset = INSTRUMENT_PRESETS.get(instrument_key, {})

        resolved_staves = int(staves if staves is not None else preset.get("staves", 1))
        resolved_abbreviation = (
            abbreviation if abbreviation is not None else preset.get("abbreviation")
        )

        if clefs is None:
            clef_specs = tuple(
                _parse_clef(spec) for spec in preset.get("clefs", ("treble",))
            )
        else:
            clef_specs = tuple(_parse_clef(spec) for spec in clefs)
        if len(clef_specs) != resolved_staves:
            raise ValueError("The number of clefs must match the part's staff count")

        bridge_instrument_id = preset.get("bridge_instrument_id")
        bridge_musicxml_id = None
        resolved_instrument_name = str(preset.get("instrument_name", instrument or name))
        if bridge_instrument_id is None:
            resolved_instrument = resolve_instrument_choice(instrument or name)
            if resolved_instrument is not None:
                resolved_instrument_name = resolved_instrument.label
                bridge_instrument_id = resolved_instrument.bridge_instrument_id
                bridge_musicxml_id = resolved_instrument.musicxml_id
            else:
                bridge_musicxml_id = instrument or instrument_key.replace(" ", "-")

        part = Part(
            score=self,
            part_id=f"P{len(self.parts) + 1}",
            name=name,
            abbreviation=resolved_abbreviation,
            instrument_name=resolved_instrument_name,
            staves=resolved_staves,
            initial_clefs={index + 1: clef for index, clef in enumerate(clef_specs)},
            bridge_instrument_id=str(bridge_instrument_id) if bridge_instrument_id else None,
            bridge_musicxml_id=bridge_musicxml_id,
        )
        self.parts.append(part)

        if self._max_measure:
            for measure_number in range(1, self._max_measure + 1):
                part._ensure_measure(measure_number)

        return part

    def measure(self, number: int | None = None) -> Score:
        if number is None:
            number = 1 if self.current_measure is None else self.current_measure + 1
        if number <= 0:
            raise ValueError("Measure numbers must be positive integers")

        self.current_measure = int(number)
        self._max_measure = max(self._max_measure, self.current_measure)
        for part in self.parts:
            part._ensure_measure(self.current_measure)
        return self

    def time_signature(
        self,
        signature: str | tuple[int, int] | list[int] | int,
        beat_type: int | None = None,
    ) -> Score:
        self._require_active_measure()
        value = _parse_time_signature(signature, beat_type)
        previous = self._latest_change_before(self._time_changes, self.current_measure)
        if previous == value:
            self._time_changes.pop(self.current_measure, None)
        else:
            self._time_changes[self.current_measure] = value
        return self

    def key_signature(self, signature: str | int, mode: str | None = None) -> Score:
        self._require_active_measure()
        value = _parse_key_signature(signature, mode)
        previous = self._latest_change_before(self._key_changes, self.current_measure)
        if previous == value:
            self._key_changes.pop(self.current_measure, None)
        else:
            self._key_changes[self.current_measure] = value
        return self

    def unsupported_features(self) -> list[str]:
        unsupported: set[str] = set()
        for part in self.parts:
            for measure in part.measures.values():
                if measure.clefs:
                    unsupported.add("clef changes")
                if measure.left_barline.repeat == "forward":
                    unsupported.add("repeat start barlines")
                if measure.left_barline.ending_number or measure.right_barline.ending_number:
                    unsupported.add("volta endings")
                if measure.right_barline.repeat == "backward":
                    unsupported.add("repeat end barlines")
                for stream in measure.streams.values():
                    for event in stream.events:
                        if isinstance(event, DirectionEvent):
                            if event.kind == "wedge":
                                unsupported.add("wedge spanners")
                            continue
                        if event.ties:
                            unsupported.add("ties")
                        if event.slurs:
                            unsupported.add("slurs")
                        unsupported_articulations = set(event.articulations) - (
                            set(BRIDGE_ARTICULATION_SYMBOLS) | {"breath-mark", "caesura"}
                        )
                        if unsupported_articulations:
                            unsupported.add("some articulations")
        return sorted(unsupported)

    def to_actions(
        self,
        *,
        include_structure: bool = True,
        ignore_unsupported: bool = True,
    ) -> list[dict[str, Any]]:
        if not self.parts:
            raise ValueError("Score has no parts. Add at least one part before exporting.")
        if self.current_measure is None:
            raise ValueError("Score has no measures. Call measure() before exporting.")

        unsupported = self.unsupported_features()
        if unsupported and not ignore_unsupported:
            joined = ", ".join(unsupported)
            raise ValueError(
                "This score contains features the current MuseScore bridge backend cannot write: "
                f"{joined}."
            )

        actions: list[dict[str, Any]] = []
        self._append_metadata_actions(actions)
        if include_structure:
            self._append_structure_actions(actions)

        measure_ticks = self._measure_start_ticks()
        staff_offsets = self._part_staff_offsets()

        for measure_number in range(1, self._max_measure + 1):
            measure_tick = measure_ticks[measure_number]
            if measure_number in self._time_changes:
                beats, beat_type = self._time_changes[measure_number]
                actions.append(
                    {
                        "kind": "add_time_signature",
                        "numerator": beats,
                        "denominator": beat_type,
                        "tick": measure_tick,
                        "staff": 0,
                    }
                )
            if measure_number in self._key_changes:
                fifths, _mode = self._key_changes[measure_number]
                actions.append(
                    {
                        "kind": "add_key_signature",
                        "key": fifths,
                        "tick": measure_tick,
                        "all_staves": True,
                    }
                )

            for part in self.parts:
                measure = part._ensure_measure(measure_number)
                part_staff_offset = staff_offsets[part.part_id]

                if (
                    measure.right_barline.repeat == "backward"
                    and measure.right_barline.times is not None
                ):
                    actions.append(
                        {
                            "kind": "modify_measure",
                            "tick": measure_tick,
                            "repeatCount": measure.right_barline.times,
                        }
                    )

                for (staff, voice), stream in sorted(
                    measure.streams.items(), key=lambda item: (item[0][0], item[0][1])
                ):
                    global_staff = part_staff_offset + staff - 1
                    voice_index = voice - 1
                    active_tuplet: tuple[TupletSpec, int] | None = None

                    for event in sorted(
                        stream.events, key=lambda current: (current.offset, current.sequence)
                    ):
                        event_tick = measure_tick + _ticks_from_quarter_fraction(event.offset)
                        if isinstance(event, DirectionEvent):
                            self._append_direction_actions(
                                actions,
                                event,
                                tick=event_tick,
                                global_staff=global_staff,
                            )
                            continue

                        if event.tuplet is not None:
                            if active_tuplet is None or active_tuplet[0] != event.tuplet:
                                actions.append(
                                    {
                                        "kind": "add_tuplet",
                                        "tick": event_tick,
                                        "staff": global_staff,
                                        "voice": voice_index,
                                        "actual": event.tuplet.actual_notes,
                                        "normal": event.tuplet.normal_notes,
                                        "totalDuration": _tuplet_total_duration_name(event.tuplet),
                                    }
                                )
                                active_tuplet = (event.tuplet, event.tuplet.actual_notes)
                            remaining = active_tuplet[1] - 1
                            active_tuplet = None if remaining <= 0 else (active_tuplet[0], remaining)
                        else:
                            active_tuplet = None

                        self._append_note_actions(
                            actions,
                            event,
                            tick=event_tick,
                            global_staff=global_staff,
                            voice_index=voice_index,
                        )

        return actions

    def to_batch(
        self,
        *,
        include_structure: bool = True,
        ignore_unsupported: bool = True,
    ) -> ActionBatch:
        try:
            from maestro_musescore_bridge import ActionBatch
        except ImportError as error:
            raise _bridge_import_error("Score.to_batch()", error)
        return ActionBatch(
            self.to_actions(
                include_structure=include_structure,
                ignore_unsupported=ignore_unsupported,
            )
        )

    def to_string(
        self,
        *,
        include_structure: bool = True,
        ignore_unsupported: bool = True,
    ) -> str:
        return json.dumps(
            self.to_actions(
                include_structure=include_structure,
                ignore_unsupported=ignore_unsupported,
            ),
            indent=2,
        ) + "\n"

    def write(
        self,
        path: str | Path,
        *,
        include_structure: bool = True,
        ignore_unsupported: bool = True,
    ) -> Path:
        destination = Path(path)
        destination.write_text(
            self.to_string(
                include_structure=include_structure,
                ignore_unsupported=ignore_unsupported,
            ),
            encoding="utf-8",
        )
        return destination

    def apply(
        self,
        client: MuseScoreBridgeClient | None = None,
        *,
        fail_on_partial: bool = True,
        include_structure: bool = True,
        ignore_unsupported: bool = True,
    ) -> Any:
        actions = self.to_actions(
            include_structure=include_structure,
            ignore_unsupported=ignore_unsupported,
        )
        if client is None:
            try:
                from maestro_musescore_bridge import MuseScoreBridgeClient
            except ImportError as error:
                raise _bridge_import_error("Score.apply()", error)
            client = MuseScoreBridgeClient()
        return client.apply_actions(actions, fail_on_partial=fail_on_partial)

    def _require_active_measure(self) -> int:
        if self.current_measure is None:
            raise ValueError("Call measure() before writing score content.")
        return self.current_measure

    @staticmethod
    def _latest_change_before(
        changes: dict[int, object], measure_number: int | None
    ) -> object | None:
        if measure_number is None:
            return None
        latest_measure = -1
        latest_value = None
        for candidate_measure, value in changes.items():
            if candidate_measure < measure_number and candidate_measure > latest_measure:
                latest_measure = candidate_measure
                latest_value = value
        return latest_value

    def _append_metadata_actions(self, actions: list[dict[str, Any]]) -> None:
        if self.title:
            actions.append(
                {"kind": "set_header_text", "type": "title", "text": self.title}
            )
        if self.composer:
            actions.append(
                {"kind": "set_header_text", "type": "composer", "text": self.composer}
            )
            actions.append(
                {"kind": "set_meta_tag", "tag": "composer", "value": self.composer}
            )
        if self.lyricist:
            actions.append(
                {"kind": "set_header_text", "type": "poet", "text": self.lyricist}
            )
            actions.append(
                {"kind": "set_meta_tag", "tag": "lyricist", "value": self.lyricist}
            )
        if self.rights:
            actions.append(
                {"kind": "set_meta_tag", "tag": "rights", "value": self.rights}
            )

    def _append_structure_actions(self, actions: list[dict[str, Any]]) -> None:
        for part in self.parts[1:]:
            actions.append(self._part_append_action(part))

        additional_measures = max(0, self._max_measure - 1)
        if additional_measures:
            actions.append({"kind": "append_measures", "count": additional_measures})

    @staticmethod
    def _part_append_action(part: Part) -> dict[str, Any]:
        payload: dict[str, Any] = {"kind": "add_part"}
        if part.bridge_instrument_id:
            payload["instrumentId"] = part.bridge_instrument_id
        elif part.bridge_musicxml_id:
            payload["musicXmlId"] = part.bridge_musicxml_id
        elif part.instrument_name:
            payload["instrumentName"] = part.instrument_name
        else:
            payload["instrumentId"] = "piano"
        return payload

    def clone_shell(self) -> Score:
        cloned = Score(
            title=self.title,
            composer=self.composer,
            lyricist=self.lyricist,
            rights=self.rights,
        )

        for part in self.parts:
            clefs = tuple(
                (part.initial_clefs.get(staff) or Clef(*CLEF_PRESETS["treble"]))
                for staff in range(1, part.staves + 1)
            )
            clone_part = cloned.add_part(
                part.name,
                instrument=(
                    part.bridge_instrument_id
                    or part.bridge_musicxml_id
                    or part.instrument_name
                    or part.name
                ),
                abbreviation=part.abbreviation,
                staves=part.staves,
                clefs=((clef.sign, clef.line) for clef in clefs),
            )
            clone_part.bridge_instrument_id = part.bridge_instrument_id
            clone_part.bridge_musicxml_id = part.bridge_musicxml_id
            clone_part.instrument_name = part.instrument_name

        for measure_number in range(1, self._max_measure + 1):
            cloned.measure(measure_number)
            time_signature = self._time_changes.get(measure_number)
            if time_signature is not None:
                cloned.time_signature(time_signature)
            key_signature = self._key_changes.get(measure_number)
            if key_signature is not None:
                cloned.key_signature(key_signature[0], mode=key_signature[1])

        return cloned

    def to_delta_actions(
        self,
        base_score: Score,
        *,
        ignore_unsupported: bool = True,
    ) -> list[dict[str, Any]]:
        if len(self.parts) < len(base_score.parts):
            raise ValueError("Live edit scores cannot remove existing parts.")
        if self._max_measure < base_score._max_measure:
            raise ValueError("Live edit scores cannot remove existing measures.")

        for index, base_part in enumerate(base_score.parts):
            current_part = self.parts[index]
            if current_part.staves != base_part.staves:
                raise ValueError("Live edit scores cannot change existing part staff counts.")
            if current_part.bridge_instrument_id != base_part.bridge_instrument_id:
                raise ValueError("Live edit scores cannot replace existing part instruments.")
            if current_part.bridge_musicxml_id != base_part.bridge_musicxml_id:
                raise ValueError("Live edit scores cannot replace existing part MusicXML ids.")

        current_actions = self.to_actions(
            include_structure=False,
            ignore_unsupported=ignore_unsupported,
        )
        base_actions = base_score.to_actions(
            include_structure=False,
            ignore_unsupported=ignore_unsupported,
        )

        base_counts: Counter[str] = Counter(
            json.dumps(action, sort_keys=True) for action in base_actions
        )

        delta_actions: list[dict[str, Any]] = []
        extra_parts = self.parts[len(base_score.parts) :]
        for part in extra_parts:
            delta_actions.append(self._part_append_action(part))

        extra_measures = max(0, self._max_measure - base_score._max_measure)
        if extra_measures:
            delta_actions.append({"kind": "append_measures", "count": extra_measures})

        for action in current_actions:
            key = json.dumps(action, sort_keys=True)
            if base_counts[key]:
                base_counts[key] -= 1
                continue
            delta_actions.append(action)

        return delta_actions

    def _measure_start_ticks(self) -> dict[int, int]:
        ticks: dict[int, int] = {}
        current_time = self._time_changes.get(1, DEFAULT_TIME_SIGNATURE)
        current_tick = 0
        for measure_number in range(1, self._max_measure + 1):
            if measure_number in self._time_changes:
                current_time = self._time_changes[measure_number]
            ticks[measure_number] = current_tick
            current_tick += _measure_length_ticks(*current_time)
        return ticks

    def _part_staff_offsets(self) -> dict[str, int]:
        offsets: dict[str, int] = {}
        running = 0
        for part in self.parts:
            offsets[part.part_id] = running
            running += part.staves
        return offsets

    def _append_direction_actions(
        self,
        actions: list[dict[str, Any]],
        event: DirectionEvent,
        *,
        tick: int,
        global_staff: int,
    ) -> None:
        if event.kind == "tempo":
            actions.append(
                {
                    "kind": "add_tempo",
                    "bpm": event.data["bpm"],
                    "text": event.data.get("text"),
                    "tick": tick,
                    "staff": global_staff,
                }
            )
            return

        if event.kind == "dynamic":
            actions.append(
                {
                    "kind": "add_dynamic",
                    "text": event.data["mark"],
                    "tick": tick,
                    "staff": global_staff,
                }
            )
            return

        if event.kind == "text":
            action_kind = (
                "add_expression_text"
                if event.placement == "below"
                else "add_staff_text"
            )
            actions.append(
                {
                    "kind": action_kind,
                    "text": event.data["content"],
                    "tick": tick,
                    "staff": global_staff,
                }
            )
            return

        if event.kind == "wedge":
            text = _direction_text(str(event.data["type"]))
            if text:
                actions.append(
                    {
                        "kind": "add_expression_text",
                        "text": text,
                        "tick": tick,
                        "staff": global_staff,
                    }
                )
            return

        raise ValueError(f"Unsupported direction type: {event.kind}")

    def _append_note_actions(
        self,
        actions: list[dict[str, Any]],
        event: NoteEvent,
        *,
        tick: int,
        global_staff: int,
        voice_index: int,
    ) -> None:
        base_action: dict[str, Any] = {
            "tick": tick,
            "staff": global_staff,
            "voice": voice_index,
        }
        if event.dots:
            base_action["dots"] = event.dots

        if event.is_rest:
            actions.append(
                {
                    "kind": "add_rest",
                    "duration": event.duration_name,
                    **base_action,
                }
            )
        elif len(event.pitches) == 1:
            actions.append(
                {
                    "kind": "add_note",
                    "pitch": _pitch_to_string(event.pitches[0]),
                    "duration": event.duration_name,
                    **base_action,
                }
            )
        else:
            actions.append(
                {
                    "kind": "add_chord",
                    "pitches": [_pitch_to_string(pitch) for pitch in event.pitches],
                    "duration": event.duration_name,
                    **base_action,
                }
            )

        if event.accidental:
            accidental_type = BRIDGE_ACCIDENTAL_TYPES.get(event.accidental.strip().lower())
            if accidental_type is not None:
                for note_index in range(len(event.pitches) or 1):
                    actions.append(
                        {
                            "kind": "modify_note",
                            "tick": tick,
                            "staff": global_staff,
                            "voice": voice_index,
                            "noteIndex": note_index,
                            "accidentalType": accidental_type,
                        }
                    )

        if event.beams:
            beam_mode = BRIDGE_BEAM_MODES.get(event.beams[0].strip().lower())
            if beam_mode is not None:
                actions.append(
                    {
                        "kind": "modify_chord",
                        "tick": tick,
                        "staff": global_staff,
                        "voice": voice_index,
                        "beamMode": beam_mode,
                    }
                )

        for articulation in event.articulations:
            if articulation in {"breath-mark", "caesura"}:
                actions.append(
                    {"kind": "add_breath", "tick": tick, "staff": global_staff}
                )
                continue
            symbol = BRIDGE_ARTICULATION_SYMBOLS.get(articulation)
            if symbol is None:
                continue
            actions.append(
                {
                    "kind": "add_articulation",
                    "tick": tick,
                    "staff": global_staff,
                    "voice": voice_index,
                    "symbol": symbol,
                }
            )


class Part:
    def __init__(
        self,
        *,
        score: Score,
        part_id: str,
        name: str,
        abbreviation: str | None,
        instrument_name: str,
        staves: int,
        initial_clefs: dict[int, Clef],
        bridge_instrument_id: str | None,
        bridge_musicxml_id: str | None,
    ) -> None:
        self.score = score
        self.part_id = part_id
        self.name = name
        self.abbreviation = abbreviation
        self.instrument_name = instrument_name
        self.staves = staves
        self.initial_clefs = dict(initial_clefs)
        self.bridge_instrument_id = bridge_instrument_id
        self.bridge_musicxml_id = bridge_musicxml_id
        self.measures: dict[int, MeasureState] = {}
        self._event_sequence = 0
        self._voice_cache: dict[tuple[int, int], VoiceCursor] = {}

    def voice(self, number: int, staff: int = 1) -> VoiceCursor:
        if number <= 0:
            raise ValueError("Voice numbers must be positive integers")
        if staff <= 0 or staff > self.staves:
            raise ValueError(f"Staff must be between 1 and {self.staves}")
        key = (staff, number)
        if key not in self._voice_cache:
            self._voice_cache[key] = VoiceCursor(part=self, voice=number, staff=staff)
        return self._voice_cache[key]

    def measure(self, number: int | None = None) -> Part:
        self.score.measure(number)
        return self

    def note(self, duration: str, pitch: str, **kwargs: object) -> Part:
        self.voice(1, 1).note(duration, pitch, **kwargs)
        return self

    def notes(self, duration: str, pitches: Iterable[str], **kwargs: object) -> Part:
        self.voice(1, 1).notes(duration, pitches, **kwargs)
        return self

    def rest(self, duration: str, **kwargs: object) -> Part:
        self.voice(1, 1).rest(duration, **kwargs)
        return self

    def chord(self, duration: str, pitches: Iterable[str], **kwargs: object) -> Part:
        self.voice(1, 1).chord(duration, pitches, **kwargs)
        return self

    def tempo(
        self,
        bpm: int | float,
        *,
        beat_unit: str = "quarter",
        text: str | None = None,
        placement: str = "above",
    ) -> Part:
        self.voice(1, 1).tempo(bpm, beat_unit=beat_unit, text=text, placement=placement)
        return self

    def dynamic(self, mark: str, *, placement: str = "below") -> Part:
        self.voice(1, 1).dynamic(mark, placement=placement)
        return self

    def text(self, content: str, *, placement: str = "above") -> Part:
        self.voice(1, 1).text(content, placement=placement)
        return self

    def wedge(self, type: str, *, placement: str = "below") -> Part:
        self.voice(1, 1).wedge(type, placement=placement)
        return self

    def clef(self, clef: str | tuple[str, int], *, staff: int = 1) -> Part:
        measure = self._current_measure()
        resolved = _parse_clef(clef)
        previous = self._latest_clef_before(measure.number, staff)
        if previous == resolved:
            measure.clefs.pop(staff, None)
        else:
            measure.clefs[staff] = resolved
        if measure.number == 1:
            self.initial_clefs[staff] = resolved
        return self

    def repeat_start(self) -> Part:
        measure = self._current_measure()
        measure.left_barline.repeat = "forward"
        return self

    def repeat_end(self, times: int | None = None) -> Part:
        measure = self._current_measure()
        measure.right_barline.repeat = "backward"
        measure.right_barline.times = times
        return self

    def ending(self, number: int | str, type: str) -> Part:
        normalized_type = type.strip().lower()
        if normalized_type not in {"start", "stop", "discontinue"}:
            raise ValueError("Ending type must be start, stop, or discontinue")
        target = (
            self._current_measure().left_barline
            if normalized_type == "start"
            else self._current_measure().right_barline
        )
        target.ending_number = str(number)
        target.ending_type = normalized_type
        return self

    def _current_measure(self) -> MeasureState:
        return self._ensure_measure(self.score._require_active_measure())

    def _ensure_measure(self, number: int) -> MeasureState:
        if number not in self.measures:
            self.measures[number] = MeasureState(number=number)
        return self.measures[number]

    def _latest_clef_before(self, measure_number: int, staff: int) -> Clef | None:
        latest_measure = 0
        latest = self.initial_clefs.get(staff)
        for candidate_measure, measure in self.measures.items():
            if candidate_measure >= measure_number:
                continue
            if staff in measure.clefs and candidate_measure > latest_measure:
                latest_measure = candidate_measure
                latest = measure.clefs[staff]
        return latest

    def _next_sequence(self) -> int:
        self._event_sequence += 1
        return self._event_sequence

    def _stream(self, voice: int, staff: int) -> StreamTimeline:
        measure = self._current_measure()
        key = (staff, voice)
        if key not in measure.streams:
            measure.streams[key] = StreamTimeline()
        return measure.streams[key]


class VoiceCursor:
    def __init__(self, *, part: Part, voice: int, staff: int) -> None:
        self.part = part
        self.voice = voice
        self.staff = staff

    def note(
        self,
        duration: str,
        pitch: str,
        *,
        dots: int = 0,
        tuplet: tuple[int, int] | tuple[int, int, str] | None = None,
        tie: str | Iterable[str] | None = None,
        slur: str | Iterable[str] | None = None,
        articulations: str | Iterable[str] | None = None,
        accidental: str | None = None,
        beams: Iterable[str] | None = None,
    ) -> VoiceCursor:
        stream = self.part._stream(self.voice, self.staff)
        duration_name, total_dots = _parse_duration_spec(duration, dots=dots)
        tuplet_spec = _parse_tuplet(tuplet, duration_name)
        event = NoteEvent(
            sequence=self.part._next_sequence(),
            offset=stream.offset,
            duration=_duration_fraction(duration_name, dots=total_dots, tuplet=tuplet_spec),
            duration_name=duration_name,
            voice=self.voice,
            staff=self.staff,
            pitches=(_parse_pitch(pitch),),
            dots=total_dots,
            tuplet=tuplet_spec,
            ties=_normalize_tie_or_slur(tie, "tie"),
            slurs=_normalize_tie_or_slur(slur, "slur"),
            articulations=_normalize_articulations(articulations),
            accidental=accidental,
            beams=tuple(beams or ()),
        )
        stream.events.append(event)
        stream.offset += event.duration
        return self

    def notes(
        self, duration: str, pitches: Iterable[str], **kwargs: object
    ) -> VoiceCursor:
        for pitch in pitches:
            self.note(duration, pitch, **kwargs)
        return self

    def rest(
        self,
        duration: str,
        *,
        dots: int = 0,
        tuplet: tuple[int, int] | tuple[int, int, str] | None = None,
        beams: Iterable[str] | None = None,
    ) -> VoiceCursor:
        stream = self.part._stream(self.voice, self.staff)
        duration_name, total_dots = _parse_duration_spec(duration, dots=dots)
        tuplet_spec = _parse_tuplet(tuplet, duration_name)
        event = NoteEvent(
            sequence=self.part._next_sequence(),
            offset=stream.offset,
            duration=_duration_fraction(duration_name, dots=total_dots, tuplet=tuplet_spec),
            duration_name=duration_name,
            voice=self.voice,
            staff=self.staff,
            is_rest=True,
            dots=total_dots,
            tuplet=tuplet_spec,
            beams=tuple(beams or ()),
        )
        stream.events.append(event)
        stream.offset += event.duration
        return self

    def chord(
        self,
        duration: str,
        pitches: Iterable[str],
        *,
        dots: int = 0,
        tuplet: tuple[int, int] | tuple[int, int, str] | None = None,
        tie: str | Iterable[str] | None = None,
        slur: str | Iterable[str] | None = None,
        articulations: str | Iterable[str] | None = None,
        accidental: str | None = None,
        beams: Iterable[str] | None = None,
    ) -> VoiceCursor:
        parsed_pitches = tuple(_parse_pitch(pitch) for pitch in pitches)
        if not parsed_pitches:
            raise ValueError("Chord pitches cannot be empty")
        stream = self.part._stream(self.voice, self.staff)
        duration_name, total_dots = _parse_duration_spec(duration, dots=dots)
        tuplet_spec = _parse_tuplet(tuplet, duration_name)
        event = NoteEvent(
            sequence=self.part._next_sequence(),
            offset=stream.offset,
            duration=_duration_fraction(duration_name, dots=total_dots, tuplet=tuplet_spec),
            duration_name=duration_name,
            voice=self.voice,
            staff=self.staff,
            pitches=parsed_pitches,
            dots=total_dots,
            tuplet=tuplet_spec,
            ties=_normalize_tie_or_slur(tie, "tie"),
            slurs=_normalize_tie_or_slur(slur, "slur"),
            articulations=_normalize_articulations(articulations),
            accidental=accidental,
            beams=tuple(beams or ()),
        )
        stream.events.append(event)
        stream.offset += event.duration
        return self

    def tempo(
        self,
        bpm: int | float,
        *,
        beat_unit: str = "quarter",
        text: str | None = None,
        placement: str = "above",
    ) -> VoiceCursor:
        self._direction(
            kind="tempo",
            placement=placement,
            data={
                "bpm": bpm,
                "beat_unit": _normalize_duration_name(beat_unit),
                "text": text,
            },
        )
        return self

    def dynamic(self, mark: str, *, placement: str = "below") -> VoiceCursor:
        self._direction(
            kind="dynamic", placement=placement, data={"mark": mark.strip()}
        )
        return self

    def text(self, content: str, *, placement: str = "above") -> VoiceCursor:
        self._direction(kind="text", placement=placement, data={"content": content})
        return self

    def wedge(self, type: str, *, placement: str = "below") -> VoiceCursor:
        normalized = type.strip().lower()
        if normalized not in {"crescendo", "diminuendo", "stop"}:
            raise ValueError("Wedge type must be crescendo, diminuendo, or stop")
        self._direction(kind="wedge", placement=placement, data={"type": normalized})
        return self

    def _direction(
        self, *, kind: str, placement: str | None, data: dict[str, object]
    ) -> None:
        stream = self.part._stream(self.voice, self.staff)
        stream.events.append(
            DirectionEvent(
                sequence=self.part._next_sequence(),
                offset=stream.offset,
                voice=self.voice,
                staff=self.staff,
                kind=kind,
                placement=placement,
                data=data,
            )
        )
