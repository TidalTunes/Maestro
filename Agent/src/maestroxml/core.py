from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from fractions import Fraction
from math import lcm
from pathlib import Path
from typing import Iterable

DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)

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
    "64th": "64th",
    "sixty-fourth": "64th",
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
    },
    "viola": {
        "abbreviation": "Vla.",
        "staves": 1,
        "clefs": ["alto"],
        "instrument_name": "Viola",
    },
    "cello": {
        "abbreviation": "Vc.",
        "staves": 1,
        "clefs": ["bass"],
        "instrument_name": "Cello",
    },
    "piano": {
        "abbreviation": "Pno.",
        "staves": 2,
        "clefs": ["treble", "bass"],
        "instrument_name": "Piano",
    },
    "flute": {
        "abbreviation": "Fl.",
        "staves": 1,
        "clefs": ["treble"],
        "instrument_name": "Flute",
    },
    "clarinet": {
        "abbreviation": "Cl.",
        "staves": 1,
        "clefs": ["treble"],
        "instrument_name": "Clarinet",
    },
    "voice": {
        "abbreviation": "V.",
        "staves": 1,
        "clefs": ["treble"],
        "instrument_name": "Voice",
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
    canonical = CANONICAL_DURATION_NAMES.get(duration.strip().lower())
    if canonical is None:
        raise ValueError(f"Unsupported duration name: {duration!r}")
    return canonical


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


def _lcm_denominators(values: Iterable[Fraction]) -> int:
    result = 1
    for value in values:
        result = lcm(result, value.denominator)
    return result


def _set_text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = str(value)
    return element


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

        part = Part(
            score=self,
            part_id=f"P{len(self.parts) + 1}",
            name=name,
            abbreviation=resolved_abbreviation,
            instrument_name=str(preset.get("instrument_name", instrument or name)),
            staves=resolved_staves,
            initial_clefs={index + 1: clef for index, clef in enumerate(clef_specs)},
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

    def to_string(self) -> str:
        if not self.parts:
            raise ValueError(
                "Score has no parts. Add at least one part before serializing."
            )
        if self.current_measure is None:
            raise ValueError(
                "Score has no measures. Call measure() before serializing."
            )

        root = ET.Element("score-partwise", version="4.0")
        self._build_header(root)
        self._build_part_list(root)

        divisions = self._compute_divisions()
        max_measure = self._max_measure
        for part in self.parts:
            part_element = ET.SubElement(root, "part", id=part.part_id)
            for measure_number in range(1, max_measure + 1):
                measure = part._ensure_measure(measure_number)
                self._build_measure(part, measure, part_element, divisions)

        ET.indent(root, space="  ")
        body = ET.tostring(root, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n{DOCTYPE}\n{body}\n'

    def write(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.write_text(self.to_string(), encoding="utf-8")
        return destination

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
            if (
                candidate_measure < measure_number
                and candidate_measure > latest_measure
            ):
                latest_measure = candidate_measure
                latest_value = value
        return latest_value

    def _build_header(self, root: ET.Element) -> None:
        if self.title:
            work = ET.SubElement(root, "work")
            _set_text(work, "work-title", self.title)
            _set_text(root, "movement-title", self.title)

        if self.composer or self.lyricist or self.rights:
            identification = ET.SubElement(root, "identification")
            if self.composer:
                creator = _set_text(identification, "creator", self.composer)
                creator.set("type", "composer")
            if self.lyricist:
                creator = _set_text(identification, "creator", self.lyricist)
                creator.set("type", "lyricist")
            if self.rights:
                _set_text(identification, "rights", self.rights)

    def _build_part_list(self, root: ET.Element) -> None:
        part_list = ET.SubElement(root, "part-list")
        for part in self.parts:
            score_part = ET.SubElement(part_list, "score-part", id=part.part_id)
            _set_text(score_part, "part-name", part.name)
            if part.abbreviation:
                _set_text(score_part, "part-abbreviation", part.abbreviation)
            score_instrument = ET.SubElement(
                score_part, "score-instrument", id=f"{part.part_id}-I1"
            )
            _set_text(score_instrument, "instrument-name", part.instrument_name)

    def _compute_divisions(self) -> int:
        durations: list[Fraction] = []
        for part in self.parts:
            for measure in part.measures.values():
                for stream in measure.streams.values():
                    if stream.offset:
                        durations.append(stream.offset)
                    for event in stream.events:
                        if isinstance(event, NoteEvent):
                            durations.append(event.duration)
                            durations.append(event.offset)
                        else:
                            durations.append(event.offset)
        if not durations:
            return 1
        return _lcm_denominators(durations)

    def _build_measure(
        self, part: Part, measure: MeasureState, parent: ET.Element, divisions: int
    ) -> None:
        measure_element = ET.SubElement(parent, "measure", number=str(measure.number))

        attributes = self._build_attributes_if_needed(
            part, measure, measure_element, divisions
        )
        if attributes is not None and len(attributes) == 0:
            measure_element.remove(attributes)

        self._append_barline(measure_element, measure.left_barline, location="left")
        self._append_streams(measure_element, measure, divisions)
        self._append_barline(measure_element, measure.right_barline, location="right")

    def _build_attributes_if_needed(
        self,
        part: Part,
        measure: MeasureState,
        measure_element: ET.Element,
        divisions: int,
    ) -> ET.Element | None:
        should_emit = (
            measure.number == 1
            or measure.number in self._time_changes
            or measure.number in self._key_changes
            or bool(measure.clefs)
        )
        if not should_emit:
            return None

        attributes = ET.SubElement(measure_element, "attributes")
        if measure.number == 1:
            _set_text(attributes, "divisions", divisions)
            if part.staves > 1:
                _set_text(attributes, "staves", part.staves)

        if measure.number in self._key_changes:
            fifths, mode = self._key_changes[measure.number]
            key = ET.SubElement(attributes, "key")
            _set_text(key, "fifths", fifths)
            _set_text(key, "mode", mode)

        if measure.number in self._time_changes:
            beats, beat_type = self._time_changes[measure.number]
            time = ET.SubElement(attributes, "time")
            _set_text(time, "beats", beats)
            _set_text(time, "beat-type", beat_type)

        if measure.number == 1:
            for staff_number in sorted(part.initial_clefs):
                self._append_clef(
                    attributes,
                    part.initial_clefs[staff_number],
                    staff_number,
                    part.staves,
                )

        if measure.clefs and measure.number != 1:
            for staff_number in sorted(measure.clefs):
                self._append_clef(
                    attributes, measure.clefs[staff_number], staff_number, part.staves
                )

        return attributes

    @staticmethod
    def _append_clef(
        attributes: ET.Element, clef: Clef, staff_number: int, staff_count: int
    ) -> None:
        clef_element = ET.SubElement(attributes, "clef")
        if staff_count > 1:
            clef_element.set("number", str(staff_number))
        _set_text(clef_element, "sign", clef.sign)
        _set_text(clef_element, "line", clef.line)

    def _append_streams(
        self, measure_element: ET.Element, measure: MeasureState, divisions: int
    ) -> None:
        sorted_streams = sorted(
            measure.streams.items(), key=lambda item: (item[0][0], item[0][1])
        )
        previous_stream_duration = Fraction(0)
        first_stream = True
        for _, stream in sorted_streams:
            if not first_stream and previous_stream_duration > 0:
                backup = ET.SubElement(measure_element, "backup")
                _set_text(backup, "duration", int(previous_stream_duration * divisions))
            first_stream = False

            for event in sorted(
                stream.events, key=lambda current: (current.offset, current.sequence)
            ):
                if isinstance(event, DirectionEvent):
                    self._append_direction(measure_element, event)
                else:
                    self._append_note_event(measure_element, event, divisions)

            previous_stream_duration = stream.offset

    @staticmethod
    def _append_direction(measure_element: ET.Element, event: DirectionEvent) -> None:
        direction = ET.SubElement(measure_element, "direction")
        if event.placement:
            direction.set("placement", event.placement)

        direction_type = ET.SubElement(direction, "direction-type")
        if event.kind == "tempo":
            metronome = ET.SubElement(direction_type, "metronome")
            _set_text(metronome, "beat-unit", event.data["beat_unit"])
            _set_text(metronome, "per-minute", event.data["bpm"])
            if event.data.get("text"):
                _set_text(direction_type, "words", event.data["text"])
        elif event.kind == "dynamic":
            dynamics = ET.SubElement(direction_type, "dynamics")
            mark = str(event.data["mark"])
            if mark in SUPPORTED_DYNAMIC_TAGS:
                ET.SubElement(dynamics, mark)
            else:
                _set_text(dynamics, "other-dynamics", mark)
        elif event.kind == "text":
            _set_text(direction_type, "words", event.data["content"])
        elif event.kind == "wedge":
            wedge = ET.SubElement(direction_type, "wedge")
            wedge.set("type", str(event.data["type"]))
        else:
            raise ValueError(f"Unsupported direction type: {event.kind}")

        _set_text(direction, "voice", event.voice)
        if event.staff > 1:
            _set_text(direction, "staff", event.staff)

    @staticmethod
    def _append_note_event(
        measure_element: ET.Element, event: NoteEvent, divisions: int
    ) -> None:
        chord_pitches = (None,) if event.is_rest else event.pitches
        for index, pitch in enumerate(chord_pitches):
            note = ET.SubElement(measure_element, "note")
            if index > 0:
                ET.SubElement(note, "chord")

            if event.is_rest:
                ET.SubElement(note, "rest")
            else:
                pitch_element = ET.SubElement(note, "pitch")
                _set_text(pitch_element, "step", pitch.step)
                if pitch.alter is not None:
                    _set_text(pitch_element, "alter", pitch.alter)
                _set_text(pitch_element, "octave", pitch.octave)

            _set_text(note, "duration", int(event.duration * divisions))

            for tie_type in event.ties:
                tie = ET.SubElement(note, "tie")
                tie.set("type", tie_type)

            _set_text(note, "voice", event.voice)
            _set_text(note, "type", event.duration_name)

            for _ in range(event.dots):
                ET.SubElement(note, "dot")

            if event.accidental:
                _set_text(note, "accidental", event.accidental)

            if event.tuplet is not None:
                time_modification = ET.SubElement(note, "time-modification")
                _set_text(time_modification, "actual-notes", event.tuplet.actual_notes)
                _set_text(time_modification, "normal-notes", event.tuplet.normal_notes)
                if event.tuplet.normal_type:
                    _set_text(
                        time_modification, "normal-type", event.tuplet.normal_type
                    )

            if event.staff > 1:
                _set_text(note, "staff", event.staff)

            for beam_number, beam_value in enumerate(event.beams, start=1):
                beam = _set_text(note, "beam", beam_value)
                beam.set("number", str(beam_number))

            if event.ties or event.slurs or event.articulations:
                notations = ET.SubElement(note, "notations")
                for tie_type in event.ties:
                    tied = ET.SubElement(notations, "tied")
                    tied.set("type", tie_type)
                for slur_type in event.slurs:
                    slur = ET.SubElement(notations, "slur")
                    slur.set("number", "1")
                    slur.set("type", slur_type)
                if event.articulations:
                    articulations = ET.SubElement(notations, "articulations")
                    for articulation_name in event.articulations:
                        ET.SubElement(articulations, articulation_name)

    @staticmethod
    def _append_barline(
        measure_element: ET.Element, barline: MeasureBarline, *, location: str
    ) -> None:
        if not any((barline.repeat, barline.ending_number, barline.ending_type)):
            return

        barline_element = ET.SubElement(measure_element, "barline", location=location)
        if barline.repeat == "forward":
            _set_text(barline_element, "bar-style", "heavy-light")
        elif barline.repeat == "backward":
            _set_text(barline_element, "bar-style", "light-heavy")

        if barline.ending_number and barline.ending_type:
            ending = ET.SubElement(barline_element, "ending")
            ending.set("number", barline.ending_number)
            ending.set("type", barline.ending_type)

        if barline.repeat:
            repeat = ET.SubElement(barline_element, "repeat")
            repeat.set("direction", barline.repeat)
            if barline.times is not None:
                repeat.set("times", str(barline.times))


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
    ) -> None:
        self.score = score
        self.part_id = part_id
        self.name = name
        self.abbreviation = abbreviation
        self.instrument_name = instrument_name
        self.staves = staves
        self.initial_clefs = dict(initial_clefs)
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
        duration_name = _normalize_duration_name(duration)
        tuplet_spec = _parse_tuplet(tuplet, duration_name)
        event = NoteEvent(
            sequence=self.part._next_sequence(),
            offset=stream.offset,
            duration=_duration_fraction(duration_name, dots=dots, tuplet=tuplet_spec),
            duration_name=duration_name,
            voice=self.voice,
            staff=self.staff,
            pitches=(_parse_pitch(pitch),),
            dots=dots,
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
        duration_name = _normalize_duration_name(duration)
        tuplet_spec = _parse_tuplet(tuplet, duration_name)
        event = NoteEvent(
            sequence=self.part._next_sequence(),
            offset=stream.offset,
            duration=_duration_fraction(duration_name, dots=dots, tuplet=tuplet_spec),
            duration_name=duration_name,
            voice=self.voice,
            staff=self.staff,
            is_rest=True,
            dots=dots,
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
        duration_name = _normalize_duration_name(duration)
        tuplet_spec = _parse_tuplet(tuplet, duration_name)
        event = NoteEvent(
            sequence=self.part._next_sequence(),
            offset=stream.offset,
            duration=_duration_fraction(duration_name, dots=dots, tuplet=tuplet_spec),
            duration_name=duration_name,
            voice=self.voice,
            staff=self.staff,
            pitches=parsed_pitches,
            dots=dots,
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
