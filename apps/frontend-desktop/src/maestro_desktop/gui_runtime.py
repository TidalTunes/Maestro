#!/usr/bin/env python3
"""
Maestro - AI Compose Assistant for MuseScore
Zed-style flat editorial layout. No bubbles, no rounded corners.
"""

import sys
import tempfile
import wave
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import List, Optional

from .backend import (
    DEFAULT_OLLAMA_MODEL,
    DesktopAgentBackend,
    ModelProviderConfig,
    OllamaProviderConfig,
    OpenAIProviderConfig,
    get_default_provider_config,
)
from .plugin_setup import (
    PLUGIN_DISPLAY_NAME,
    PluginInstallState,
    inspect_plugin_install,
    install_plugin,
    launch_musescore,
    verify_bridge_connection,
)
from .runtime_support import app_icon_path, frame_paths, images_dir
from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QMovie,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QScroller,
    QScrollerProperties,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

# ============== CONFIGURATION ==============
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 600

# Colors
BG_COLOR = "#1a1a1a"
SURFACE_COLOR = "#252525"
INPUT_BG = "#2d2d2d"
BORDER_COLOR = "#3a3a3a"
ACCENT_COLOR = "#3daee9"
USER_LABEL_COLOR = "#5dd9a0"  # Green for "you"
AI_LABEL_COLOR = "#869bed"  # Light purple for "maestro"
TEXT_PRIMARY = "#e0e0e0"
TEXT_SECONDARY = "#707070"
RECORDING_COLOR = "#c04040"
DIVIDER_COLOR = "#333333"

# Font - Clean sans-serif (Claude-style)
UI_FONT = "Helvetica Neue"
UI_FONT_SIZE = 13
LABEL_FONT_SIZE = 11

# Animation durations (ms)
FADE_DURATION = 300
SLIDE_DURATION = 250

# ===========================================


class MessageType(Enum):
    USER_TEXT = "user_text"
    USER_AUDIO = "user_audio"
    AI_TEXT = "ai_text"
    LOADING = "loading"


@dataclass
class Message:
    type: MessageType
    content: str = ""
    audio_path: Optional[str] = None
    duration: float = 0.0


RECORD_SAMPLE_RATE = 16_000


class MicrophoneRecorder:
    """Capture mono float32 audio from the default microphone."""

    def __init__(self, sample_rate: int = RECORD_SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._frames = []
        self._numpy = None
        self._stream = None

    def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Recording is already in progress.")

        try:
            import numpy as np
            import sounddevice as sounddevice
        except ImportError as exc:
            raise RuntimeError(
                "Microphone recording requires the optional 'sounddevice' package. "
                "Install the humming-detector dependencies first."
            ) from exc

        self._numpy = np
        self._frames = []

        def callback(indata, frames: int, time_info: object, status: object) -> None:
            del frames, time_info
            if status:
                print(f"sounddevice status: {status}", file=sys.stderr)
            self._frames.append(indata.copy())

        self._stream = sounddevice.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is None:
            raise RuntimeError("Recording is not in progress.")

        stream = self._stream
        self._stream = None

        try:
            stream.stop()
        finally:
            stream.close()

        np = self._numpy
        if np is None:
            raise RuntimeError("Recording backend was not initialized correctly.")

        if not self._frames:
            return np.zeros(0, dtype=np.float32)

        audio = np.concatenate(self._frames, axis=0).reshape(-1)
        return audio.astype(np.float32, copy=False)


def write_wav_file(audio, sample_rate: int = RECORD_SAMPLE_RATE) -> Path:
    import numpy as np

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


class LoadingAnimation(QWidget):
    """Animated loading using a 6x6 sprite sheet with rotating status text."""

    SPRITE_PATH = images_dir() / "animation-sequence.png"
    GRID_SIZE = 6  # 6x6 grid = 36 frames
    DISPLAY_SIZE = 80

    THINKING_PHRASES = [
        "Thinking",
        "Composing",
        "Writing Scales",
        "Finding Harmony",
        "Crafting Melody",
        "Arranging Notes",
        "Conducting",
        "Orchestrating",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame_index = 0
        self._direction = 1  # 1 = forward, -1 = reverse
        self._dot_count = 0
        self._phrase_index = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._next_frame)
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._update_dots)
        self._phrase_timer = QTimer(self)
        self._phrase_timer.timeout.connect(self._rotate_phrase)

        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sprite animation
        self._sprite = QLabel()
        self._sprite.setStyleSheet("background: transparent;")
        self._sprite.setFixedSize(self.DISPLAY_SIZE, self.DISPLAY_SIZE)
        layout.addWidget(self._sprite)

        layout.addSpacing(12)

        # Status text
        self._phrase = self.THINKING_PHRASES[self._phrase_index]
        self._status = QLabel(f"{self._phrase}...")
        self._status.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: {UI_FONT_SIZE}px;
            font-style: italic;
            background: transparent;
        """)
        layout.addWidget(self._status)

        # Load sprite sheet and slice into frames
        self._frames = []
        sprite_sheet = QPixmap(str(self.SPRITE_PATH))

        if not sprite_sheet.isNull():
            frame_w = sprite_sheet.width() // self.GRID_SIZE
            frame_h = sprite_sheet.height() // self.GRID_SIZE

            # Extract each frame from the 6x6 grid
            for row in range(self.GRID_SIZE):
                for col in range(self.GRID_SIZE):
                    frame = sprite_sheet.copy(
                        col * frame_w, row * frame_h, frame_w, frame_h
                    )
                    # Scale to display size
                    frame = frame.scaled(
                        self.DISPLAY_SIZE,
                        self.DISPLAY_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self._frames.append(frame)

        self._update_frame()

    def _update_frame(self):
        if self._frames:
            self._sprite.setPixmap(self._frames[self._frame_index])

    def _refresh_status(self):
        dots = "." * self._dot_count
        spaces = " " * (3 - self._dot_count)
        self._status.setText(f"{self._phrase}{dots}{spaces}")

    def _update_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        self._refresh_status()

    def _rotate_phrase(self):
        self._phrase_index = (self._phrase_index + 1) % len(self.THINKING_PHRASES)
        self._phrase = self.THINKING_PHRASES[self._phrase_index]
        self._refresh_status()

    def start(self):
        self._frame_index = 0
        self._direction = 1
        self._phrase_index = 0
        self._phrase = self.THINKING_PHRASES[self._phrase_index]
        self._dot_count = 0
        self._update_frame()
        self._update_dots()
        self._timer.start(50)  # ~20 FPS for smooth animation
        self._dot_timer.start(400)  # Dot animation
        self._phrase_timer.start(3000)  # Rotate status text every 3 seconds

    def stop(self):
        self._timer.stop()
        self._dot_timer.stop()
        self._phrase_timer.stop()

    def _next_frame(self):
        if self._frames:
            self._frame_index += self._direction

            # Ping-pong: reverse direction at ends
            if self._frame_index >= len(self._frames) - 1:
                self._direction = -1
            elif self._frame_index <= 0:
                self._direction = 1

            self._update_frame()


class AudioPlayer(QFrame):
    """Flat audio player matching the preview bar style."""

    def __init__(self, audio_path: str, duration: float, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.duration = duration
        self._is_playing = False

        self.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border: 2px solid {BORDER_COLOR};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Play/Pause button - rounded
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: #ffffff;
                border: none;
                border-radius: 16px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #5abeef;
            }}
        """)
        self.play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self.play_btn)

        # Progress bar - rounded slider to match preview
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BORDER_COLOR};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT_COLOR};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT_COLOR};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress, 1)

        # Duration label
        mins = int(duration) // 60
        secs = int(duration) % 60
        self.duration_label = QLabel(f"{mins}:{secs:02d}")
        self.duration_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        layout.addWidget(self.duration_label)

        # Media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(str(Path(audio_path).resolve())))
        self.player.positionChanged.connect(self._on_position)
        self.player.mediaStatusChanged.connect(self._on_status)

    def _toggle_play(self):
        if self._is_playing:
            self.player.pause()
            self.play_btn.setText("▶")
            self._is_playing = False
        else:
            self.player.play()
            self.play_btn.setText("■")
            self._is_playing = True

    def _on_position(self, pos):
        if self.player.duration() > 0:
            self.progress.setValue(int((pos / self.player.duration()) * 100))

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_btn.setText("▶")
            self._is_playing = False
            self.progress.setValue(0)


class MessageWidget(QWidget):
    """Single message with speaker label - Zed style."""

    def __init__(self, message: Message, parent=None):
        super().__init__(parent)
        self.message = message
        self._setup_ui()
        self._setup_animation()

    def _setup_animation(self):
        """Setup fade-in animation."""
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self.opacity_effect)

    def animate_in(self):
        """Fade in the message."""
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(FADE_DURATION)
        self.fade_anim.setStartValue(0)
        self.fade_anim.setEndValue(1)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade_anim.start()

    def _setup_ui(self):
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        is_user = self.message.type in (MessageType.USER_TEXT, MessageType.USER_AUDIO)
        is_loading = self.message.type == MessageType.LOADING

        # Speaker label
        if is_loading:
            label_text = "Maestro"
            label_color = AI_LABEL_COLOR
        elif is_user:
            label_text = "You"
            label_color = USER_LABEL_COLOR
        else:
            label_text = "Maestro"
            label_color = AI_LABEL_COLOR

        speaker_label = QLabel(label_text)
        speaker_label.setStyleSheet(f"""
            color: {label_color};
            font-size: {LABEL_FONT_SIZE}px;
            font-weight: bold;
            background: transparent;
            padding: 0px;
            margin: 0px;
        """)
        layout.addWidget(speaker_label)

        # Content
        if self.message.type == MessageType.LOADING:
            self.loading_anim = LoadingAnimation()
            layout.addWidget(self.loading_anim)
            self.loading_anim.start()

        elif self.message.type == MessageType.USER_AUDIO:
            # Audio player with extra spacing
            if self.message.audio_path:
                layout.addSpacing(4)
                player = AudioPlayer(self.message.audio_path, self.message.duration)
                player.setFixedWidth(280)
                layout.addWidget(player)
                layout.addSpacing(4)

            # Text content if any
            if self.message.content:
                text = QLabel(self.message.content)
                text.setWordWrap(True)
                text.setStyleSheet(f"""
                    color: {TEXT_PRIMARY};
                    font-size: {UI_FONT_SIZE}px;
                    background: transparent;
                    padding: 0px;
                    margin: 0px;
                """)
                layout.addWidget(text)
        else:
            # Plain text
            text = QLabel(self.message.content)
            text.setWordWrap(True)
            text.setStyleSheet(f"""
                color: {TEXT_PRIMARY};
                font-size: {UI_FONT_SIZE}px;
                background: transparent;
                padding: 0px;
                margin: 0px;
            """)
            layout.addWidget(text)

    def stop_loading(self):
        if hasattr(self, "loading_anim"):
            self.loading_anim.stop()


class IdleAnimation(QLabel):
    """Small idle animation that cycles through frames 1-5-1."""

    FRAME_PATHS = [str(path) for path in frame_paths()]

    def __init__(self, size=32, parent=None):
        super().__init__(parent)
        self._frame_index = 0
        self._direction = 1
        self._size = size

        # Load frames
        self._frames = []
        for path in self.FRAME_PATHS:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    size,
                    size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self._frames.append(pixmap)

        self.setStyleSheet("background: transparent;")
        self.setFixedSize(size, size)

        if self._frames:
            self.setPixmap(self._frames[0])

        # Timer for animation (240ms)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(240)

    def _animate(self):
        self._frame_index += self._direction
        if self._frame_index >= len(self._frames) - 1:
            self._direction = -1
        elif self._frame_index <= 0:
            self._direction = 1
        if self._frames:
            self.setPixmap(self._frames[self._frame_index])


class WatermarkLogo(QWidget):
    """Subtle centered logo watermark for empty state with idle animation."""

    IDLE_FRAMES = [str(path) for path in frame_paths()]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._opacity = 1.0
        self._frame_index = 0
        self._direction = 1

        # Load idle frames
        self._frames = []
        for path in self.IDLE_FRAMES:
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    80,
                    80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            self._frames.append(pixmap)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)

        # Logo image
        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setStyleSheet("background: transparent;")
        if self._frames:
            self.logo.setPixmap(self._frames[0])
        layout.addWidget(self.logo)

        # Title below
        self.title = QLabel("MAESTRO")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        layout.addStretch(1)

        self._update_style()

        # Timer for idle animation (240ms)
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._idle_animate)
        self._idle_timer.start(240)

        # Timer for manual fade
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_step)

    def _idle_animate(self):
        """Cycle through frames 1-5-1."""
        self._frame_index += self._direction
        if self._frame_index >= len(self._frames) - 1:
            self._direction = -1
        elif self._frame_index <= 0:
            self._direction = 1
        if self._frames:
            self.logo.setPixmap(self._frames[self._frame_index])

    def _update_style(self):
        """Update label styles with current opacity."""
        color = f"rgba(112, 112, 112, {self._opacity})"
        self.logo.setStyleSheet(f"background: transparent;")
        self.title.setStyleSheet(
            f"color: {color}; font-size: 14px; letter-spacing: 4px; background: transparent;"
        )

    def _fade_step(self):
        """Manual fade step."""
        self._opacity -= 0.15
        if self._opacity <= 0:
            self._opacity = 0
            self._fade_timer.stop()
            self.hide()
        self._update_style()

    def fade_out(self):
        """Fade out the watermark with smooth animation."""
        self._idle_timer.stop()
        self._fade_timer.start(30)


class ConversationArea(QScrollArea):
    """Scrollable conversation area - Zed style."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {BG_COLOR};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {BG_COLOR};
                width: 8px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background-color: {BORDER_COLOR};
                min-height: 20px;
                border-radius: 0px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #555555;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        # Main container
        self.container = QWidget()
        self.container.setStyleSheet(f"background-color: {BG_COLOR};")
        self.setWidget(self.container)

        # Enable tension/elastic scrolling
        QScroller.grabGesture(
            self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture
        )
        scroller = QScroller.scroller(self.viewport())
        props = scroller.scrollerProperties()
        props.setScrollMetric(
            QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor, 0.3
        )
        props.setScrollMetric(
            QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.2
        )
        props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollTime, 0.3)
        scroller.setScrollerProperties(props)

        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(12)

        # Add stretch to push messages to top
        self.main_layout.addStretch(1)

        # Watermark (overlaid, not in layout - so no shift when messages added)
        self.watermark = WatermarkLogo(self)
        self.watermark.raise_()

        self.messages: List[MessageWidget] = []
        self._loading_widget: Optional[MessageWidget] = None
        self._has_messages = False
        self._last_was_ai = False  # Track for dividers

    def _position_watermark(self):
        """Position watermark centered in viewport."""
        if self.watermark.isVisible():
            w = self.viewport().width()
            h = self.viewport().height()
            self.watermark.setGeometry(0, 0, w, h)

    def showEvent(self, event):
        """Position watermark on initial show."""
        super().showEvent(event)
        QTimer.singleShot(0, self._position_watermark)

    def resizeEvent(self, event):
        """Position watermark on resize."""
        super().resizeEvent(event)
        self._position_watermark()

    def _create_divider(self) -> QFrame:
        """Create a horizontal divider line."""
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {DIVIDER_COLOR};")
        return divider

    def add_message(self, message: Message) -> MessageWidget:
        """Add a message to the conversation."""
        # First message - fade out watermark
        if not self._has_messages:
            self._has_messages = True
            self.watermark.fade_out()

        is_user = message.type in (MessageType.USER_TEXT, MessageType.USER_AUDIO)

        # Add divider before user message if last was AI response
        if is_user and self._last_was_ai:
            divider = self._create_divider()
            # Insert before the stretch
            self.main_layout.insertWidget(self.main_layout.count() - 1, divider)

        widget = MessageWidget(message)
        # Insert before the stretch
        self.main_layout.insertWidget(self.main_layout.count() - 1, widget)
        self.messages.append(widget)

        # Track if this is an AI response (not loading)
        if message.type == MessageType.AI_TEXT:
            self._last_was_ai = True
        elif is_user:
            self._last_was_ai = False

        # Track loading widget
        if message.type == MessageType.LOADING:
            self._loading_widget = widget

        # Animate in
        QTimer.singleShot(10, widget.animate_in)

        # Auto-scroll
        QTimer.singleShot(50, self._scroll_bottom)

        return widget

    def remove_loading(self):
        """Remove loading indicator."""
        if self._loading_widget:
            self._loading_widget.stop_loading()
            self._loading_widget.deleteLater()
            self.messages.remove(self._loading_widget)
            self._loading_widget = None

    def _scroll_bottom(self):
        """Smoothly scroll to bottom."""
        sb = self.verticalScrollBar()
        target = sb.maximum()

        # Animate scroll
        self._scroll_anim = QPropertyAnimation(sb, b"value")
        self._scroll_anim.setDuration(SLIDE_DURATION)
        self._scroll_anim.setStartValue(sb.value())
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.start()


class MicButton(QPushButton):
    """Microphone button with smooth, rounded icon and state animations."""

    # States
    STATE_IDLE = 0
    STATE_PREPARING = 1
    STATE_RECORDING = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = self.STATE_IDLE
        self._pulse_opacity = 1.0
        self._spin_angle = 0
        self.setFixedSize(40, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style()

        # Animation timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._pulse_direction = -1

    def _update_style(self):
        if self._state == self.STATE_RECORDING:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {RECORDING_COLOR};
                    border: 2px solid {RECORDING_COLOR};
                    border-radius: 6px;
                }}
            """)
        elif self._state == self.STATE_PREPARING:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {INPUT_BG};
                    border: 2px solid {ACCENT_COLOR};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {INPUT_BG};
                    border: 2px solid {BORDER_COLOR};
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    border: 2px solid {ACCENT_COLOR};
                    background-color: #383838;
                }}
            """)
        self.update()

    def set_preparing(self):
        """Show preparing/loading state."""
        self._state = self.STATE_PREPARING
        self._spin_angle = 0
        self._update_style()
        self._anim_timer.start(30)

    def set_recording(self, recording: bool):
        if recording:
            self._state = self.STATE_RECORDING
            self._pulse_opacity = 1.0
            self._pulse_direction = -1
            self._anim_timer.start(50)
        else:
            self._state = self.STATE_IDLE
            self._anim_timer.stop()
            self._pulse_opacity = 1.0
        self._update_style()

    def _animate(self):
        """Animate based on current state."""
        if self._state == self.STATE_PREPARING:
            self._spin_angle = (self._spin_angle + 12) % 360
        elif self._state == self.STATE_RECORDING:
            self._pulse_opacity += self._pulse_direction * 0.05
            if self._pulse_opacity <= 0.4:
                self._pulse_direction = 1
            elif self._pulse_opacity >= 1.0:
                self._pulse_direction = -1
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 20, 17

        if self._state == self.STATE_PREPARING:
            # Draw spinning arc indicator
            painter.setPen(QPen(QColor(ACCENT_COLOR), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(cx - 10, cy - 8, 20, 20, self._spin_angle * 16, 270 * 16)

        else:
            # Set opacity for pulse effect when recording
            if self._state == self.STATE_RECORDING:
                painter.setOpacity(self._pulse_opacity)

            # Draw rounded mic icon
            if self._state == self.STATE_RECORDING:
                pen_color = QColor("#ffffff")
            else:
                pen_color = QColor(TEXT_SECONDARY)

            pen = QPen(pen_color, 1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Mic head (capsule shape)
            mic_path = QPainterPath()
            mic_path.addRoundedRect(cx - 4, cy - 9, 8, 14, 4, 4)
            painter.drawPath(mic_path)

            # Mic pickup arc
            painter.drawArc(cx - 7, cy - 1, 14, 10, 0, -180 * 16)

            # Stand line
            painter.drawLine(cx, cy + 9, cx, cy + 13)

            # Base
            painter.drawLine(cx - 4, cy + 13, cx + 4, cy + 13)


class AudioPreviewBar(QFrame):
    """Animated audio preview bar that slides in above input."""

    deleted = pyqtSignal()

    def __init__(self, audio_path: str, duration: float, parent=None):
        super().__init__(parent)
        self.audio_path = audio_path
        self.duration = duration
        self._is_playing = False

        self.setFixedHeight(0)  # Start collapsed
        self._target_height = 50

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_COLOR};
                border: none;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Play button
        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(32, 32)
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: #ffffff;
                border: none;
                border-radius: 16px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: #5abeef; }}
        """)
        self.play_btn.clicked.connect(self._toggle_play)
        layout.addWidget(self.play_btn)

        # Progress bar
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BORDER_COLOR};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT_COLOR};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT_COLOR};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress, 1)

        # Duration label
        mins = int(duration) // 60
        secs = int(duration) % 60
        self.duration_label = QLabel(f"{mins}:{secs:02d}")
        self.duration_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        layout.addWidget(self.duration_label)

        # Delete button
        self.delete_btn = QPushButton("×")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                font-size: 16px;
            }}
            QPushButton:hover {{ color: {RECORDING_COLOR}; }}
        """)
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn)

        # Media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(1.0)
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(str(Path(audio_path).resolve())))
        self.player.positionChanged.connect(self._on_position)
        self.player.mediaStatusChanged.connect(self._on_status)

    def slide_in(self):
        """Animate sliding in."""
        self._anim = QPropertyAnimation(self, b"maximumHeight")
        self._anim.setDuration(SLIDE_DURATION)
        self._anim.setStartValue(0)
        self._anim.setEndValue(self._target_height)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()

        self._anim2 = QPropertyAnimation(self, b"minimumHeight")
        self._anim2.setDuration(SLIDE_DURATION)
        self._anim2.setStartValue(0)
        self._anim2.setEndValue(self._target_height)
        self._anim2.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim2.start()

    def slide_out(self, callback=None):
        """Animate sliding out."""
        self.player.stop()

        self._anim = QPropertyAnimation(self, b"maximumHeight")
        self._anim.setDuration(SLIDE_DURATION)
        self._anim.setStartValue(self._target_height)
        self._anim.setEndValue(0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        if callback:
            self._anim.finished.connect(callback)
        self._anim.start()

        self._anim2 = QPropertyAnimation(self, b"minimumHeight")
        self._anim2.setDuration(SLIDE_DURATION)
        self._anim2.setStartValue(self._target_height)
        self._anim2.setEndValue(0)
        self._anim2.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim2.start()

    def _toggle_play(self):
        if self._is_playing:
            self.player.pause()
            self.play_btn.setText("▶")
            self._is_playing = False
        else:
            self.player.play()
            self.play_btn.setText("▮▮")
            self._is_playing = True

    def _on_position(self, pos):
        if self.player.duration() > 0:
            self.progress.setValue(int((pos / self.player.duration()) * 100))

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_btn.setText("▶")
            self._is_playing = False
            self.progress.setValue(0)

    def _on_delete(self):
        self.player.stop()
        self.slide_out(lambda: self.deleted.emit())


class ProviderSettingsDialog(QDialog):
    """Small provider settings dialog for the Python Maestro UI."""

    def __init__(self, provider_config: ModelProviderConfig, parent=None):
        super().__init__(parent)
        self._openai_model = (
            provider_config.openai.model
            if provider_config.openai is not None
            else ""
        )
        self._ollama_base_url = (
            provider_config.ollama.base_url
            if provider_config.ollama is not None
            else ""
        )

        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setFixedWidth(340)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE_COLOR};
                border: 1px solid {BORDER_COLOR};
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
                background: transparent;
            }}
            QLineEdit, QComboBox {{
                background-color: {INPUT_BG};
                color: {TEXT_PRIMARY};
                border: 2px solid {BORDER_COLOR};
                padding: 0 10px;
                min-height: 36px;
                font-size: {LABEL_FONT_SIZE}px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 2px solid {ACCENT_COLOR};
            }}
            QDialogButtonBox QPushButton {{
                background-color: {INPUT_BG};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                min-width: 78px;
                min-height: 34px;
                padding: 0 10px;
            }}
            QDialogButtonBox QPushButton:hover {{
                border: 1px solid {ACCENT_COLOR};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Model Settings")
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(title)

        subtitle = QLabel("Choose which provider the live edit backend should use.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        layout.addWidget(subtitle)

        provider_label = QLabel("Provider")
        provider_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        layout.addWidget(provider_label)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("OpenAI", "openai")
        self.provider_combo.addItem("Ollama", "ollama")
        layout.addWidget(self.provider_combo)

        self.openai_section = QWidget()
        openai_layout = QVBoxLayout(self.openai_section)
        openai_layout.setContentsMargins(0, 0, 0, 0)
        openai_layout.setSpacing(8)

        openai_label = QLabel("OpenAI API Key")
        openai_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        openai_layout.addWidget(openai_label)

        self.openai_key_input = QLineEdit()
        self.openai_key_input.setPlaceholderText("sk-...")
        self.openai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        if provider_config.openai is not None:
            self.openai_key_input.setText(provider_config.openai.api_key)
        openai_layout.addWidget(self.openai_key_input)
        layout.addWidget(self.openai_section)

        self.ollama_section = QWidget()
        ollama_layout = QVBoxLayout(self.ollama_section)
        ollama_layout.setContentsMargins(0, 0, 0, 0)
        ollama_layout.setSpacing(8)

        ollama_label = QLabel("Ollama Model")
        ollama_label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        ollama_layout.addWidget(ollama_label)

        self.ollama_model_input = QLineEdit()
        self.ollama_model_input.setPlaceholderText(DEFAULT_OLLAMA_MODEL)
        if provider_config.ollama is not None and provider_config.ollama.model.strip():
            self.ollama_model_input.setText(provider_config.ollama.model.strip())
        else:
            self.ollama_model_input.setText(DEFAULT_OLLAMA_MODEL)
        ollama_layout.addWidget(self.ollama_model_input)
        layout.addWidget(self.ollama_section)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        provider_name = provider_config.provider.strip().lower()
        current_index = self.provider_combo.findData(provider_name)
        if current_index < 0:
            current_index = self.provider_combo.findData("ollama")
        self.provider_combo.setCurrentIndex(current_index)
        self.provider_combo.currentIndexChanged.connect(self._update_sections)
        self._update_sections()

    def _update_sections(self):
        provider_name = self.provider_combo.currentData()
        show_openai = provider_name == "openai"
        self.openai_section.setVisible(show_openai)
        self.ollama_section.setVisible(not show_openai)

    def provider_config(self) -> ModelProviderConfig:
        provider_name = str(self.provider_combo.currentData() or "ollama")
        return ModelProviderConfig(
            provider=provider_name,
            openai=OpenAIProviderConfig(
                api_key=self.openai_key_input.text().strip(),
                model=self._openai_model,
            ),
            ollama=OllamaProviderConfig(
                model=self.ollama_model_input.text().strip() or DEFAULT_OLLAMA_MODEL,
                base_url=self._ollama_base_url,
            ),
        )


class MuseScoreSetupDialog(QDialog):
    """Guided installer/checker for the bundled MuseScore plugin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._install_state: PluginInstallState | None = None

        self.setWindowTitle("MuseScore Setup")
        self.setModal(True)
        self.setFixedWidth(420)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {SURFACE_COLOR};
                border: 1px solid {BORDER_COLOR};
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
                background: transparent;
            }}
            QPushButton {{
                background-color: {INPUT_BG};
                color: {TEXT_PRIMARY};
                border: 1px solid {BORDER_COLOR};
                min-height: 34px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                border: 1px solid {ACCENT_COLOR};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("MuseScore Setup")
        title.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: 14px; font-weight: bold;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "Install the bundled Maestro Plugin, open MuseScore, then verify that the bridge responds."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        layout.addWidget(subtitle)

        self._musescore_value = QLabel()
        self._musescore_value.setWordWrap(True)
        layout.addWidget(self._build_row("MuseScore App", self._musescore_value))

        self._plugin_dir_value = QLabel()
        self._plugin_dir_value.setWordWrap(True)
        layout.addWidget(self._build_row("Plugin Folder", self._plugin_dir_value))

        self._plugin_status_value = QLabel()
        self._plugin_status_value.setWordWrap(True)
        layout.addWidget(self._build_row("Plugin Status", self._plugin_status_value))

        self._bridge_status_value = QLabel()
        self._bridge_status_value.setWordWrap(True)
        layout.addWidget(self._build_row("Bridge Status", self._bridge_status_value))

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        install_button = QPushButton("Install Plugin")
        install_button.clicked.connect(self._install_plugin)
        button_row.addWidget(install_button)

        open_button = QPushButton("Open MuseScore")
        open_button.clicked.connect(self._open_musescore)
        button_row.addWidget(open_button)

        verify_button = QPushButton("Verify Connection")
        verify_button.clicked.connect(self._verify_bridge)
        button_row.addWidget(verify_button)

        layout.addLayout(button_row)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.refresh_status(check_bridge=False)

    @staticmethod
    def _build_row(label_text: str, value_label: QLabel) -> QWidget:
        widget = QWidget()
        row = QVBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        label = QLabel(label_text)
        label.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        row.addWidget(label)

        value_label.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {LABEL_FONT_SIZE}px;"
        )
        row.addWidget(value_label)
        return widget

    @staticmethod
    def _plugin_status_text(state: PluginInstallState) -> str:
        if state.up_to_date:
            return f"{PLUGIN_DISPLAY_NAME} is installed and up to date."

        pieces: list[str] = []
        if state.missing_files:
            pieces.append("Missing: " + ", ".join(state.missing_files))
        if state.outdated_files:
            pieces.append("Needs update: " + ", ".join(state.outdated_files))
        return "; ".join(pieces)

    def refresh_status(self, *, check_bridge: bool) -> None:
        state = inspect_plugin_install()
        self._install_state = state

        app_path = state.musescore_app_path
        if app_path is None:
            self._musescore_value.setText(
                "MuseScore 4.app not found. Expected in /Applications or ~/Applications."
            )
            self._musescore_value.setStyleSheet(
                f"color: {RECORDING_COLOR}; font-size: {LABEL_FONT_SIZE}px;"
            )
        else:
            self._musescore_value.setText(str(app_path))
            self._musescore_value.setStyleSheet(
                f"color: {TEXT_PRIMARY}; font-size: {LABEL_FONT_SIZE}px;"
            )

        self._plugin_dir_value.setText(str(state.plugin_dir))

        plugin_color = TEXT_PRIMARY if state.up_to_date else RECORDING_COLOR
        self._plugin_status_value.setText(self._plugin_status_text(state))
        self._plugin_status_value.setStyleSheet(
            f"color: {plugin_color}; font-size: {LABEL_FONT_SIZE}px;"
        )

        if check_bridge:
            ok, message = verify_bridge_connection()
            bridge_color = USER_LABEL_COLOR if ok else RECORDING_COLOR
            self._bridge_status_value.setText(message)
            self._bridge_status_value.setStyleSheet(
                f"color: {bridge_color}; font-size: {LABEL_FONT_SIZE}px;"
            )
        else:
            self._bridge_status_value.setText(
                f"After opening Plugins > Maestro > {PLUGIN_DISPLAY_NAME}, click Verify Connection."
            )
            self._bridge_status_value.setStyleSheet(
                f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;"
            )

    def _install_plugin(self) -> None:
        state = install_plugin()
        self._install_state = state
        self.refresh_status(check_bridge=False)

    def _open_musescore(self) -> None:
        try:
            path = launch_musescore()
        except FileNotFoundError as exc:
            self._musescore_value.setText(str(exc))
            self._musescore_value.setStyleSheet(
                f"color: {RECORDING_COLOR}; font-size: {LABEL_FONT_SIZE}px;"
            )
            return

        self._musescore_value.setText(str(path))
        self._musescore_value.setStyleSheet(
            f"color: {TEXT_PRIMARY}; font-size: {LABEL_FONT_SIZE}px;"
        )

    def _verify_bridge(self) -> None:
        self.refresh_status(check_bridge=True)


class BackgroundTaskThread(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self._callback = callback

    def run(self):
        try:
            result = self._callback()
        except Exception as exc:
            self.failed.emit(exc)
            return
        self.succeeded.emit(result)


class InputSection(QFrame):
    """Input section with audio preview and input bar."""

    messageSubmitted = pyqtSignal(str, str, float)  # text, audio_path, duration

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._record_ticks = 0
        self._temp_path = None
        self._recorder = None
        self._pending_audio = None  # (path, duration)

        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Audio preview area (empty initially)
        self.audio_preview_container = QWidget()
        self.audio_preview_container.setStyleSheet("background: transparent;")
        self.audio_preview_layout = QVBoxLayout(self.audio_preview_container)
        self.audio_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_preview_layout.setSpacing(0)
        layout.addWidget(self.audio_preview_container)

        self._audio_preview = None

        # Input bar
        self.input_bar = QFrame()
        self.input_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_COLOR};
                border: none;
            }}
        """)

        bar_layout = QHBoxLayout(self.input_bar)
        bar_layout.setContentsMargins(12, 12, 12, 12)
        bar_layout.setSpacing(8)

        # Mic button
        self.mic_btn = MicButton()
        self.mic_btn.clicked.connect(self._toggle_recording)
        bar_layout.addWidget(self.mic_btn)

        # Text input
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Describe changes to the score...")
        self.text_input.setFixedHeight(40)
        self.text_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {INPUT_BG};
                color: {TEXT_PRIMARY};
                border: 2px solid {BORDER_COLOR};
                border-radius: 0px;
                padding: 0 12px;
                font-size: {UI_FONT_SIZE}px;
            }}
            QLineEdit:focus {{
                border: 2px solid {ACCENT_COLOR};
            }}
            QLineEdit::placeholder {{ color: {TEXT_SECONDARY}; }}
        """)
        self.text_input.returnPressed.connect(self._submit)
        bar_layout.addWidget(self.text_input, 1)

        # Send button
        self.send_btn = QPushButton("↑")
        self.send_btn.setFixedSize(40, 40)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_send_btn_style()
        self.send_btn.clicked.connect(self._submit)
        bar_layout.addWidget(self.send_btn)

        # Connect text changes to button state
        self.text_input.textChanged.connect(self._update_send_btn_state)

        layout.addWidget(self.input_bar)

        # Recording timer
        self._rec_timer = QTimer(self)
        self._rec_timer.timeout.connect(self._on_rec_tick)

        # Track if we're waiting for response
        self._waiting = False

        # Set initial button state (disabled since text is empty)
        self._update_send_btn_state()

    def _update_send_btn_style(self):
        """Update send button style based on enabled state."""
        if self.send_btn.isEnabled():
            self.send_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {ACCENT_COLOR};
                    color: #ffffff;
                    border: none;
                    border-radius: 6px;
                    font-size: 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: #5abeef; }}
                QPushButton:pressed {{ background-color: #2d9ed9; }}
            """)
            self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.send_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {BORDER_COLOR};
                    color: {TEXT_SECONDARY};
                    border: none;
                    border-radius: 6px;
                    font-size: 20px;
                    font-weight: bold;
                }}
            """)
            self.send_btn.setCursor(Qt.CursorShape.ArrowCursor)

    def _update_send_btn_state(self):
        """Enable/disable send button based on input state."""
        has_text = bool(self.text_input.text().strip())
        can_send = has_text and not self._waiting
        self.send_btn.setEnabled(can_send)
        self._update_send_btn_style()

    def _toggle_recording(self):
        if self._recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        # Remove any existing preview first
        if self._audio_preview:
            self._audio_preview.deleteLater()
            self._audio_preview = None
            self._pending_audio = None

        # Show preparing state with spinner
        self.mic_btn.set_preparing()

        # Simulate setup delay, then start actual recording
        QTimer.singleShot(400, self._begin_recording)

    def _begin_recording(self):
        """Actually start recording after preparation."""
        try:
            recorder = MicrophoneRecorder(sample_rate=RECORD_SAMPLE_RATE)
            recorder.start()
        except Exception as exc:
            self._recorder = None
            self.mic_btn.set_recording(False)
            print(f"Microphone recording unavailable: {exc}", file=sys.stderr)
            return

        self._recorder = recorder
        self._recording = True
        self._record_ticks = 0
        self.mic_btn.set_recording(True)
        self._rec_timer.start(500)

    def _stop_recording(self):
        self._recording = False
        self._rec_timer.stop()

        # Show preparing spinner while processing
        self.mic_btn.set_preparing()

        recorder = self._recorder
        self._recorder = None
        if recorder is None:
            self.mic_btn.set_recording(False)
            return

        try:
            audio = recorder.stop()
        except Exception as exc:
            self.mic_btn.set_recording(False)
            print(f"Failed to stop recording: {exc}", file=sys.stderr)
            return

        if getattr(audio, "size", 0) == 0:
            self.mic_btn.set_recording(False)
            return

        try:
            wav_path = write_wav_file(audio, sample_rate=RECORD_SAMPLE_RATE)
        except Exception as exc:
            self.mic_btn.set_recording(False)
            print(f"Failed to write recording: {exc}", file=sys.stderr)
            return

        self._temp_path = str(wav_path)
        duration = float(len(audio)) / float(RECORD_SAMPLE_RATE)

        # Delay to show processing, then show preview
        QTimer.singleShot(300, lambda: self._finish_recording(duration))

    def _finish_recording(self, duration: float):
        """Finish recording and show preview."""
        self.mic_btn.set_recording(False)  # Back to idle

        if self._temp_path and Path(self._temp_path).exists():
            self._show_audio_preview(self._temp_path, duration)

    def _show_audio_preview(self, path: str, duration: float):
        """Show animated audio preview bar."""
        self._pending_audio = (path, duration)

        self._audio_preview = AudioPreviewBar(path, duration)
        self._audio_preview.deleted.connect(self._clear_audio_preview)
        self.audio_preview_layout.addWidget(self._audio_preview)

        # Animate in
        QTimer.singleShot(10, self._audio_preview.slide_in)

        # Update send button state
        self._update_send_btn_state()

    def _clear_audio_preview(self):
        """Clear the audio preview."""
        if self._audio_preview:
            self._audio_preview.deleteLater()
            self._audio_preview = None
        self._pending_audio = None
        self._temp_path = None
        self._update_send_btn_state()

    def _on_rec_tick(self):
        self._record_ticks += 1

    def _submit(self):
        text = self.text_input.text().strip()
        audio_path = ""
        audio_duration = 0.0

        if self._pending_audio:
            audio_path, audio_duration = self._pending_audio

        if not text:
            return

        # Slide out audio preview if present
        if self._audio_preview:
            preview = self._audio_preview
            self._audio_preview = None
            self._pending_audio = None
            preview.slide_out(lambda: preview.deleteLater())

        self.messageSubmitted.emit(text, audio_path, audio_duration)
        self.text_input.clear()

    def set_enabled(self, enabled: bool):
        self._waiting = not enabled
        self.text_input.setEnabled(enabled)
        self.mic_btn.setEnabled(enabled)
        self._update_send_btn_state()


class MaestroWindow(QWidget):
    """Main window - Zed-style flat design."""

    def __init__(self):
        super().__init__()
        self.backend = DesktopAgentBackend()
        self._provider_config = get_default_provider_config()
        self._tasks: list[BackgroundTaskThread] = []
        self._setup_prompted = False
        self._setup_window()
        self._setup_ui()
        QTimer.singleShot(0, self._maybe_prompt_setup)

    def _setup_window(self):
        self.setWindowTitle("Maestro")
        self.setMinimumSize(320, 400)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )

        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.width() - WINDOW_WIDTH - 20, (screen.height() - WINDOW_HEIGHT) // 2
        )

        self._drag_pos = None
        self._resize_edge = None
        self._resize_margin = 6

    def _setup_ui(self):
        self.setStyleSheet(f"background-color: {BG_COLOR}; border-radius: 0px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setFixedHeight(36)
        header.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_COLOR};
                border-bottom: 1px solid {BORDER_COLOR};
                border-radius: 0px;
            }}
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 8, 0)

        title = QLabel("MAESTRO")
        title.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: 11px;
            letter-spacing: 3px;
        """)
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.setup_btn = QPushButton("Setup")
        self.setup_btn.setFixedHeight(24)
        self.setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                font-size: 10px;
                letter-spacing: 1px;
                padding: 0 6px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
        """)
        self.setup_btn.setToolTip("Install or verify the MuseScore plugin")
        self.setup_btn.clicked.connect(self._open_setup_dialog)
        header_layout.addWidget(self.setup_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedSize(24, 24)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                font-size: 13px;
                border-radius: 0px;
            }}
            QPushButton:hover {{
                color: {TEXT_PRIMARY};
            }}
        """)
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        header_layout.addWidget(self.settings_btn)

        # Window buttons
        for text, action, hover_color in [
            ("−", self.showMinimized, TEXT_PRIMARY),
            ("×", self.close, RECORDING_COLOR),
        ]:
            btn = QPushButton(text)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {TEXT_SECONDARY};
                    border: none;
                    font-size: 14px;
                    border-radius: 0px;
                }}
                QPushButton:hover {{
                    color: {hover_color};
                }}
            """)
            btn.clicked.connect(action)
            header_layout.addWidget(btn)

        layout.addWidget(header)
        self._refresh_settings_tooltip()

        # Conversation area
        self.conversation = ConversationArea()
        layout.addWidget(self.conversation, 1)

        # Input section (includes audio preview + input bar)
        self.input_section = InputSection()
        self.input_section.messageSubmitted.connect(self._on_submit)
        layout.addWidget(self.input_section)

    def _start_task(self, callback, on_success, on_error):
        task = BackgroundTaskThread(callback, self)
        self._tasks.append(task)
        task.succeeded.connect(on_success)
        task.failed.connect(on_error)

        def _cleanup():
            if task in self._tasks:
                self._tasks.remove(task)

        task.finished.connect(_cleanup)
        task.finished.connect(task.deleteLater)
        task.start()

    def _on_submit(self, text: str, audio_path: str, audio_duration: float):
        # Add user message (with optional audio)
        if audio_path:
            msg = Message(
                type=MessageType.USER_AUDIO,
                content=text,
                audio_path=audio_path,
                duration=audio_duration,
            )
        else:
            msg = Message(type=MessageType.USER_TEXT, content=text)

        self.conversation.add_message(msg)

        # Show loading
        loading = Message(type=MessageType.LOADING)
        self.conversation.add_message(loading)

        self.input_section.set_enabled(False)
        provider_config = self._provider_config
        self._start_task(
            lambda: self.backend.apply_live_score_edit(
                text,
                audio_path=audio_path,
                provider=provider_config,
            ),
            self._on_live_edit_success,
            self._on_live_edit_error,
        )

    def _open_settings_dialog(self):
        dialog = ProviderSettingsDialog(self._provider_config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._provider_config = dialog.provider_config()
            self._refresh_settings_tooltip()

    def _open_setup_dialog(self):
        dialog = MuseScoreSetupDialog(self)
        dialog.exec()

    def _maybe_prompt_setup(self):
        if self._setup_prompted or os.environ.get("MAESTRO_SKIP_SETUP_PROMPT", "").strip():
            return

        state = inspect_plugin_install()
        if state.up_to_date:
            return

        self._setup_prompted = True
        self._open_setup_dialog()

    def _refresh_settings_tooltip(self):
        provider_name = self._provider_config.provider.strip().lower()
        if provider_name == "openai":
            has_key = bool(
                (
                    self._provider_config.openai is not None
                    and self._provider_config.openai.api_key.strip()
                )
                or os.environ.get("OPENAI_API_KEY", "").strip()
            )
            detail = "API key set" if has_key else "API key not set"
            self.settings_btn.setToolTip(f"Provider: OpenAI ({detail})")
            return

        model = DEFAULT_OLLAMA_MODEL
        if self._provider_config.ollama is not None and self._provider_config.ollama.model.strip():
            model = self._provider_config.ollama.model.strip()
        self.settings_btn.setToolTip(f"Provider: Ollama ({model})")

    def _on_live_edit_success(self, result: object):
        self.conversation.remove_loading()
        action_count = int(getattr(result, "action_count", 0) or 0)
        bridge_result = getattr(result, "bridge_result", {}) or {}
        all_ok = bool(bridge_result.get("all_ok", True))

        status = f"Applied {action_count} action{'s' if action_count != 1 else ''} to the open score."
        if not all_ok:
            status += "\n\nMuseScore reported partial failures. Inspect the bridge result."

        hummed_notes = str(getattr(result, "hummed_notes", "") or "").strip()
        if hummed_notes:
            status += "\n\nHummed input was used."

        self.conversation.add_message(Message(type=MessageType.AI_TEXT, content=status))
        self.input_section.set_enabled(True)
        self.input_section.text_input.setFocus()

    def _on_live_edit_error(self, exc: object):
        self.conversation.remove_loading()

        message = str(exc)
        python_code = getattr(exc, "python_code", "")
        if python_code:
            message = f"{message}\n\nGenerated edit code:\n{python_code}"

        self.conversation.add_message(Message(type=MessageType.AI_TEXT, content=message))
        self.input_section.set_enabled(True)
        self.input_section.text_input.setFocus()

    # Drag and resize handling
    def _get_resize_edge(self, pos):
        """Determine which edge/corner the mouse is near."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self._resize_margin

        edges = []
        if x < m:
            edges.append("left")
        elif x > w - m:
            edges.append("right")
        if y < m:
            edges.append("top")
        elif y > h - m:
            edges.append("bottom")

        return tuple(edges) if edges else None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            edge = self._get_resize_edge(pos)
            if edge:
                self._resize_edge = edge
                self._drag_pos = event.globalPosition().toPoint()
            elif pos.y() < 36:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()
                self._resize_edge = None

    def mouseMoveEvent(self, event):
        pos = event.position()

        # Update cursor based on position
        if event.buttons() == Qt.MouseButton.NoButton:
            edge = self._get_resize_edge(pos)
            if edge in [("left",), ("right",)]:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge in [("top",), ("bottom",)]:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif edge in [("left", "top"), ("right", "bottom")]:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif edge in [("right", "top"), ("left", "bottom")]:
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
            return

        if event.buttons() == Qt.MouseButton.LeftButton:
            if self._resize_edge:
                # Resizing
                global_pos = event.globalPosition().toPoint()
                delta = global_pos - self._drag_pos
                self._drag_pos = global_pos

                geo = self.geometry()
                min_w, min_h = self.minimumWidth(), self.minimumHeight()

                if "right" in self._resize_edge:
                    geo.setWidth(max(min_w, geo.width() + delta.x()))
                if "bottom" in self._resize_edge:
                    geo.setHeight(max(min_h, geo.height() + delta.y()))
                if "left" in self._resize_edge:
                    new_w = max(min_w, geo.width() - delta.x())
                    if new_w != geo.width():
                        geo.setLeft(geo.left() + delta.x())
                if "top" in self._resize_edge:
                    new_h = max(min_h, geo.height() - delta.y())
                    if new_h != geo.height():
                        geo.setTop(geo.top() + delta.y())

                self.setGeometry(geo)
            elif self._drag_pos:
                # Dragging
                self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resize_edge = None


def main():
    global UI_FONT
    app = QApplication(sys.argv)
    icon_path = app_icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Try to load clean sans-serif fonts (Claude-style)
    available_fonts = QFontDatabase.families()
    for font_name in [
        ".AppleSystemUIFont",
        "Helvetica Neue",
        "SF Pro",
        "Inter",
        "Helvetica",
        "Arial",
    ]:
        if font_name in available_fonts:
            UI_FONT = font_name
            app.setFont(QFont(font_name, UI_FONT_SIZE))
            print(f"Using font: {font_name}")
            break

    window = MaestroWindow()
    if icon_path.is_file():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
