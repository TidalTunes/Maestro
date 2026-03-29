from __future__ import annotations

from threading import Lock
from typing import Callable, Protocol


class HummingError(RuntimeError):
    """Raised when microphone recording or humming transcription fails."""


class RecorderControllerProtocol(Protocol):
    @property
    def is_recording(self) -> bool: ...

    def start_recording(self) -> None: ...

    def stop_recording(self) -> str: ...


def _build_default_controller() -> RecorderControllerProtocol:
    try:
        from detector.humming_tester import RecorderController
    except ImportError as exc:
        raise HummingError(
            "Humming support is unavailable. Install the detector dependencies from "
            "Agent/detector/requirements.txt first."
        ) from exc

    return RecorderController()


class HummingService:
    """Small adapter around the detector recorder for the local test app."""

    def __init__(
        self,
        controller_factory: Callable[[], RecorderControllerProtocol] | None = None,
    ) -> None:
        self._controller_factory = controller_factory or _build_default_controller
        self._controller: RecorderControllerProtocol | None = None
        self._last_notes = ""
        self._lock = Lock()

    @property
    def is_recording(self) -> bool:
        controller = self._controller
        return controller is not None and controller.is_recording

    @property
    def last_notes(self) -> str:
        return self._last_notes

    def start_recording(self) -> None:
        with self._lock:
            if self.is_recording:
                raise HummingError("Recording is already in progress.")

            controller = self._controller_factory()
            try:
                controller.start_recording()
            except Exception as exc:
                raise HummingError(str(exc)) from exc

            self._controller = controller
            self._last_notes = ""

    def stop_recording(self) -> str:
        with self._lock:
            controller = self._controller
            if controller is None or not controller.is_recording:
                raise HummingError("Recording has not started.")

            try:
                notes = controller.stop_recording().strip()
            except Exception as exc:
                self._controller = None
                raise HummingError(str(exc)) from exc

            self._controller = None
            self._last_notes = notes
            return notes
