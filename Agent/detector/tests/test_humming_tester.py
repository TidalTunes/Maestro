from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from detector.humming_tester import RecorderController, write_wav_file


class FakeRecorder:
    def __init__(self, audio: np.ndarray) -> None:
        self.audio = audio
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> np.ndarray:
        self.stopped = True
        return self.audio


class RecorderControllerTests(unittest.TestCase):
    def test_round_trip_records_then_transcribes(self) -> None:
        fake_audio = np.array([0.0, 0.25, -0.25], dtype=np.float32)
        recorder = FakeRecorder(fake_audio)
        seen_paths: list[Path] = []

        def detector(path: Path) -> str:
            seen_paths.append(path)
            self.assertTrue(path.exists())
            return "A4, quarter"

        controller = RecorderController(
            detector=detector,
            recorder_factory=lambda: recorder,
        )

        controller.start_recording()
        result = controller.stop_recording()

        self.assertTrue(recorder.started)
        self.assertTrue(recorder.stopped)
        self.assertEqual(result, "A4, quarter")
        self.assertEqual(len(seen_paths), 1)
        self.assertFalse(seen_paths[0].exists())

    def test_empty_audio_returns_empty_string_without_detector_call(self) -> None:
        recorder = FakeRecorder(np.zeros(0, dtype=np.float32))
        detector_calls = 0

        def detector(path: Path) -> str:
            del path
            nonlocal detector_calls
            detector_calls += 1
            return "unexpected"

        controller = RecorderController(
            detector=detector,
            recorder_factory=lambda: recorder,
        )

        controller.start_recording()
        result = controller.stop_recording()

        self.assertEqual(result, "")
        self.assertEqual(detector_calls, 0)

    def test_cannot_start_twice(self) -> None:
        recorder = FakeRecorder(np.zeros(4, dtype=np.float32))
        controller = RecorderController(recorder_factory=lambda: recorder)

        controller.start_recording()
        with self.assertRaises(RuntimeError):
            controller.start_recording()

    def test_cannot_stop_before_start(self) -> None:
        controller = RecorderController(recorder_factory=lambda: FakeRecorder(np.zeros(4, dtype=np.float32)))

        with self.assertRaises(RuntimeError):
            controller.stop_recording()


class WaveWriterTests(unittest.TestCase):
    def test_write_wav_file_creates_pcm_wave(self) -> None:
        audio = np.array([0.0, 0.5, -0.5], dtype=np.float32)

        path = write_wav_file(audio)
        try:
            self.assertEqual(path.suffix, ".wav")
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 44)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
