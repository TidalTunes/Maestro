from __future__ import annotations

from pathlib import Path
import queue
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import scrolledtext
from typing import Callable
import wave

import numpy as np


TARGET_SAMPLE_RATE = 16_000


if __package__ in {None, ""}:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from maestro_humming_detector import transcribe_humming
else:
    from .api import transcribe_humming


class MicrophoneRecorder:
    """Capture mono float32 audio from the default microphone."""

    def __init__(self, sample_rate: int = TARGET_SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._sounddevice = None

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Recording is already in progress.")

        try:
            import sounddevice as sounddevice
        except ImportError as exc:
            raise RuntimeError(
                "Microphone recording requires the optional 'sounddevice' package. "
                "Install packages/humming-detector first."
            ) from exc

        self._sounddevice = sounddevice
        self._frames = []

        def callback(indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
            del frames, time_info, status
            self._frames.append(indata.copy())

        self._stream = sounddevice.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        if self._stream is None:
            raise RuntimeError("Recording is not in progress.")

        stream = self._stream
        self._stream = None

        try:
            stream.stop()
        finally:
            stream.close()

        if not self._frames:
            return np.zeros(0, dtype=np.float32)

        audio = np.concatenate(self._frames, axis=0).reshape(-1)
        return audio.astype(np.float32, copy=False)


def write_wav_file(audio: np.ndarray, sample_rate: int = TARGET_SAMPLE_RATE) -> Path:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        path = Path(handle.name)

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())

    return path


class RecorderController:
    def __init__(
        self,
        detector: Callable[[str | Path], str] = transcribe_humming,
        recorder_factory: Callable[[], object] | None = None,
        sample_rate: int = TARGET_SAMPLE_RATE,
    ) -> None:
        self._detector = detector
        self._recorder_factory = recorder_factory or (lambda: MicrophoneRecorder(sample_rate=sample_rate))
        self._sample_rate = sample_rate
        self._recorder: MicrophoneRecorder | None = None

    @property
    def is_recording(self) -> bool:
        return self._recorder is not None

    def start_recording(self) -> None:
        if self._recorder is not None:
            raise RuntimeError("Recording is already in progress.")

        recorder = self._recorder_factory()
        recorder.start()
        self._recorder = recorder

    def stop_recording(self) -> str:
        if self._recorder is None:
            raise RuntimeError("Recording has not started.")

        recorder = self._recorder
        self._recorder = None
        audio = recorder.stop()
        if audio.size == 0:
            return ""

        wav_path = write_wav_file(audio, sample_rate=self._sample_rate)
        try:
            return self._detector(wav_path)
        finally:
            wav_path.unlink(missing_ok=True)


class HummingTesterApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Humming Detector")
        self.root.resizable(False, False)

        self.controller = RecorderController()
        self._events: queue.Queue[tuple[str, str]] = queue.Queue()
        self._worker: threading.Thread | None = None

        self.status_var = tk.StringVar(value="Ready to record.")

        container = tk.Frame(self.root, padx=14, pady=14)
        container.pack(fill="both", expand=True)

        button_row = tk.Frame(container)
        button_row.pack(fill="x")

        self.record_button = tk.Button(
            button_row,
            text="Record",
            width=12,
            command=self.on_record,
        )
        self.record_button.pack(side="left")

        self.stop_button = tk.Button(
            button_row,
            text="Stop",
            width=12,
            command=self.on_stop,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=(8, 0))

        self.status_label = tk.Label(container, textvariable=self.status_var, anchor="w")
        self.status_label.pack(fill="x", pady=(10, 8))

        self.output = scrolledtext.ScrolledText(container, width=32, height=10, wrap="word")
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")

        self.root.after(100, self._poll_events)

    def run(self) -> None:
        self.root.mainloop()

    def on_record(self) -> None:
        try:
            self.controller.start_recording()
        except Exception as exc:
            self._show_result("")
            self.status_var.set(str(exc))
            return

        self.record_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.status_var.set("Recording... hum, then press Stop.")

    def on_stop(self) -> None:
        self.stop_button.configure(state="disabled")
        self.status_var.set("Transcribing...")

        self._worker = threading.Thread(target=self._transcribe_worker, daemon=True)
        self._worker.start()

    def _transcribe_worker(self) -> None:
        try:
            result = self.controller.stop_recording()
        except Exception as exc:
            self._events.put(("error", str(exc)))
            return

        self._events.put(("result", result))

    def _poll_events(self) -> None:
        try:
            while True:
                event_type, payload = self._events.get_nowait()
                if event_type == "error":
                    self._show_result("")
                    self.status_var.set(payload)
                else:
                    self._show_result(payload)
                    if payload:
                        self.status_var.set("Done. Record again whenever you want.")
                    else:
                        self.status_var.set("No stable notes detected. Try again.")
                self.record_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
        except queue.Empty:
            pass

        self.root.after(100, self._poll_events)

    def _show_result(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")


def main() -> None:
    app = HummingTesterApp()
    app.run()


if __name__ == "__main__":
    main()
