from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import math
import struct
import sys
import unittest
import warnings
import wave

import numpy as np

warnings.filterwarnings(
    "ignore",
    message="aifc was removed in Python 3.13.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message="sunau was removed in Python 3.13.*",
    category=DeprecationWarning,
)


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "packages" / "humming-detector" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maestro_humming_detector import transcribe_humming
from maestro_humming_detector import _pipeline


class NoteFormattingTests(unittest.TestCase):
    def test_midi_to_note_name_uses_flats_and_octaves(self) -> None:
        self.assertEqual(_pipeline._midi_to_note_name(58), "Bb3")
        self.assertEqual(_pipeline._midi_to_note_name(61), "Db4")
        self.assertEqual(_pipeline._midi_to_note_name(72), "C5")

    def test_relative_pitch_anchor_uses_first_note_offset(self) -> None:
        segments = [
            _pipeline.RawSegment(0.00, 0.24, (69.49, 69.50)),
            _pipeline.RawSegment(0.30, 0.54, (71.49, 71.50)),
            _pipeline.RawSegment(0.60, 0.84, (72.49, 72.50)),
        ]

        events = _pipeline._build_note_events(segments, quarter_seconds=0.24)

        self.assertEqual([event.note_name for event in events], ["A4", "B4", "C5"])

    def test_relative_duration_anchor_uses_first_note_duration(self) -> None:
        segments = [
            _pipeline.RawSegment(0.00, 0.24, (69.0,)),
            _pipeline.RawSegment(0.30, 0.78, (71.0,)),
            _pipeline.RawSegment(0.84, 1.08, (72.0,)),
        ]

        events = _pipeline._build_note_events(segments, quarter_seconds=0.40)

        self.assertEqual(
            [event.duration_label for event in events],
            ["eighth", "quarter", "eighth"],
        )


class SegmentationTests(unittest.TestCase):
    def test_vibrato_stays_single_segment(self) -> None:
        frame_times = np.arange(40, dtype=np.float32) * (_pipeline.HOP_LENGTH / _pipeline.TARGET_SAMPLE_RATE)
        vibrato = 69.0 + 0.35 * np.sin(np.linspace(0.0, 6.0 * math.pi, 40))
        segments = _pipeline._segment_pitch_track(vibrato.astype(np.float32), frame_times)

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].rounded_midi, 69)


class EndToEndTests(unittest.TestCase):
    def test_transcribe_humming_detects_notes_and_lengths(self) -> None:
        signal = np.concatenate(
            [
                synth_note(440.0, 0.50),
                np.zeros(int(0.08 * _pipeline.TARGET_SAMPLE_RATE), dtype=np.float32),
                synth_note(466.1637615, 0.25),
                np.zeros(int(0.08 * _pipeline.TARGET_SAMPLE_RATE), dtype=np.float32),
                synth_note(523.2511306, 0.25),
            ]
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "hum.wav"
            write_wav(path, signal, _pipeline.TARGET_SAMPLE_RATE)

            result = transcribe_humming(path)

        self.assertEqual(result, "A4, quarter\nBb4, eighth\nC5, eighth")

    def test_silence_only_returns_empty_string(self) -> None:
        signal = np.zeros(_pipeline.TARGET_SAMPLE_RATE, dtype=np.float32)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "silence.wav"
            write_wav(path, signal, _pipeline.TARGET_SAMPLE_RATE)

            result = transcribe_humming(path)

        self.assertEqual(result, "")

    def test_short_breath_noise_does_not_create_fake_note(self) -> None:
        hum = synth_note(440.0, 0.50)
        breath = 0.015 * np.random.default_rng(7).normal(size=int(0.03 * _pipeline.TARGET_SAMPLE_RATE)).astype(np.float32)
        signal = np.concatenate([hum, np.zeros(int(0.05 * _pipeline.TARGET_SAMPLE_RATE), dtype=np.float32), breath])

        with TemporaryDirectory() as directory:
            path = Path(directory) / "breath.wav"
            write_wav(path, signal, _pipeline.TARGET_SAMPLE_RATE)

            result = transcribe_humming(path)

        self.assertEqual(result, "A4, quarter")

    def test_quieter_noisy_hum_still_detects_note(self) -> None:
        rng = np.random.default_rng(11)
        hum = 0.10 * synth_note(196.0, 0.80, vibrato_depth=0.008)
        noise = 0.010 * rng.normal(size=hum.shape[0]).astype(np.float32)
        signal = hum + noise

        with TemporaryDirectory() as directory:
            path = Path(directory) / "quiet_noisy.wav"
            write_wav(path, signal, _pipeline.TARGET_SAMPLE_RATE)

            result = transcribe_humming(path)

        self.assertEqual(result, "G3, quarter")

    def test_beat_tracking_fallback_uses_segment_median_duration(self) -> None:
        signal = np.concatenate(
            [
                synth_note(440.0, 0.20, attack_seconds=0.05),
                np.zeros(int(0.04 * _pipeline.TARGET_SAMPLE_RATE), dtype=np.float32),
                synth_note(493.8833013, 0.20, attack_seconds=0.05),
                np.zeros(int(0.04 * _pipeline.TARGET_SAMPLE_RATE), dtype=np.float32),
                synth_note(523.2511306, 0.20, attack_seconds=0.05),
            ]
        )

        with TemporaryDirectory() as directory:
            path = Path(directory) / "fallback.wav"
            write_wav(path, signal, _pipeline.TARGET_SAMPLE_RATE)

            with patch.object(_pipeline.librosa.beat, "beat_track", return_value=(0.0, np.array([], dtype=int))):
                result = transcribe_humming(path)

        self.assertEqual(result, "A4, quarter\nB4, quarter\nC5, quarter")


def synth_note(
    frequency_hz: float,
    duration_seconds: float,
    attack_seconds: float = 0.02,
    vibrato_hz: float = 5.5,
    vibrato_depth: float = 0.015,
) -> np.ndarray:
    sample_count = max(1, int(round(duration_seconds * _pipeline.TARGET_SAMPLE_RATE)))
    times = np.arange(sample_count, dtype=np.float32) / _pipeline.TARGET_SAMPLE_RATE
    vibrato = np.sin(2.0 * np.pi * vibrato_hz * times)
    instantaneous_frequency = frequency_hz * (1.0 + vibrato_depth * vibrato)
    phase = 2.0 * np.pi * np.cumsum(instantaneous_frequency) / _pipeline.TARGET_SAMPLE_RATE

    signal = (
        0.70 * np.sin(phase)
        + 0.20 * np.sin(2.0 * phase)
        + 0.10 * np.sin(3.0 * phase)
    ).astype(np.float32)

    attack_samples = min(sample_count, max(1, int(round(attack_seconds * _pipeline.TARGET_SAMPLE_RATE))))
    release_samples = min(sample_count, max(1, int(round(0.04 * _pipeline.TARGET_SAMPLE_RATE))))

    envelope = np.ones(sample_count, dtype=np.float32)
    envelope[:attack_samples] = np.linspace(0.0, 1.0, attack_samples, endpoint=True, dtype=np.float32)
    envelope[-release_samples:] *= np.linspace(1.0, 0.0, release_samples, endpoint=True, dtype=np.float32)

    return 0.60 * signal * envelope


def write_wav(path: Path, signal: np.ndarray, sample_rate: int) -> None:
    clipped = np.clip(signal, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack("<" + "h" * len(pcm), *pcm))


if __name__ == "__main__":
    unittest.main()
