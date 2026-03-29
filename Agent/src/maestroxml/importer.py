from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Iterable
import re
import xml.etree.ElementTree as ET

from .core import (
    CANONICAL_DURATION_NAMES,
    CLEF_PRESETS,
    DURATION_VALUES,
    INSTRUMENT_PRESETS,
    Clef,
    MeasureBarline,
    Pitch,
    SUPPORTED_ARTICULATIONS,
)

ALTER_TO_ACCIDENTAL = {
    None: "",
    -2: "bb",
    -1: "b",
    0: "n",
    1: "#",
    2: "##",
}

DURATION_BY_VALUE = {value: name for name, value in DURATION_VALUES.items()}


@dataclass
class ImportedNoteItem:
    pitch: Pitch | None
    ties: tuple[str, ...]
    slurs: tuple[str, ...]
    articulations: tuple[str, ...]
    accidental: str | None
    beams: tuple[str, ...]


@dataclass
class ImportedNoteGroup:
    sequence: int
    offset: Fraction
    duration_name: str
    duration_value: Fraction
    dots: int
    tuplet: tuple[int, int] | tuple[int, int, str] | None
    voice: int
    staff: int
    is_rest: bool
    items: list[ImportedNoteItem] = field(default_factory=list)


@dataclass
class ImportedDirection:
    sequence: int
    offset: Fraction
    voice: int
    staff: int
    kind: str
    placement: str | None
    data: dict[str, object]


ImportedEvent = ImportedNoteGroup | ImportedDirection


@dataclass
class ImportedMeasure:
    source_number: str
    time_signature: tuple[int, int] | None = None
    key_signature: tuple[int, str] | None = None
    clefs: dict[int, Clef] = field(default_factory=dict)
    streams: dict[tuple[int, int], list[ImportedEvent]] = field(default_factory=dict)
    left_barline: MeasureBarline = field(default_factory=MeasureBarline)
    right_barline: MeasureBarline = field(default_factory=MeasureBarline)


@dataclass
class ImportedPart:
    part_id: str
    name: str
    abbreviation: str | None
    instrument_name: str | None
    staves: int
    initial_clefs: dict[int, Clef]
    measures: list[ImportedMeasure]


@dataclass
class ImportedScore:
    title: str | None
    composer: str | None
    lyricist: str | None
    rights: str | None
    output_measure_numbers: list[int]
    time_changes: dict[int, tuple[int, int]]
    key_changes: dict[int, tuple[int, str]]
    parts: list[ImportedPart]


def musicxml_to_python(
    path: str | Path, *, output_path: str | Path | None = None
) -> str:
    """Read a MusicXML file and return editable Python using maestroxml."""

    return musicxml_string_to_python(
        Path(path).read_text(encoding="utf-8"), output_path=output_path
    )


def musicxml_string_to_python(
    xml_text: str, *, output_path: str | Path | None = None
) -> str:
    """Translate MusicXML text into editable Python using maestroxml."""

    root = ET.fromstring(xml_text)
    imported = _parse_score(root)
    return _render_python(imported, output_path=output_path)


def _parse_score(root: ET.Element) -> ImportedScore:
    root_name = _local_name(root)
    if root_name not in {"score-partwise", "score-timewise"}:
        raise ValueError(
            "maestroxml only imports MusicXML score-partwise or score-timewise documents."
        )

    title = (
        _child_text(_first_child(root, "work"), "work-title")
        or _child_text(root, "movement-title")
        or None
    )
    composer = None
    lyricist = None
    rights = None

    identification = _first_child(root, "identification")
    if identification is not None:
        rights = _child_text(identification, "rights") or None
        for creator in _children_named(identification, "creator"):
            creator_type = (creator.attrib.get("type") or "").strip().lower()
            text = _text(creator)
            if not text:
                continue
            if creator_type == "composer" and composer is None:
                composer = text
            elif creator_type in {"lyricist", "poet"} and lyricist is None:
                lyricist = text

    part_headers = _parse_part_headers(root)
    part_sequences = _extract_measure_sequences(root, root_name)
    parts: list[ImportedPart] = []

    ordered_part_ids = list(part_headers)
    for part_id in part_sequences:
        if part_id not in ordered_part_ids:
            ordered_part_ids.append(part_id)

    for part_id in ordered_part_ids:
        header = part_headers.get(part_id, {})
        measures = part_sequences.get(part_id, [])
        parts.append(
            _parse_part(
                part_id=part_id,
                name=header.get("name") or part_id,
                abbreviation=header.get("abbreviation"),
                instrument_name=header.get("instrument_name"),
                measures=measures,
            )
        )

    measure_labels = parts[0].measures if parts else []
    output_measure_numbers = _choose_measure_numbers(
        [measure.source_number for measure in measure_labels]
    )
    time_changes = _collect_score_level_changes(parts, output_measure_numbers, "time")
    key_changes = _collect_score_level_changes(parts, output_measure_numbers, "key")

    return ImportedScore(
        title=title,
        composer=composer,
        lyricist=lyricist,
        rights=rights,
        output_measure_numbers=output_measure_numbers,
        time_changes=time_changes,
        key_changes=key_changes,
        parts=parts,
    )


def _parse_part_headers(root: ET.Element) -> dict[str, dict[str, str | None]]:
    part_list = _first_child(root, "part-list")
    if part_list is None:
        return {}

    headers: dict[str, dict[str, str | None]] = {}
    for score_part in _children_named(part_list, "score-part"):
        part_id = score_part.attrib.get("id")
        if not part_id:
            continue
        instrument_name = None
        score_instrument = _first_child(score_part, "score-instrument")
        if score_instrument is not None:
            instrument_name = _child_text(score_instrument, "instrument-name")
        headers[part_id] = {
            "name": _child_text(score_part, "part-name"),
            "abbreviation": _child_text(score_part, "part-abbreviation"),
            "instrument_name": instrument_name,
        }
    return headers


def _extract_measure_sequences(
    root: ET.Element, root_name: str
) -> dict[str, list[tuple[str, ET.Element]]]:
    sequences: dict[str, list[tuple[str, ET.Element]]] = {}

    if root_name == "score-partwise":
        for part in _children_named(root, "part"):
            part_id = part.attrib.get("id")
            if not part_id:
                continue
            part_measures: list[tuple[str, ET.Element]] = []
            for index, measure in enumerate(_children_named(part, "measure"), start=1):
                part_measures.append((measure.attrib.get("number", str(index)), measure))
            sequences[part_id] = part_measures
        return sequences

    for outer_index, measure in enumerate(_children_named(root, "measure"), start=1):
        measure_number = measure.attrib.get("number", str(outer_index))
        for part in _children_named(measure, "part"):
            part_id = part.attrib.get("id")
            if not part_id:
                continue
            sequences.setdefault(part_id, []).append((measure_number, part))
    return sequences


def _parse_part(
    *,
    part_id: str,
    name: str,
    abbreviation: str | None,
    instrument_name: str | None,
    measures: list[tuple[str, ET.Element]],
) -> ImportedPart:
    current_divisions = 1
    current_clefs: dict[int, Clef] = {}
    initial_clefs: dict[int, Clef] = {}
    staves = 1
    parsed_measures: list[ImportedMeasure] = []

    for measure_index, (measure_number, measure_element) in enumerate(measures, start=1):
        parsed = ImportedMeasure(source_number=measure_number)
        sequence = 0
        current_position = Fraction(0)
        last_note_group_by_stream: dict[tuple[int, int], ImportedNoteGroup] = {}

        for child in measure_element:
            child_name = _local_name(child)
            if child_name == "attributes":
                current_divisions = _parse_attributes(
                    child,
                    parsed,
                    current_divisions=current_divisions,
                    current_clefs=current_clefs,
                    initial_clefs=initial_clefs,
                    measure_index=measure_index,
                )
                staves = max(staves, _parse_staves(child) or staves)
                continue

            if child_name == "note":
                result = _parse_note_group(
                    child,
                    sequence=sequence,
                    current_position=current_position,
                    current_divisions=current_divisions,
                    last_note_group_by_stream=last_note_group_by_stream,
                    parsed=parsed,
                )
                sequence = result["sequence"]
                current_position = result["position"]
                continue

            if child_name == "backup":
                backup_duration = _read_duration_fraction(child, current_divisions)
                if backup_duration is not None:
                    current_position -= backup_duration
                continue

            if child_name == "forward":
                forward_duration = _read_duration_fraction(child, current_divisions)
                if forward_duration is not None:
                    current_position += forward_duration
                continue

            if child_name == "direction":
                directions = _parse_directions(
                    child,
                    sequence_start=sequence,
                    current_position=current_position,
                    current_divisions=current_divisions,
                )
                for direction in directions:
                    parsed.streams.setdefault((direction.staff, direction.voice), []).append(
                        direction
                    )
                sequence += len(directions)
                continue

            if child_name == "barline":
                _parse_barline(child, parsed)

        if not initial_clefs:
            initial_clefs[1] = _preset_clef("treble")

        if len(initial_clefs) < staves:
            for staff_number in range(1, staves + 1):
                initial_clefs.setdefault(staff_number, _preset_clef("treble"))

        for key in parsed.streams:
            parsed.streams[key].sort(key=lambda event: (event.offset, event.sequence))
        parsed_measures.append(parsed)

    if not parsed_measures:
        initial_clefs = {1: _preset_clef("treble")}

    return ImportedPart(
        part_id=part_id,
        name=name,
        abbreviation=abbreviation,
        instrument_name=instrument_name,
        staves=staves,
        initial_clefs=initial_clefs,
        measures=parsed_measures,
    )


def _parse_attributes(
    element: ET.Element,
    parsed: ImportedMeasure,
    *,
    current_divisions: int,
    current_clefs: dict[int, Clef],
    initial_clefs: dict[int, Clef],
    measure_index: int,
) -> int:
    divisions_text = _child_text(element, "divisions")
    if divisions_text and divisions_text.isdigit():
        current_divisions = int(divisions_text)

    key = _first_child(element, "key")
    if key is not None:
        fifths_text = _child_text(key, "fifths")
        mode_text = (_child_text(key, "mode") or "major").lower()
        if fifths_text is not None:
            try:
                parsed.key_signature = (int(fifths_text), mode_text)
            except ValueError:
                pass

    time = _first_child(element, "time")
    if time is not None:
        beats_text = _child_text(time, "beats")
        beat_type_text = _child_text(time, "beat-type")
        if beats_text and beat_type_text:
            try:
                parsed.time_signature = (int(beats_text), int(beat_type_text))
            except ValueError:
                pass

    for clef in _children_named(element, "clef"):
        sign = _child_text(clef, "sign")
        line_text = _child_text(clef, "line")
        if not sign or not line_text:
            continue
        try:
            clef_value = Clef(sign=sign, line=int(line_text))
        except ValueError:
            continue
        staff_number = int(clef.attrib.get("number", "1"))
        if measure_index == 1:
            initial_clefs[staff_number] = clef_value
        elif current_clefs.get(staff_number) != clef_value:
            parsed.clefs[staff_number] = clef_value
        current_clefs[staff_number] = clef_value

    return current_divisions


def _parse_staves(element: ET.Element) -> int | None:
    staves_text = _child_text(element, "staves")
    if staves_text is None:
        return None
    try:
        return int(staves_text)
    except ValueError:
        return None


def _parse_note_group(
    element: ET.Element,
    *,
    sequence: int,
    current_position: Fraction,
    current_divisions: int,
    last_note_group_by_stream: dict[tuple[int, int], ImportedNoteGroup],
    parsed: ImportedMeasure,
) -> dict[str, object]:
    duration_value = _read_duration_fraction(element, current_divisions)
    voice = _parse_int(_child_text(element, "voice"), default=1)
    staff = _parse_int(_child_text(element, "staff"), default=1)
    stream_key = (staff, voice)
    is_chord = _first_child(element, "chord") is not None
    is_rest = _first_child(element, "rest") is not None

    if _first_child(element, "grace") is not None:
        return {"sequence": sequence, "position": current_position}

    duration_name = _parse_duration_name(element, duration_value)
    if duration_value is None:
        return {"sequence": sequence, "position": current_position}

    if duration_name is None:
        if not is_chord:
            current_position += duration_value
        return {"sequence": sequence, "position": current_position}

    dots = len(_children_named(element, "dot"))
    tuplet = _parse_tuplet(element, duration_name)
    note_item = _parse_note_item(element, is_rest=is_rest)
    if note_item is None and not is_rest:
        if not is_chord:
            current_position += duration_value
        return {"sequence": sequence, "position": current_position}

    if is_chord:
        group = last_note_group_by_stream.get(stream_key)
        if group is not None and not group.is_rest:
            if note_item is not None:
                group.items.append(note_item)
            return {"sequence": sequence, "position": current_position}
        if note_item is None:
            return {"sequence": sequence, "position": current_position}

    group = ImportedNoteGroup(
        sequence=sequence,
        offset=current_position,
        duration_name=duration_name,
        duration_value=duration_value,
        dots=dots,
        tuplet=tuplet,
        voice=voice,
        staff=staff,
        is_rest=is_rest,
        items=[] if note_item is None else [note_item],
    )
    parsed.streams.setdefault(stream_key, []).append(group)
    last_note_group_by_stream[stream_key] = group
    sequence += 1

    if not is_chord:
        current_position += duration_value

    return {"sequence": sequence, "position": current_position}


def _parse_note_item(element: ET.Element, *, is_rest: bool) -> ImportedNoteItem | None:
    pitch = None
    if not is_rest:
        pitch_element = _first_child(element, "pitch")
        if pitch_element is None:
            return None
        step = _child_text(pitch_element, "step")
        octave_text = _child_text(pitch_element, "octave")
        if not step or octave_text is None:
            return None
        try:
            alter_text = _child_text(pitch_element, "alter")
            pitch = Pitch(
                step=step,
                alter=int(alter_text) if alter_text is not None else None,
                octave=int(octave_text),
            )
        except ValueError:
            return None

    ties = tuple(
        tie.attrib.get("type", "").strip().lower()
        for tie in _children_named(element, "tie")
        if tie.attrib.get("type")
    )
    slurs: list[str] = []
    articulations: list[str] = []
    notations = _first_child(element, "notations")
    if notations is not None:
        for slur in _children_named(notations, "slur"):
            slur_type = slur.attrib.get("type", "").strip().lower()
            if slur_type in {"start", "stop"}:
                slurs.append(slur_type)
        articulations_parent = _first_child(notations, "articulations")
        if articulations_parent is not None:
            for articulation in articulations_parent:
                articulation_name = _local_name(articulation)
                if articulation_name in SUPPORTED_ARTICULATIONS:
                    articulations.append(articulation_name)

    accidental = _text(_first_child(element, "accidental")) or None
    beams = tuple(_text(beam) or "" for beam in _children_named(element, "beam"))

    return ImportedNoteItem(
        pitch=pitch,
        ties=tuple(item for item in ties if item in {"start", "stop"}),
        slurs=tuple(slurs),
        articulations=tuple(articulations),
        accidental=accidental,
        beams=tuple(beam for beam in beams if beam),
    )


def _parse_tuplet(
    element: ET.Element, duration_name: str
) -> tuple[int, int] | tuple[int, int, str] | None:
    time_modification = _first_child(element, "time-modification")
    if time_modification is None:
        return None

    actual_text = _child_text(time_modification, "actual-notes")
    normal_text = _child_text(time_modification, "normal-notes")
    if not actual_text or not normal_text:
        return None
    try:
        actual = int(actual_text)
        normal = int(normal_text)
    except ValueError:
        return None

    normal_type = _child_text(time_modification, "normal-type")
    if normal_type:
        normalized = CANONICAL_DURATION_NAMES.get(normal_type.strip().lower())
        if normalized and normalized != duration_name:
            return (actual, normal, normalized)
    return (actual, normal)


def _parse_duration_name(
    element: ET.Element, duration_value: Fraction | None
) -> str | None:
    type_text = _child_text(element, "type")
    if type_text:
        return CANONICAL_DURATION_NAMES.get(type_text.strip().lower())
    if duration_value is None:
        return None
    return DURATION_BY_VALUE.get(duration_value)


def _parse_directions(
    element: ET.Element,
    *,
    sequence_start: int,
    current_position: Fraction,
    current_divisions: int,
) -> list[ImportedDirection]:
    placement = element.attrib.get("placement")
    voice = _parse_int(_child_text(element, "voice"), default=1)
    staff = _parse_int(_child_text(element, "staff"), default=1)
    offset_text = _child_text(element, "offset")
    offset_value = Fraction(0)
    if offset_text is not None:
        try:
            offset_value = Fraction(int(offset_text), current_divisions)
        except ValueError:
            offset_value = Fraction(0)
    position = current_position + offset_value

    events: list[ImportedDirection] = []
    sequence = sequence_start
    for direction_type in _children_named(element, "direction-type"):
        metronome = _first_child(direction_type, "metronome")
        words = _child_text(direction_type, "words")
        if metronome is not None:
            beat_unit = _child_text(metronome, "beat-unit")
            per_minute = _child_text(metronome, "per-minute")
            normalized = (
                CANONICAL_DURATION_NAMES.get(beat_unit.strip().lower())
                if beat_unit
                else None
            )
            bpm = _parse_number(per_minute)
            if normalized is not None and bpm is not None:
                events.append(
                    ImportedDirection(
                        sequence=sequence,
                        offset=position,
                        voice=voice,
                        staff=staff,
                        kind="tempo",
                        placement=placement,
                        data={
                            "bpm": bpm,
                            "beat_unit": normalized,
                            "text": words,
                        },
                    )
                )
                sequence += 1
                continue

        dynamics = _first_child(direction_type, "dynamics")
        if dynamics is not None:
            mark = None
            for child in dynamics:
                child_name = _local_name(child)
                if child_name == "other-dynamics":
                    mark = _text(child)
                    break
                mark = child_name
                break
            if mark:
                events.append(
                    ImportedDirection(
                        sequence=sequence,
                        offset=position,
                        voice=voice,
                        staff=staff,
                        kind="dynamic",
                        placement=placement,
                        data={"mark": mark},
                    )
                )
                sequence += 1
                continue

        wedge = _first_child(direction_type, "wedge")
        if wedge is not None:
            wedge_type = (wedge.attrib.get("type") or "").strip().lower()
            if wedge_type in {"crescendo", "diminuendo", "stop"}:
                events.append(
                    ImportedDirection(
                        sequence=sequence,
                        offset=position,
                        voice=voice,
                        staff=staff,
                        kind="wedge",
                        placement=placement,
                        data={"type": wedge_type},
                    )
                )
                sequence += 1
                continue

        if words:
            events.append(
                ImportedDirection(
                    sequence=sequence,
                    offset=position,
                    voice=voice,
                    staff=staff,
                    kind="text",
                    placement=placement,
                    data={"content": words},
                )
            )
            sequence += 1

    return events


def _parse_barline(element: ET.Element, parsed: ImportedMeasure) -> None:
    location = element.attrib.get("location", "right")
    target = parsed.left_barline if location == "left" else parsed.right_barline

    repeat = _first_child(element, "repeat")
    if repeat is not None:
        direction = (repeat.attrib.get("direction") or "").strip().lower()
        if direction in {"forward", "backward"}:
            target.repeat = direction
            if repeat.attrib.get("times"):
                try:
                    target.times = int(repeat.attrib["times"])
                except ValueError:
                    target.times = None

    ending = _first_child(element, "ending")
    if ending is not None:
        number = ending.attrib.get("number")
        ending_type = (ending.attrib.get("type") or "").strip().lower()
        if number and ending_type in {"start", "stop", "discontinue"}:
            target.ending_number = number
            target.ending_type = ending_type


def _collect_score_level_changes(
    parts: list[ImportedPart], output_measure_numbers: list[int], kind: str
) -> dict[int, tuple[int, int] | tuple[int, str]]:
    changes: dict[int, tuple[int, int] | tuple[int, str]] = {}
    previous = None
    for index, measure_number in enumerate(output_measure_numbers):
        value = None
        for part in parts:
            if index >= len(part.measures):
                continue
            candidate = (
                part.measures[index].time_signature
                if kind == "time"
                else part.measures[index].key_signature
            )
            if candidate is not None:
                value = candidate
                break
        if value is not None and value != previous:
            changes[measure_number] = value
            previous = value
    return changes


def _choose_measure_numbers(source_numbers: Iterable[str]) -> list[int]:
    labels = list(source_numbers)
    parsed_numbers: list[int] = []
    previous = -1
    for source_number in labels:
        try:
            value = int(str(source_number).strip())
        except ValueError:
            return list(range(1, len(labels) + 1))
        if value <= 0 or value <= previous:
            return list(range(1, len(labels) + 1))
        parsed_numbers.append(value)
        previous = value
    return parsed_numbers


def _render_python(
    score: ImportedScore, *, output_path: str | Path | None = None
) -> str:
    lines = ["from maestroxml import Score", "", _render_score_ctor(score), ""]

    part_variables = _build_part_variable_names(score.parts)
    cursor_variables = _build_cursor_variable_names(score.parts, part_variables)

    for part in score.parts:
        lines.append(_render_add_part(part, part_variables[part.part_id]))
    if score.parts:
        lines.append("")

    for cursor_key, variable in cursor_variables.items():
        part_id, staff, voice = cursor_key
        part_variable = part_variables[part_id]
        lines.append(f"{variable} = {part_variable}.voice({voice}, staff={staff})")
    if cursor_variables:
        lines.append("")

    for index, measure_number in enumerate(score.output_measure_numbers):
        lines.append(f"score.measure({measure_number})")

        if measure_number in score.time_changes:
            beats, beat_type = score.time_changes[measure_number]
            lines.append(f'score.time_signature("{beats}/{beat_type}")')
        if measure_number in score.key_changes:
            fifths, mode = score.key_changes[measure_number]
            key_repr = _key_signature_repr(fifths, mode)
            lines.append(f"score.key_signature({key_repr})")

        for part in score.parts:
            if index >= len(part.measures):
                continue
            part_variable = part_variables[part.part_id]
            measure = part.measures[index]
            if measure.left_barline.repeat == "forward":
                lines.append(f"{part_variable}.repeat_start()")
            if measure.left_barline.ending_number and measure.left_barline.ending_type:
                lines.append(
                    f'{part_variable}.ending("{measure.left_barline.ending_number}", '
                    f'"{measure.left_barline.ending_type}")'
                )

            for staff_number in sorted(measure.clefs):
                clef_value = _clef_repr(measure.clefs[staff_number])
                lines.append(
                    f"{part_variable}.clef({clef_value}, staff={staff_number})"
                )

            for (staff, voice), events in sorted(
                measure.streams.items(), key=lambda item: (item[0][0], item[0][1])
            ):
                target = (
                    part_variable
                    if (staff, voice) == (1, 1)
                    else cursor_variables[(part.part_id, staff, voice)]
                )
                lines.extend(_render_stream_events(target, events))

            if measure.right_barline.ending_number and measure.right_barline.ending_type:
                lines.append(
                    f'{part_variable}.ending("{measure.right_barline.ending_number}", '
                    f'"{measure.right_barline.ending_type}")'
                )
            if measure.right_barline.repeat == "backward":
                if measure.right_barline.times is None:
                    lines.append(f"{part_variable}.repeat_end()")
                else:
                    lines.append(
                        f"{part_variable}.repeat_end(times={measure.right_barline.times})"
                    )

        lines.append("")

    if output_path is not None:
        lines.append(f"score.write({output_path!r})")
    else:
        lines.pop()

    return "\n".join(lines) + "\n"


def _render_score_ctor(score: ImportedScore) -> str:
    kwargs = []
    for key in ("title", "composer", "lyricist", "rights"):
        value = getattr(score, key)
        if value is not None:
            kwargs.append(f"{key}={value!r}")
    return f"score = Score({', '.join(kwargs)})" if kwargs else "score = Score()"


def _build_part_variable_names(parts: list[ImportedPart]) -> dict[str, str]:
    used: set[str] = set()
    result: dict[str, str] = {}
    for index, part in enumerate(parts, start=1):
        base = _slugify(part.name) or f"part_{index}"
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        result[part.part_id] = candidate
    return result


def _build_cursor_variable_names(
    parts: list[ImportedPart], part_variables: dict[str, str]
) -> dict[tuple[str, int, int], str]:
    result: dict[tuple[str, int, int], str] = {}
    for part in parts:
        streams = {
            key
            for measure in part.measures
            for key in measure.streams
            if key != (1, 1)
        }
        for staff, voice in sorted(streams):
            result[(part.part_id, staff, voice)] = (
                f"{part_variables[part.part_id]}_voice_{voice}_staff_{staff}"
            )
    return result


def _render_add_part(part: ImportedPart, variable_name: str) -> str:
    kwargs: list[str] = []
    inferred_preset = _infer_instrument_preset(part)
    if inferred_preset is not None:
        kwargs.append(f'instrument="{inferred_preset}"')
    if part.abbreviation and (
        inferred_preset is None
        or part.abbreviation != INSTRUMENT_PRESETS[inferred_preset]["abbreviation"]
    ):
        kwargs.append(f"abbreviation={part.abbreviation!r}")
    if inferred_preset is None:
        if part.staves != 1:
            kwargs.append(f"staves={part.staves}")
        clefs = _render_initial_clefs(part)
        if clefs is not None:
            kwargs.append(f"clefs={clefs}")
    else:
        preset = INSTRUMENT_PRESETS[inferred_preset]
        if part.staves != preset["staves"]:
            kwargs.append(f"staves={part.staves}")
        current_clefs = tuple(
            _clef_to_named_or_tuple(part.initial_clefs[index])
            for index in sorted(part.initial_clefs)
        )
        preset_clefs = tuple(preset["clefs"])
        if current_clefs != preset_clefs:
            kwargs.append(f"clefs={_render_initial_clefs(part)}")

    args = [repr(part.name), *kwargs]
    return f"{variable_name} = score.add_part({', '.join(args)})"


def _render_initial_clefs(part: ImportedPart) -> str | None:
    values = [
        _clef_to_named_or_tuple(part.initial_clefs[index])
        for index in sorted(part.initial_clefs)
    ]
    if values == ["treble"]:
        return None
    return "[" + ", ".join(_python_repr(value) for value in values) + "]"


def _infer_instrument_preset(part: ImportedPart) -> str | None:
    clef_values = tuple(
        _clef_to_named_or_tuple(part.initial_clefs[index])
        for index in sorted(part.initial_clefs)
    )
    lowered_names = [
        part.name.lower(),
        (part.instrument_name or "").lower(),
    ]

    for preset_name, preset in INSTRUMENT_PRESETS.items():
        if part.staves != preset["staves"]:
            continue
        if clef_values != tuple(preset["clefs"]):
            continue
        preset_label = preset["instrument_name"].lower()
        if any(
            value == preset_name
            or value == preset_label
            or value.startswith(f"{preset_label} ")
            or value.startswith(f"{preset_name} ")
            for value in lowered_names
            if value
        ):
            return preset_name
    return None


def _render_stream_events(target: str, events: list[ImportedEvent]) -> list[str]:
    lines: list[str] = []
    index = 0
    while index < len(events):
        event = events[index]
        if _is_compressible_single_note(event):
            run = [event]
            look_ahead = index + 1
            while look_ahead < len(events) and _same_simple_note_signature(
                run[-1], events[look_ahead]
            ):
                run.append(events[look_ahead])
                look_ahead += 1
            if len(run) > 1:
                pitches = [_pitch_to_string(run_event.items[0].pitch) for run_event in run]
                kwargs = _render_note_kwargs(run[0], run[0].items[0])
                lines.append(
                    f'{target}.notes("{run[0].duration_name}", {pitches!r}{kwargs})'
                )
                index = look_ahead
                continue

        if isinstance(event, ImportedDirection):
            lines.append(_render_direction_call(target, event))
        else:
            lines.append(_render_note_call(target, event))
        index += 1
    return lines


def _render_direction_call(target: str, event: ImportedDirection) -> str:
    if event.kind == "tempo":
        args = [repr(event.data["bpm"])]
        if event.data.get("beat_unit") != "quarter":
            args.append(f'beat_unit="{event.data["beat_unit"]}"')
        if event.data.get("text"):
            args.append(f'text={event.data["text"]!r}')
        if event.placement and event.placement != "above":
            args.append(f'placement="{event.placement}"')
        return f"{target}.tempo({', '.join(args)})"
    if event.kind == "dynamic":
        args = [repr(event.data["mark"])]
        if event.placement and event.placement != "below":
            args.append(f'placement="{event.placement}"')
        return f"{target}.dynamic({', '.join(args)})"
    if event.kind == "text":
        args = [repr(event.data["content"])]
        if event.placement and event.placement != "above":
            args.append(f'placement="{event.placement}"')
        return f"{target}.text({', '.join(args)})"
    if event.kind == "wedge":
        args = [repr(event.data["type"])]
        if event.placement and event.placement != "below":
            args.append(f'placement="{event.placement}"')
        return f"{target}.wedge({', '.join(args)})"
    raise ValueError(f"Unsupported imported direction: {event.kind}")


def _render_note_call(target: str, event: ImportedNoteGroup) -> str:
    if event.is_rest:
        kwargs = _render_rest_kwargs(event)
        return f'{target}.rest("{event.duration_name}"{kwargs})'

    if len(event.items) > 1:
        shared_item = _shared_note_item(event.items)
        kwargs = _render_note_kwargs(event, shared_item)
        pitches = [_pitch_to_string(item.pitch) for item in event.items]
        return f'{target}.chord("{event.duration_name}", {pitches!r}{kwargs})'

    kwargs = _render_note_kwargs(event, event.items[0])
    pitch = _pitch_to_string(event.items[0].pitch)
    return f'{target}.note("{event.duration_name}", {pitch!r}{kwargs})'


def _render_note_kwargs(event: ImportedNoteGroup, item: ImportedNoteItem | None) -> str:
    kwargs: list[str] = []
    if event.dots:
        kwargs.append(f"dots={event.dots}")
    if event.tuplet is not None:
        kwargs.append(f"tuplet={_python_repr(event.tuplet)}")
    if item is not None:
        if item.ties:
            kwargs.append(f"tie={_python_repr(_sequence_or_scalar(item.ties))}")
        if item.slurs:
            kwargs.append(f"slur={_python_repr(_sequence_or_scalar(item.slurs))}")
        if item.articulations:
            kwargs.append(f"articulations={_python_repr(list(item.articulations))}")
        if item.accidental:
            kwargs.append(f"accidental={item.accidental!r}")
        if item.beams:
            kwargs.append(f"beams={_python_repr(list(item.beams))}")
    return "" if not kwargs else ", " + ", ".join(kwargs)


def _render_rest_kwargs(event: ImportedNoteGroup) -> str:
    kwargs: list[str] = []
    if event.dots:
        kwargs.append(f"dots={event.dots}")
    if event.tuplet is not None:
        kwargs.append(f"tuplet={_python_repr(event.tuplet)}")
    if event.items and event.items[0].beams:
        kwargs.append(f"beams={_python_repr(list(event.items[0].beams))}")
    return "" if not kwargs else ", " + ", ".join(kwargs)


def _shared_note_item(items: list[ImportedNoteItem]) -> ImportedNoteItem | None:
    if not items:
        return None
    shared_ties = _shared_value(items, lambda item: item.ties)
    shared_slurs = _shared_value(items, lambda item: item.slurs)
    shared_articulations = _shared_value(items, lambda item: item.articulations)
    shared_accidental = _shared_value(items, lambda item: item.accidental)
    shared_beams = _shared_value(items, lambda item: item.beams)
    return ImportedNoteItem(
        pitch=None,
        ties=shared_ties or (),
        slurs=shared_slurs or (),
        articulations=shared_articulations or (),
        accidental=shared_accidental,
        beams=shared_beams or (),
    )


def _is_compressible_single_note(event: ImportedEvent) -> bool:
    return (
        isinstance(event, ImportedNoteGroup)
        and not event.is_rest
        and len(event.items) == 1
    )


def _same_simple_note_signature(
    left: ImportedEvent, right: ImportedEvent
) -> bool:
    if not (_is_compressible_single_note(left) and _is_compressible_single_note(right)):
        return False
    left_note = left.items[0]
    right_note = right.items[0]
    return (
        left.duration_name == right.duration_name
        and left.dots == right.dots
        and left.tuplet == right.tuplet
        and left_note.ties == right_note.ties
        and left_note.slurs == right_note.slurs
        and left_note.articulations == right_note.articulations
        and left_note.accidental == right_note.accidental
        and left_note.beams == right_note.beams
    )


def _pitch_to_string(pitch: Pitch | None) -> str:
    if pitch is None:
        raise ValueError("Pitch is required for note output.")
    return f"{pitch.step}{ALTER_TO_ACCIDENTAL[pitch.alter]}{pitch.octave}"


def _key_signature_repr(fifths: int, mode: str) -> str:
    lookup = {
        (0, "major"): '"C major"',
        (1, "major"): '"G major"',
        (2, "major"): '"D major"',
        (3, "major"): '"A major"',
        (4, "major"): '"E major"',
        (5, "major"): '"B major"',
        (6, "major"): '"F# major"',
        (7, "major"): '"C# major"',
        (-1, "major"): '"F major"',
        (-2, "major"): '"Bb major"',
        (-3, "major"): '"Eb major"',
        (-4, "major"): '"Ab major"',
        (-5, "major"): '"Db major"',
        (-6, "major"): '"Gb major"',
        (-7, "major"): '"Cb major"',
        (0, "minor"): '"A minor"',
        (1, "minor"): '"E minor"',
        (2, "minor"): '"B minor"',
        (3, "minor"): '"F# minor"',
        (4, "minor"): '"C# minor"',
        (5, "minor"): '"G# minor"',
        (6, "minor"): '"D# minor"',
        (7, "minor"): '"A# minor"',
        (-1, "minor"): '"D minor"',
        (-2, "minor"): '"G minor"',
        (-3, "minor"): '"C minor"',
        (-4, "minor"): '"F minor"',
        (-5, "minor"): '"Bb minor"',
        (-6, "minor"): '"Eb minor"',
        (-7, "minor"): '"Ab minor"',
    }
    return lookup.get((fifths, mode), f"{fifths}, mode={mode!r}")


def _clef_repr(clef: Clef) -> str:
    return _python_repr(_clef_to_named_or_tuple(clef))


def _clef_to_named_or_tuple(clef: Clef) -> str | tuple[str, int]:
    for name, value in CLEF_PRESETS.items():
        if value == (clef.sign, clef.line):
            return name
    return (clef.sign, clef.line)


def _preset_clef(name: str) -> Clef:
    sign, line = CLEF_PRESETS[name]
    return Clef(sign=sign, line=line)


def _read_duration_fraction(
    element: ET.Element, current_divisions: int
) -> Fraction | None:
    duration_text = _child_text(element, "duration")
    if duration_text is None:
        return None
    try:
        return Fraction(int(duration_text), current_divisions)
    except ValueError:
        return None


def _parse_number(text: str | None) -> int | float | None:
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return int(value) if value.is_integer() else value


def _parse_int(text: str | None, *, default: int) -> int:
    if text is None:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _shared_value(items: list[ImportedNoteItem], getter) -> object | None:
    first = getter(items[0])
    if all(getter(item) == first for item in items[1:]):
        return first
    return None


def _sequence_or_scalar(values: tuple[str, ...]) -> str | tuple[str, ...]:
    return values[0] if len(values) == 1 else values


def _python_repr(value: object) -> str:
    return repr(value)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    if not slug:
        return ""
    if slug[0].isdigit():
        slug = f"part_{slug}"
    return slug


def _local_name(element: ET.Element | str) -> str:
    tag = element if isinstance(element, str) else element.tag
    return tag.split("}", 1)[-1]


def _children_named(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local_name(child) == name]


def _first_child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in element:
        if _local_name(child) == name:
            return child
    return None


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    return text or None


def _child_text(element: ET.Element | None, name: str) -> str | None:
    return _text(_first_child(element, name))
