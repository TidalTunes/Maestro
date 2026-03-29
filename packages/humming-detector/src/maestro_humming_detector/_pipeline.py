from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import librosa
import numpy as np


TARGET_SAMPLE_RATE = 16_000
FRAME_LENGTH = 1_024
HOP_LENGTH = 256
TRIM_TOP_DB = 30
PREEMPHASIS_COEFFICIENT = 0.30
STRICT_VOICED_PROBABILITY = 0.55
RELAXED_VOICED_PROBABILITY = 0.15
RMS_FLOOR = 0.03
RMS_NOISE_MULTIPLIER = 1.5
RMS_MAX_RATIO = 0.30
MEDIAN_FILTER_WINDOW = 5
MAX_GAP_FRAMES = 2
PITCH_JUMP_SEMITONES = 1.5
MIN_SEGMENT_SECONDS = 0.10
MERGE_GAP_SECONDS = 0.10
DEFAULT_QUARTER_SECONDS = 0.50

FLAT_NOTE_NAMES = (
    "C",
    "Db",
    "D",
    "Eb",
    "E",
    "F",
    "Gb",
    "G",
    "Ab",
    "A",
    "Bb",
    "B",
)

DURATION_VALUES = (
    ("16th", 0.25),
    ("eighth", 0.50),
    ("quarter", 1.00),
    ("half", 2.00),
    ("whole", 4.00),
)


@dataclass(frozen=True)
class RawSegment:
    start_time: float
    end_time: float
    midi_values: tuple[float, ...]

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def rounded_midi(self) -> int:
        return int(round(float(np.median(self.midi_values))))

    @property
    def median_midi(self) -> float:
        return float(np.median(self.midi_values))


@dataclass(frozen=True)
class NoteEvent:
    note_name: str
    start_time: float
    end_time: float
    duration_seconds: float
    duration_label: str


def transcribe_path(audio_path: Path) -> str:
    y, sr = _load_and_preprocess(audio_path)
    if y.size == 0:
        return ""

    midi_track, frame_times = _track_pitch(y, sr)
    raw_segments = _segment_pitch_track(midi_track, frame_times)
    if not raw_segments:
        return ""

    quarter_seconds = _estimate_quarter_duration_seconds(y, sr, raw_segments)
    events = _build_note_events(raw_segments, quarter_seconds)
    if not events:
        return ""

    return "\n".join(f"{event.note_name}, {event.duration_label}" for event in events)


def _load_and_preprocess(audio_path: Path) -> tuple[np.ndarray, int]:
    y, sr = librosa.load(str(audio_path), sr=TARGET_SAMPLE_RATE, mono=True)
    y = np.asarray(y, dtype=np.float32)
    if y.size == 0:
        return y, sr

    trimmed, _ = librosa.effects.trim(y, top_db=TRIM_TOP_DB)
    if trimmed.size:
        y = trimmed

    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 0:
        y = y / peak

    return y.astype(np.float32, copy=False), sr


def _track_pitch(y: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    candidates = (
        (librosa.effects.preemphasis(y, coef=PREEMPHASIS_COEFFICIENT), STRICT_VOICED_PROBABILITY),
        (y, RELAXED_VOICED_PROBABILITY),
    )

    best_track = np.array([], dtype=np.float32)
    best_times = np.array([], dtype=np.float32)
    best_score = (-1, -1)

    for candidate_y, min_voiced_probability in candidates:
        midi_track, frame_times = _track_pitch_candidate(candidate_y, sr, min_voiced_probability)
        score = _score_pitch_track(midi_track)
        if score > best_score:
            best_track = midi_track
            best_times = frame_times
            best_score = score

    return best_track, best_times


def _track_pitch_candidate(
    y: np.ndarray,
    sr: int,
    min_voiced_probability: float,
) -> tuple[np.ndarray, np.ndarray]:
    if y.size < FRAME_LENGTH:
        y = np.pad(y, (0, FRAME_LENGTH - y.size))

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C6"),
        sr=sr,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
        fill_na=np.nan,
    )
    rms = librosa.feature.rms(
        y=y,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
        center=True,
    )[0]
    frame_times = librosa.times_like(f0, sr=sr, hop_length=HOP_LENGTH)

    length = min(len(f0), len(voiced_flag), len(voiced_prob), len(rms), len(frame_times))
    if length == 0:
        return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

    f0 = f0[:length]
    voiced_flag = np.asarray(voiced_flag[:length], dtype=bool)
    voiced_prob = np.asarray(voiced_prob[:length], dtype=np.float32)
    rms = np.asarray(rms[:length], dtype=np.float32)
    frame_times = np.asarray(frame_times[:length], dtype=np.float32)

    noise_floor = _percentile_or_zero(rms[rms > 0], 20)
    rms_threshold = max(RMS_FLOOR, RMS_NOISE_MULTIPLIER * noise_floor)
    peak_rms = float(np.max(rms)) if rms.size else 0.0
    if peak_rms > 0:
        rms_threshold = min(rms_threshold, RMS_MAX_RATIO * peak_rms)

    voiced_mask = (
        voiced_flag
        & np.isfinite(f0)
        & np.isfinite(voiced_prob)
        & (voiced_prob >= min_voiced_probability)
        & (rms >= rms_threshold)
    )

    midi = np.full(length, np.nan, dtype=np.float32)
    if np.any(voiced_mask):
        midi[voiced_mask] = librosa.hz_to_midi(f0[voiced_mask]).astype(np.float32)

    smoothed = _nan_median_filter(midi, MEDIAN_FILTER_WINDOW)
    return smoothed, frame_times


def _score_pitch_track(midi_track: np.ndarray) -> tuple[int, int]:
    voiced_mask = np.isfinite(midi_track)
    voiced_frames = int(np.sum(voiced_mask))
    longest_run = 0
    current_run = 0
    for is_voiced in voiced_mask:
        if is_voiced:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 0
    return voiced_frames, longest_run


def _segment_pitch_track(midi_track: np.ndarray, frame_times: np.ndarray) -> list[RawSegment]:
    voiced_indices = np.flatnonzero(np.isfinite(midi_track))
    if voiced_indices.size == 0:
        return []

    raw_segments: list[RawSegment] = []
    segment_start = int(voiced_indices[0])
    previous_index = int(voiced_indices[0])

    for index in voiced_indices[1:]:
        index = int(index)
        gap_frames = index - previous_index - 1
        pitch_jump = abs(float(midi_track[index] - midi_track[previous_index])) >= PITCH_JUMP_SEMITONES
        if gap_frames > MAX_GAP_FRAMES or pitch_jump:
            raw_segments.append(_build_raw_segment(segment_start, previous_index, midi_track, frame_times))
            segment_start = index
        previous_index = index

    raw_segments.append(_build_raw_segment(segment_start, previous_index, midi_track, frame_times))
    raw_segments = [segment for segment in raw_segments if segment.duration >= MIN_SEGMENT_SECONDS]
    return _merge_adjacent_segments(raw_segments)


def _build_raw_segment(
    start_index: int,
    end_index: int,
    midi_track: np.ndarray,
    frame_times: np.ndarray,
) -> RawSegment:
    midi_values = midi_track[start_index : end_index + 1]
    midi_values = midi_values[np.isfinite(midi_values)]
    start_time = float(frame_times[start_index])
    end_time = float(frame_times[end_index] + (HOP_LENGTH / TARGET_SAMPLE_RATE))
    return RawSegment(
        start_time=start_time,
        end_time=end_time,
        midi_values=tuple(float(value) for value in midi_values),
    )


def _merge_adjacent_segments(segments: list[RawSegment]) -> list[RawSegment]:
    if not segments:
        return []

    merged: list[RawSegment] = [segments[0]]
    for segment in segments[1:]:
        previous = merged[-1]
        gap_seconds = segment.start_time - previous.end_time
        if gap_seconds < MERGE_GAP_SECONDS and segment.rounded_midi == previous.rounded_midi:
            merged[-1] = RawSegment(
                start_time=previous.start_time,
                end_time=segment.end_time,
                midi_values=previous.midi_values + segment.midi_values,
            )
            continue
        merged.append(segment)

    return merged


def _estimate_quarter_duration_seconds(
    y: np.ndarray,
    sr: int,
    segments: list[RawSegment],
) -> float:
    onset_envelope = librosa.onset.onset_strength(
        y=y,
        sr=sr,
        hop_length=HOP_LENGTH,
        aggregate=np.median,
    )
    tempo, beat_frames = librosa.beat.beat_track(
        onset_envelope=onset_envelope,
        sr=sr,
        hop_length=HOP_LENGTH,
        units="frames",
    )

    bpm = _coerce_scalar(tempo)
    beat_count = int(np.size(beat_frames))
    if bpm > 0 and beat_count >= 2:
        return 60.0 / bpm

    durations = np.asarray([segment.duration for segment in segments], dtype=np.float32)
    fallback = float(np.median(durations)) if durations.size else DEFAULT_QUARTER_SECONDS
    if durations.size >= 2 and fallback > 0 and float(np.max(durations)) >= (1.75 * fallback):
        fallback *= 2.0
    if not np.isfinite(fallback) or fallback <= 0:
        return DEFAULT_QUARTER_SECONDS
    return fallback


def _build_note_events(segments: list[RawSegment], quarter_seconds: float) -> list[NoteEvent]:
    if not segments:
        return []

    if quarter_seconds <= 0:
        quarter_seconds = DEFAULT_QUARTER_SECONDS

    pitch_offset = _relative_pitch_offset(segments[0])
    quarter_seconds = _anchor_quarter_seconds(segments[0].duration, quarter_seconds)

    events: list[NoteEvent] = []
    for segment in segments:
        midi_number = int(round(segment.median_midi - pitch_offset))
        note_name = _midi_to_note_name(midi_number)
        duration_label = _quantize_duration_label(segment.duration / quarter_seconds)
        events.append(
            NoteEvent(
                note_name=note_name,
                start_time=segment.start_time,
                end_time=segment.end_time,
                duration_seconds=segment.duration,
                duration_label=duration_label,
            )
        )
    return events


def _relative_pitch_offset(first_segment: RawSegment) -> float:
    first_midi = first_segment.median_midi
    return first_midi - round(first_midi)


def _anchor_quarter_seconds(first_duration: float, estimated_quarter_seconds: float) -> float:
    if not np.isfinite(estimated_quarter_seconds) or estimated_quarter_seconds <= 0:
        estimated_quarter_seconds = DEFAULT_QUARTER_SECONDS

    _, first_duration_units = _quantize_duration(first_duration / estimated_quarter_seconds)
    anchored_quarter_seconds = first_duration / first_duration_units
    if not np.isfinite(anchored_quarter_seconds) or anchored_quarter_seconds <= 0:
        return estimated_quarter_seconds
    return anchored_quarter_seconds


def _nan_median_filter(values: np.ndarray, window_size: int) -> np.ndarray:
    if values.size == 0 or window_size <= 1:
        return values.copy()

    radius = window_size // 2
    smoothed = values.copy()
    finite_indices = np.flatnonzero(np.isfinite(values))
    for index in finite_indices:
        start = max(0, int(index) - radius)
        end = min(len(values), int(index) + radius + 1)
        local_values = values[start:end]
        local_values = local_values[np.isfinite(local_values)]
        if local_values.size:
            smoothed[int(index)] = float(np.median(local_values))
    return smoothed


def _midi_to_note_name(midi_number: int) -> str:
    pitch_class = FLAT_NOTE_NAMES[midi_number % 12]
    octave = (midi_number // 12) - 1
    return f"{pitch_class}{octave}"


def _quantize_duration_label(duration_in_quarters: float) -> str:
    label, _ = _quantize_duration(duration_in_quarters)
    return label


def _quantize_duration(duration_in_quarters: float) -> tuple[str, float]:
    if not np.isfinite(duration_in_quarters) or duration_in_quarters <= 0:
        return "quarter", 1.0
    label, _ = min(
        DURATION_VALUES,
        key=lambda item: abs(math.log(duration_in_quarters / item[1])) if duration_in_quarters > 0 else float("inf"),
    )
    for duration_label, duration_units in DURATION_VALUES:
        if duration_label == label:
            return duration_label, duration_units
    return "quarter", 1.0


def _percentile_or_zero(values: np.ndarray, percentile: float) -> float:
    if values.size == 0:
        return 0.0
    return float(np.percentile(values, percentile))


def _coerce_scalar(value: object) -> float:
    array = np.asarray(value)
    if array.size == 0:
        return 0.0
    return float(array.reshape(-1)[0])
