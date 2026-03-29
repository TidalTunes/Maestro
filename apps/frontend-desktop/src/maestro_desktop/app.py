#!/usr/bin/env python3
"""
Maestro - AI Compose Assistant for MuseScore
Zed-style flat editorial layout. No bubbles, no rounded corners.
"""

from pathlib import Path
import sys
import os
from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QScrollArea, QSizePolicy,
    QGraphicsOpacityEffect, QSlider, QScroller, QScrollerProperties,
    QPlainTextEdit
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QUrl, QThread
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QFontDatabase, QPainterPath
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from .backend import CapturedHumming, DesktopAgentBackend

# ============== CONFIGURATION ==============
WINDOW_WIDTH = 420
WINDOW_HEIGHT = 600

# Colors
BG_COLOR = "#1a1a1a"
SURFACE_COLOR = "#252525"
INPUT_BG = "#2d2d2d"
BORDER_COLOR = "#3a3a3a"
ACCENT_COLOR = "#3daee9"
USER_LABEL_COLOR = "#3daee9"      # Cyan for "you"
AI_LABEL_COLOR = "#d4a84b"        # Warm gold for "maestro"
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
    AI_TEXT = "ai_text"
    AI_CODE = "ai_code"
    LOADING = "loading"


@dataclass
class Message:
    type: MessageType
    content: str = ""
    audio_path: Optional[str] = None
    duration: float = 0.0


class LoadingAnimation(QLabel):
    """Animated 'thinking...' text with cycling dots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dot_count = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._update_text()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: {UI_FONT_SIZE}px;
            font-style: italic;
            background: transparent;
        """)

    def _update_text(self):
        dots = "." * self._dot_count
        spaces = " " * (3 - self._dot_count)
        self.setText(f"thinking{dots}{spaces}")

    def start(self):
        self._dot_count = 0
        self._update_text()
        self._timer.start(400)

    def stop(self):
        self._timer.stop()

    def _animate(self):
        self._dot_count = (self._dot_count + 1) % 4
        self._update_text()


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
        self.duration_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;")
        layout.addWidget(self.duration_label)

        # Media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(audio_path))
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

        is_user = self.message.type == MessageType.USER_TEXT
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

        elif self.message.type == MessageType.AI_CODE:
            code = QPlainTextEdit()
            code.setReadOnly(True)
            code.setPlainText(self.message.content)
            code.setMinimumHeight(110)
            code.setMaximumHeight(240)
            code.setStyleSheet(f"""
                QPlainTextEdit {{
                    background-color: {INPUT_BG};
                    color: {TEXT_PRIMARY};
                    border: 2px solid {BORDER_COLOR};
                    padding: 8px;
                    font-family: Menlo, Monaco, 'Courier New', monospace;
                    font-size: 12px;
                }}
            """)
            layout.addWidget(code)
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
        if hasattr(self, 'loading_anim'):
            self.loading_anim.stop()


class WatermarkLogo(QWidget):
    """Subtle centered logo watermark for empty state."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._opacity = 1.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)

        # Music note symbol
        self.note = QLabel("♪")
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.note)

        # Title below
        self.title = QLabel("MAESTRO")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)

        layout.addStretch(1)

        self._update_style()

        # Timer for manual fade
        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._fade_step)

    def _update_style(self):
        """Update label styles with current opacity."""
        alpha = int(self._opacity * 112)  # TEXT_SECONDARY is #707070, so ~112 brightness
        color = f"rgba(112, 112, 112, {self._opacity})"
        self.note.setStyleSheet(f"color: {color}; font-size: 48px; background: transparent;")
        self.title.setStyleSheet(f"color: {color}; font-size: 14px; letter-spacing: 4px; background: transparent;")

    def _fade_step(self):
        """Manual fade step."""
        self._opacity -= 0.05
        if self._opacity <= 0:
            self._opacity = 0
            self._fade_timer.stop()
            self.hide()
        self._update_style()

    def fade_out(self):
        """Fade out the watermark with smooth animation."""
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
        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        props = scroller.scrollerProperties()
        props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor, 0.3)
        props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.2)
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

        is_user = message.type == MessageType.USER_TEXT

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
        self.duration_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: {LABEL_FONT_SIZE}px;")
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
        self.player.setAudioOutput(self.audio_output)
        self.player.setSource(QUrl.fromLocalFile(audio_path))
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


class HummedNotesBar(QFrame):
    """Compact preview for transcribed humming notes."""

    cleared = pyqtSignal()

    def __init__(self, notes: str, parent=None):
        super().__init__(parent)
        self._target_height = 68

        self.setFixedHeight(0)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_COLOR};
                border-top: 1px solid {BORDER_COLOR};
                border-bottom: 1px solid {BORDER_COLOR};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        label = QLabel("Hummed")
        label.setStyleSheet(f"""
            color: {AI_LABEL_COLOR};
            font-size: {LABEL_FONT_SIZE}px;
            font-weight: bold;
        """)
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignTop)

        self.notes_label = QLabel(notes)
        self.notes_label.setWordWrap(True)
        self.notes_label.setStyleSheet(f"""
            color: {TEXT_PRIMARY};
            font-size: {LABEL_FONT_SIZE}px;
            background: transparent;
        """)
        layout.addWidget(self.notes_label, 1)

        clear_btn = QPushButton("×")
        clear_btn.setFixedSize(24, 24)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                font-size: 16px;
            }}
            QPushButton:hover {{ color: {RECORDING_COLOR}; }}
        """)
        clear_btn.clicked.connect(self._on_clear)
        layout.addWidget(clear_btn, 0, Qt.AlignmentFlag.AlignTop)

    def set_notes(self, notes: str):
        self.notes_label.setText(notes)

    def slide_in(self):
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

    def _on_clear(self):
        self.cleared.emit()


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
    """Input section with API key, humming controls, and prompt entry."""

    messageSubmitted = pyqtSignal(str, str, str)  # text, api_key, hummed_notes
    recordStartRequested = pyqtSignal()
    recordStopRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._record_transition_pending = False
        self._hummed_notes = ""
        self._recorded_audio_path = ""
        self._recorded_audio_duration = 0.0
        self._audio_preview: Optional[AudioPreviewBar] = None
        self._notes_preview: Optional[HummedNotesBar] = None

        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.credentials_bar = QFrame()
        self.credentials_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {SURFACE_COLOR};
                border-top: 1px solid {BORDER_COLOR};
            }}
        """)
        credentials_layout = QHBoxLayout(self.credentials_bar)
        credentials_layout.setContentsMargins(12, 10, 12, 10)
        credentials_layout.setSpacing(8)

        credentials_label = QLabel("KEY")
        credentials_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: {LABEL_FONT_SIZE}px;
            letter-spacing: 2px;
        """)
        credentials_layout.addWidget(credentials_label)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("OpenAI API key")
        self.api_key_input.setText(os.environ.get("OPENAI_API_KEY", "").strip())
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setFixedHeight(34)
        self.api_key_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {INPUT_BG};
                color: {TEXT_PRIMARY};
                border: 2px solid {BORDER_COLOR};
                border-radius: 0px;
                padding: 0 10px;
                font-size: {LABEL_FONT_SIZE}px;
            }}
            QLineEdit:focus {{
                border: 2px solid {ACCENT_COLOR};
            }}
            QLineEdit::placeholder {{ color: {TEXT_SECONDARY}; }}
        """)
        credentials_layout.addWidget(self.api_key_input, 1)
        layout.addWidget(self.credentials_bar)

        self.audio_preview_container = QWidget()
        self.audio_preview_container.setStyleSheet("background: transparent;")
        self.audio_preview_layout = QVBoxLayout(self.audio_preview_container)
        self.audio_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.audio_preview_layout.setSpacing(0)
        layout.addWidget(self.audio_preview_container)

        self.notes_preview_container = QWidget()
        self.notes_preview_container.setStyleSheet("background: transparent;")
        self.notes_preview_layout = QVBoxLayout(self.notes_preview_container)
        self.notes_preview_layout.setContentsMargins(0, 0, 0, 0)
        self.notes_preview_layout.setSpacing(0)
        layout.addWidget(self.notes_preview_container)

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

        self.text_input.textChanged.connect(self._update_send_btn_state)
        self.api_key_input.textChanged.connect(self._update_send_btn_state)

        layout.addWidget(self.input_bar)

        self.status_label = QLabel("Ready.")
        self.status_label.setStyleSheet(f"""
            color: {TEXT_SECONDARY};
            font-size: {LABEL_FONT_SIZE}px;
            padding: 8px 12px 10px 12px;
            background-color: {SURFACE_COLOR};
            border-top: 1px solid {BORDER_COLOR};
        """)
        layout.addWidget(self.status_label)

        self._waiting = False
        self._update_send_btn_state()

    def _update_send_btn_style(self):
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
        has_text = bool(self.text_input.text().strip())
        has_api_key = bool(self.api_key_input.text().strip())
        can_send = (
            has_text
            and has_api_key
            and not self._waiting
            and not self._recording
            and not self._record_transition_pending
        )
        self.send_btn.setEnabled(can_send)
        self.mic_btn.setEnabled(not self._waiting and not self._record_transition_pending)
        self._update_send_btn_style()

    def _toggle_recording(self):
        if self._waiting or self._record_transition_pending:
            return
        if self._recording:
            self._record_transition_pending = True
            self.mic_btn.set_preparing()
            self.set_status("Transcribing...", error=False)
            self._update_send_btn_state()
            self.recordStopRequested.emit()
        else:
            self._record_transition_pending = True
            self.clear_recording_artifacts()
            self.mic_btn.set_preparing()
            self.set_status("Preparing microphone...", error=False)
            self._update_send_btn_state()
            self.recordStartRequested.emit()

    def set_status(self, text: str, *, error: bool):
        color = RECORDING_COLOR if error else TEXT_SECONDARY
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"""
            color: {color};
            font-size: {LABEL_FONT_SIZE}px;
            padding: 8px 12px 10px 12px;
            background-color: {SURFACE_COLOR};
            border-top: 1px solid {BORDER_COLOR};
        """)

    def confirm_recording_started(self, status: str):
        self._record_transition_pending = False
        self._recording = True
        self.mic_btn.set_recording(True)
        self.set_status(status, error=False)
        self._update_send_btn_state()

    def confirm_recording_stopped(self, capture: CapturedHumming, status: str):
        self._record_transition_pending = False
        self._recording = False
        self.mic_btn.set_recording(False)
        self.set_recorded_audio(capture.audio_path, capture.duration_seconds)
        self.set_hummed_notes(capture.notes)
        self.set_status(status, error=False)
        self._update_send_btn_state()

    def show_recording_error(self, message: str):
        self._record_transition_pending = False
        self._recording = False
        self.mic_btn.set_recording(False)
        self.set_status(message, error=True)
        self._update_send_btn_state()

    def set_hummed_notes(self, notes: str):
        self._hummed_notes = notes.strip()
        if not self._hummed_notes:
            self._clear_hummed_notes_preview()
            return

        if self._notes_preview is None:
            self._notes_preview = HummedNotesBar(self._hummed_notes)
            self._notes_preview.cleared.connect(self.clear_recording_artifacts)
            self.notes_preview_layout.addWidget(self._notes_preview)
            QTimer.singleShot(10, self._notes_preview.slide_in)
        else:
            self._notes_preview.set_notes(self._hummed_notes)

        self._update_send_btn_state()

    def set_recorded_audio(self, audio_path: str, duration: float):
        self._clear_audio_preview(delete_file=False)

        self._recorded_audio_path = audio_path
        self._recorded_audio_duration = duration
        if not audio_path:
            return

        self._audio_preview = AudioPreviewBar(audio_path, duration)
        self._audio_preview.deleted.connect(self._on_audio_preview_deleted)
        self.audio_preview_layout.addWidget(self._audio_preview)
        QTimer.singleShot(10, self._audio_preview.slide_in)

    def clear_recording_artifacts(self):
        self._hummed_notes = ""
        self._clear_hummed_notes_preview()
        self._clear_audio_preview(delete_file=True)
        self._update_send_btn_state()

    def _clear_hummed_notes_preview(self):
        if self._notes_preview:
            preview = self._notes_preview
            self._notes_preview = None
            preview.slide_out(lambda: preview.deleteLater())

    def _clear_audio_preview(self, *, delete_file: bool):
        audio_path = self._recorded_audio_path
        self._recorded_audio_path = ""
        self._recorded_audio_duration = 0.0

        def finalize():
            if delete_file and audio_path:
                Path(audio_path).unlink(missing_ok=True)

        if self._audio_preview:
            preview = self._audio_preview
            self._audio_preview = None

            def remove_preview():
                preview.deleteLater()
                finalize()

            preview.slide_out(remove_preview)
        else:
            finalize()

    def _on_audio_preview_deleted(self):
        audio_path = self._recorded_audio_path
        self._recorded_audio_path = ""
        self._recorded_audio_duration = 0.0
        self._hummed_notes = ""

        if self._audio_preview:
            preview = self._audio_preview
            self._audio_preview = None
            preview.deleteLater()

        self._clear_hummed_notes_preview()
        if audio_path:
            Path(audio_path).unlink(missing_ok=True)
        self._update_send_btn_state()

    def _submit(self):
        text = self.text_input.text().strip()
        api_key = self.api_key_input.text().strip()
        if not text or not api_key:
            return

        self.messageSubmitted.emit(text, api_key, self._hummed_notes)
        self.text_input.clear()
        self._update_send_btn_state()

    def set_enabled(self, enabled: bool):
        self._waiting = not enabled
        self.text_input.setEnabled(enabled)
        self.api_key_input.setEnabled(enabled)
        self._update_send_btn_state()


class MaestroWindow(QWidget):
    """Main window - Zed-style flat design."""

    def __init__(self):
        super().__init__()
        self.backend = DesktopAgentBackend()
        self._tasks: list[BackgroundTaskThread] = []
        self._setup_window()
        self._setup_ui()

    def _setup_window(self):
        self.setWindowTitle("Maestro")
        self.setMinimumSize(320, 400)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - WINDOW_WIDTH - 20,
                  (screen.height() - WINDOW_HEIGHT) // 2)

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

        # Window buttons
        for text, action, hover_color in [
            ("−", self.showMinimized, TEXT_PRIMARY),
            ("×", self.close, RECORDING_COLOR)
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

        # Conversation area
        self.conversation = ConversationArea()
        layout.addWidget(self.conversation, 1)

        # Input section
        self.input_section = InputSection()
        self.input_section.messageSubmitted.connect(self._on_submit)
        self.input_section.recordStartRequested.connect(self._start_humming)
        self.input_section.recordStopRequested.connect(self._stop_humming)
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

    def _start_humming(self):
        self._start_task(
            self.backend.start_humming,
            lambda _: self.input_section.confirm_recording_started("Recording... hum, then press Stop."),
            self._on_humming_error,
        )

    def _stop_humming(self):
        self._start_task(
            self.backend.stop_humming,
            self._on_humming_stopped,
            self._on_humming_error,
        )

    def _on_humming_stopped(self, capture: object):
        notes = getattr(capture, "notes", "") or ""
        status = "Humming captured." if str(notes).strip() else "No stable notes detected. Try again."
        self.input_section.confirm_recording_stopped(capture, status)

    def _on_humming_error(self, exc: object):
        self.input_section.show_recording_error(str(exc))

    def _on_submit(self, text: str, api_key: str, hummed_notes: str):
        content = text
        cleaned_hummed_notes = hummed_notes.strip()
        if cleaned_hummed_notes:
            content = f"{text}\n\nHummed notes:\n{cleaned_hummed_notes}"

        self.conversation.add_message(Message(type=MessageType.USER_TEXT, content=content))
        self.conversation.add_message(Message(type=MessageType.LOADING))

        self.input_section.set_enabled(False)
        self.input_section.set_status("Generating...", error=False)

        self._start_task(
            lambda: self.backend.generate_code(text, api_key, cleaned_hummed_notes),
            self._on_generation_success,
            self._on_generation_error,
        )

    def _on_generation_success(self, result: object):
        self.conversation.remove_loading()
        python_code = getattr(result, "python_code", "")
        self.conversation.add_message(Message(type=MessageType.AI_CODE, content=python_code))
        self.input_section.set_enabled(True)
        self.input_section.set_status("Code ready.", error=False)
        self.input_section.text_input.setFocus()

    def _on_generation_error(self, exc: object):
        self.conversation.remove_loading()
        self.conversation.add_message(Message(type=MessageType.AI_TEXT, content=str(exc)))

        python_code = getattr(exc, "python_code", "")
        if python_code:
            self.conversation.add_message(Message(type=MessageType.AI_CODE, content=python_code))

        self.input_section.set_enabled(True)
        self.input_section.set_status("Generation failed.", error=True)
        self.input_section.text_input.setFocus()

    # Drag and resize handling
    def _get_resize_edge(self, pos):
        """Determine which edge/corner the mouse is near."""
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self._resize_margin

        edges = []
        if x < m:
            edges.append('left')
        elif x > w - m:
            edges.append('right')
        if y < m:
            edges.append('top')
        elif y > h - m:
            edges.append('bottom')

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
            if edge in [('left',), ('right',)]:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif edge in [('top',), ('bottom',)]:
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            elif edge in [('left', 'top'), ('right', 'bottom')]:
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif edge in [('right', 'top'), ('left', 'bottom')]:
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

                if 'right' in self._resize_edge:
                    geo.setWidth(max(min_w, geo.width() + delta.x()))
                if 'bottom' in self._resize_edge:
                    geo.setHeight(max(min_h, geo.height() + delta.y()))
                if 'left' in self._resize_edge:
                    new_w = max(min_w, geo.width() - delta.x())
                    if new_w != geo.width():
                        geo.setLeft(geo.left() + delta.x())
                if 'top' in self._resize_edge:
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

    # Try to load clean sans-serif fonts (Claude-style)
    available_fonts = QFontDatabase.families()
    for font_name in [".AppleSystemUIFont", "Helvetica Neue", "SF Pro", "Inter", "Helvetica", "Arial"]:
        if font_name in available_fonts:
            UI_FONT = font_name
            app.setFont(QFont(font_name, UI_FONT_SIZE))
            print(f"Using font: {font_name}")
            break

    window = MaestroWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
