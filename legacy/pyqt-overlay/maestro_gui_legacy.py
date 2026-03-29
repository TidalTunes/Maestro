#!/usr/bin/env python3
"""
Maestro - AI Compose Assistant for MuseScore 4
A floating overlay GUI panel for AI-assisted music composition.
"""

import sys
import math
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QRectF
)
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QTransform

# ============== EASY ACCESS VARIABLES ==============
WINDOW_TITLE = "Maestro"
WINDOW_SUBTITLE = "AI Compose Assistant"
WINDOW_WIDTH = 380
WINDOW_HEIGHT = 540
ACCENT_COLOR = "#3DAEE9"          # MuseScore's cyan-blue highlight
BG_COLOR = "#2D2D2D"              # Main dark gray background
SURFACE_COLOR = "#3D3D3D"         # Slightly lighter surface/panels
BORDER_COLOR = "#4A4A4A"          # Subtle borders
TEXT_PRIMARY = "#FFFFFF"          # White text
TEXT_SECONDARY = "#909090"        # Gray secondary text
BORDER_RADIUS = 0  # Angular design, no rounded corners
# ===================================================


class MusicLoadingWidget(QWidget):
    """Custom animated music staff with rippling notes."""

    # Status messages
    STATUS_MESSAGES = [
        "Composing...",
        "Arranging notes...",
        "Harmonizing...",
        "Almost there..."
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(100)

        # Animation state
        self._tick = 0
        self._status_index = 0
        self._status_time = 0

        # Note positions on staff (which line/space, 0-8 where 0=bottom, 8=top)
        self._note_positions = [2, 4, 6, 3, 5, 7, 4]  # Notes at different staff positions
        self._note_chars = ["♩", "♪", "♫", "♪", "♩", "♪", "♫"]

        # Timer for animation (~30fps)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)

    def start(self):
        """Start the animation."""
        self._tick = 0
        self._status_index = 0
        self._status_time = 0
        self._timer.start(33)  # ~30fps

    def stop(self):
        """Stop the animation."""
        self._timer.stop()
        self._tick = 0
        self.update()

    def get_status_text(self) -> str:
        """Get current status message."""
        return self.STATUS_MESSAGES[self._status_index]

    def _on_tick(self):
        """Called on each animation frame."""
        self._tick += 1
        self._status_time += 33

        # Switch status message every 2 seconds
        if self._status_time >= 2000:
            self._status_time = 0
            self._status_index = (self._status_index + 1) % len(self.STATUS_MESSAGES)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        width = self.width()
        height = self.height()

        # Staff dimensions
        staff_left = 30
        staff_right = width - 30
        staff_width = staff_right - staff_left
        staff_top = 15
        staff_height = 40
        line_spacing = staff_height / 4

        # Draw the 5 staff lines
        painter.setPen(QColor(BORDER_COLOR))
        for i in range(5):
            y = staff_top + i * line_spacing
            painter.drawLine(int(staff_left), int(y), int(staff_right), int(y))

        # Draw treble clef symbol
        painter.setPen(QColor(TEXT_SECONDARY))
        font = painter.font()
        font.setPointSize(28)
        painter.setFont(font)
        painter.drawText(int(staff_left - 5), int(staff_top + staff_height - 5), "𝄞")

        # Draw rippling notes
        num_notes = len(self._note_positions)
        note_spacing = staff_width / (num_notes + 1)

        for i in range(num_notes):
            # Calculate ripple phase for this note
            phase = (self._tick * 0.12) - (i * 0.5)
            ripple = math.sin(phase)

            # Opacity based on ripple (0.3 to 1.0)
            opacity = 0.3 + (ripple + 1) / 2 * 0.7

            # Vertical offset for bounce effect
            bounce = ripple * 3

            # Calculate position
            x = staff_left + note_spacing * (i + 1)
            # Map note position (0-8) to y coordinate on staff
            base_y = staff_top + staff_height - (self._note_positions[i] * line_spacing / 2)
            y = base_y + bounce

            # Draw the note
            painter.save()
            painter.setOpacity(opacity)
            painter.setPen(QColor(ACCENT_COLOR))

            note_font = painter.font()
            note_font.setPointSize(16)
            painter.setFont(note_font)

            painter.drawText(int(x - 6), int(y + 6), self._note_chars[i])
            painter.restore()

        # Draw status text
        painter.setOpacity(1.0)
        painter.setPen(QColor(TEXT_SECONDARY))
        font = painter.font()
        font.setPointSize(11)
        painter.setFont(font)

        text_rect = QRectF(0, staff_top + staff_height + 15, width, 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.get_status_text())


class WavyTextEdit(QTextEdit):
    """Custom text edit with wavy character positioning."""

    def __init__(self, parent=None, submit_callback=None):
        super().__init__(parent)
        self.submit_callback = submit_callback
        self._wave_amplitude = 2  # Pixels to shift up/down

        # Make text transparent so we can draw it ourselves
        self.setStyleSheet("color: transparent; background-color: transparent;")

        # Track for redraw
        self.textChanged.connect(self.update)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self.submit_callback:
                self.submit_callback()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        # Let the base class paint (handles cursor, selection, etc.)
        super().paintEvent(event)

        # Now draw our wavy text on top
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        text = self.toPlainText()

        if not text:
            # Draw placeholder with wavy effect
            painter.setPen(QColor("#666666"))
            placeholder = self.placeholderText()
            self._draw_wavy_text(painter, placeholder, 12, 20, is_placeholder=True)
        else:
            # Draw actual text with wavy effect
            painter.setPen(QColor(TEXT_PRIMARY))
            self._draw_wavy_text(painter, text, 12, 20, is_placeholder=False)

        painter.end()

    def _draw_wavy_text(self, painter, text: str, start_x: int, start_y: int, is_placeholder: bool = False):
        """Draw text with alternating vertical positions."""
        font = QFont("Palatino", 11)
        if is_placeholder:
            font.setItalic(True)
        painter.setFont(font)

        metrics = painter.fontMetrics()
        x = start_x

        for i, char in enumerate(text):
            # Alternate up and down
            y_offset = -self._wave_amplitude if i % 2 == 0 else self._wave_amplitude
            y = start_y + y_offset

            painter.drawText(int(x), int(y), char)
            x += metrics.horizontalAdvance(char)


class PromptTextEdit(QTextEdit):
    """Custom text edit that handles Enter vs Shift+Enter."""

    def __init__(self, parent=None, submit_callback=None):
        super().__init__(parent)
        self.submit_callback = submit_callback

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Return and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            if self.submit_callback:
                self.submit_callback()
        else:
            super().keyPressEvent(event)


class MaestroWindow(QWidget):
    """Main Maestro overlay window."""

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._is_loading = False
        self._history = []  # List of (prompt, summary) tuples
        # Typewriter animation state
        self._typewriter_timer = None
        self._typewriter_text = ""
        self._typewriter_index = 0
        self._typewriter_prompt = ""
        self._setup_window()
        self._setup_ui()
        self._apply_styles()

    def _setup_window(self):
        """Configure window properties."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # Frameless, always on top, tool window (less intrusive)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Position on right side of screen
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - WINDOW_WIDTH - 20
        y = (screen.height() - WINDOW_HEIGHT) // 2
        self.move(x, y)

    def _setup_ui(self):
        """Build the user interface."""
        # Main container with rounded corners
        self.container = QFrame(self)
        self.container.setObjectName("container")
        self.container.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(16, 8, 16, 12)
        main_layout.setSpacing(0)

        # === Header Section ===
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        # Spacer to push buttons to the right
        header_layout.addStretch()

        # Minimize button
        self.minimize_btn = QPushButton("—")
        self.minimize_btn.setObjectName("windowBtn")
        self.minimize_btn.setFixedSize(20, 20)
        self.minimize_btn.clicked.connect(self.showMinimized)
        header_layout.addWidget(self.minimize_btn)

        # Close button
        self.close_btn = QPushButton("×")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.close)
        header_layout.addWidget(self.close_btn)

        main_layout.addWidget(header_widget)

        # === Main Content Area (Welcome / Summary) ===
        self.content_area = QWidget()
        self.content_area.setObjectName("contentArea")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Welcome screen (shown initially)
        self.welcome_widget = QWidget()
        self.welcome_widget.setObjectName("welcomeWidget")
        welcome_layout = QVBoxLayout(self.welcome_widget)
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.setSpacing(16)

        # Music note logo
        self.logo_label = QLabel("♪")
        self.logo_label.setObjectName("logoLabel")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(self.logo_label)

        # Welcome text
        self.welcome_text = QLabel("Let's compose")
        self.welcome_text.setObjectName("welcomeText")
        self.welcome_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(self.welcome_text)

        content_layout.addWidget(self.welcome_widget)

        # Summary display (hidden initially, shown after first submission)
        self.summary_display = QTextEdit()
        self.summary_display.setObjectName("summaryDisplay")
        self.summary_display.setReadOnly(True)
        self.summary_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.summary_display.hide()
        content_layout.addWidget(self.summary_display)

        # Loading section (music animation)
        self.loading_section = QWidget()
        self.loading_section.setObjectName("loadingSection")
        loading_layout = QVBoxLayout(self.loading_section)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.music_loader = MusicLoadingWidget()
        loading_layout.addWidget(self.music_loader)

        self.loading_section.hide()
        content_layout.addWidget(self.loading_section)

        main_layout.addWidget(self.content_area, 1)

        # === Bottom Input Section ===
        input_section = QFrame()
        input_section.setObjectName("inputSection")
        input_layout = QVBoxLayout(input_section)
        input_layout.setContentsMargins(0, 12, 0, 0)
        input_layout.setSpacing(8)

        # Input row with text field and send button
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.prompt_input = WavyTextEdit(submit_callback=self._handle_submit)
        self.prompt_input.setObjectName("promptInput")
        self.prompt_input.setPlaceholderText("Describe your changes...")
        self.prompt_input.setFixedHeight(36)
        self.prompt_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        input_row.addWidget(self.prompt_input)

        self.compose_btn = QPushButton("↑")
        self.compose_btn.setObjectName("sendBtn")
        self.compose_btn.setFixedSize(36, 36)
        self.compose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.compose_btn.clicked.connect(self._handle_submit)
        input_row.addWidget(self.compose_btn)

        input_layout.addLayout(input_row)

        main_layout.addWidget(input_section)

    def _apply_styles(self):
        """Apply stylesheet to the window."""
        stylesheet = f"""
            #container {{
                background-color: {BG_COLOR};
                border: 1px solid {BORDER_COLOR};
                border-radius: {BORDER_RADIUS}px;
            }}

            #contentArea {{
                background-color: transparent;
            }}

            #welcomeWidget {{
                background-color: transparent;
            }}

            #logoLabel {{
                color: {ACCENT_COLOR};
                font-size: 64px;
                background-color: transparent;
            }}

            #welcomeText {{
                color: {TEXT_SECONDARY};
                font-size: 18px;
                font-style: italic;
                background-color: transparent;
            }}

            #windowBtn {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
            }}

            #windowBtn:hover {{
                background-color: {SURFACE_COLOR};
                color: {TEXT_PRIMARY};
            }}

            #closeBtn {{
                background-color: transparent;
                color: {TEXT_SECONDARY};
                border: none;
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
            }}

            #closeBtn:hover {{
                background-color: #E04040;
                color: {TEXT_PRIMARY};
            }}

            #inputSection {{
                background-color: transparent;
                border-top: 1px solid {BORDER_COLOR};
            }}

            #loadingSection {{
                background-color: transparent;
            }}

            #promptInput {{
                background-color: {SURFACE_COLOR};
                color: transparent;
                border: 1px solid {BORDER_COLOR};
                border-radius: 2px;
                padding: 10px;
                font-family: Palatino, Georgia, "Times New Roman", serif;
                font-size: 13px;
            }}

            #promptInput:focus {{
                border: 1px solid {ACCENT_COLOR};
            }}

            #sendBtn {{
                background-color: {ACCENT_COLOR};
                color: {TEXT_PRIMARY};
                border: none;
                border-radius: 4px;
                font-size: 18px;
                font-weight: bold;
            }}

            #sendBtn:hover {{
                background-color: #5ABEEF;
            }}

            #sendBtn:pressed {{
                background-color: #2D9ED9;
            }}

            #sendBtn:disabled {{
                background-color: {BORDER_COLOR};
                color: {TEXT_SECONDARY};
            }}

            #summaryDisplay {{
                background-color: transparent;
                color: {TEXT_PRIMARY};
                border: none;
                padding: 12px;
                font-family: Palatino, Georgia, "Times New Roman", serif;
                font-size: 13px;
            }}

            QScrollBar:vertical {{
                background-color: transparent;
                width: 6px;
                border-radius: 3px;
            }}

            QScrollBar::handle:vertical {{
                background-color: {BORDER_COLOR};
                border-radius: 3px;
                min-height: 20px;
            }}

            QScrollBar::handle:vertical:hover {{
                background-color: {TEXT_SECONDARY};
            }}

            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """
        self.setStyleSheet(stylesheet)

    # === Drag functionality ===
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Only allow dragging from the header area (top 50px)
            if event.position().y() < 50:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()
                event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # === Public API Methods ===

    def on_prompt_submit(self, prompt_text: str) -> str:
        """
        Called when user submits a prompt.
        prompt_text: the user's input string

        This is where you connect to your AI backend.
        For now, just simulate a 2-second delay and return a placeholder summary.

        Override this method or replace it to connect to your actual AI service.
        """
        # TODO: Replace with actual AI call
        placeholder_summary = f"Processed prompt: {prompt_text}\n\nChanges applied to measures 4-8."
        return placeholder_summary

    def set_summary(self, summary_text: str, prompt_text: str = None):
        """Call this to update the summary display from external code."""
        if prompt_text:
            self._history.append((prompt_text, summary_text))
        self._render_history()

    def add_entry(self, prompt_text: str, summary_text: str, animate: bool = True):
        """Add a new prompt/summary entry to the history."""
        if animate:
            self._start_typewriter(prompt_text, summary_text)
        else:
            self._history.append((prompt_text, summary_text))
            self._render_history()

    def _start_typewriter(self, prompt_text: str, summary_text: str):
        """Start the typewriter animation for a new entry."""
        # Stop any existing animation
        if self._typewriter_timer:
            self._typewriter_timer.stop()

        self._typewriter_prompt = prompt_text
        self._typewriter_text = summary_text
        self._typewriter_index = 0

        # Create timer for animation (20ms per character for smooth effect)
        self._typewriter_timer = QTimer(self)
        self._typewriter_timer.timeout.connect(self._typewriter_tick)
        self._typewriter_timer.start(20)

        # Render immediately with empty summary to show the prompt
        self._render_history_with_partial_summary(prompt_text, "")

    def _typewriter_tick(self):
        """Called on each tick of the typewriter animation."""
        self._typewriter_index += 1

        if self._typewriter_index >= len(self._typewriter_text):
            # Animation complete
            self._typewriter_timer.stop()
            self._typewriter_timer = None
            # Add final entry to history
            self._history.append((self._typewriter_prompt, self._typewriter_text))
            self._render_history()
        else:
            # Show partial text
            partial_text = self._typewriter_text[:self._typewriter_index]
            self._render_history_with_partial_summary(self._typewriter_prompt, partial_text)

    def _render_history_with_partial_summary(self, current_prompt: str, partial_summary: str):
        """Render history with a partial summary for the current entry (typewriter effect)."""
        # Hide welcome, show summary
        self.welcome_widget.hide()
        self.summary_display.show()

        html_parts = []

        # Render existing history entries
        for i, (prompt, summary) in enumerate(self._history):
            if i > 0:
                html_parts.append(f'''
                    <div style="border-top: 1px solid {BORDER_COLOR}; margin: 16px 0;"></div>
                ''')
            html_parts.append(self._format_entry_html(prompt, summary))

        # Add separator if there's existing history
        if self._history:
            html_parts.append(f'''
                <div style="border-top: 1px solid {BORDER_COLOR}; margin: 16px 0;"></div>
            ''')

        # Render current entry with partial summary (and blinking cursor)
        html_parts.append(self._format_entry_html(current_prompt, partial_summary, show_cursor=True))

        full_html = f'''
            <div style="font-family: Palatino, Georgia, 'Times New Roman', serif; font-size: 13px;">
                {''.join(html_parts)}
            </div>
        '''
        self.summary_display.setHtml(full_html)
        scrollbar = self.summary_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _format_entry_html(self, prompt: str, summary: str, show_cursor: bool = False) -> str:
        """Format a single entry as HTML."""
        cursor = '<span style="color: #5FD068;">|</span>' if show_cursor else ''
        summary_html = self._escape_html(summary).replace(chr(10), '<br>') + cursor
        font_family = "Palatino, Georgia, 'Times New Roman', serif"

        return f'''
            <div style="margin-bottom: 12px; font-family: {font_family};">
                <span style="
                    color: {ACCENT_COLOR};
                    font-weight: bold;
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">Prompt:</span>
                <p style="
                    color: {TEXT_SECONDARY};
                    margin: 4px 0 8px 0;
                    font-style: italic;
                    font-family: {font_family};
                ">{self._escape_html(prompt)}</p>
            </div>
            <div style="font-family: {font_family};">
                <span style="
                    color: #5FD068;
                    font-weight: bold;
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">Summary:</span>
                <p style="
                    color: {TEXT_PRIMARY};
                    margin: 4px 0 0 0;
                    font-family: {font_family};
                ">{summary_html}</p>
            </div>
        '''

    def clear_history(self):
        """Clear all history entries."""
        self._history = []
        self.welcome_widget.show()
        self.summary_display.hide()

    def _format_ready_message(self) -> str:
        """Format the initial ready message."""
        return f'<p style="color: {TEXT_SECONDARY}; margin: 0;">Ready to compose.</p>'

    def _render_history(self):
        """Render the history as styled HTML."""
        if not self._history:
            # Show welcome screen, hide summary
            self.welcome_widget.show()
            self.summary_display.hide()
            return

        # Hide welcome screen, show summary
        self.welcome_widget.hide()
        self.summary_display.show()

        html_parts = []
        for i, (prompt, summary) in enumerate(self._history):
            # Add separator between entries (not before the first one)
            if i > 0:
                html_parts.append(f'''
                    <div style="border-top: 1px solid {BORDER_COLOR}; margin: 16px 0;"></div>
                ''')
            html_parts.append(self._format_entry_html(prompt, summary))

        full_html = f'''
            <div style="font-family: Palatino, Georgia, 'Times New Roman', serif; font-size: 13px;">
                {''.join(html_parts)}
            </div>
        '''
        self.summary_display.setHtml(full_html)
        # Scroll to bottom to show latest entry
        scrollbar = self.summary_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
        )

    def set_loading(self, is_loading: bool):
        """Call this to toggle the loading animation from external code."""
        self._is_loading = is_loading
        if is_loading:
            self.loading_section.show()
            self.music_loader.start()
            self.compose_btn.setEnabled(False)
            self.prompt_input.setEnabled(False)
        else:
            self.loading_section.hide()
            self.music_loader.stop()
            self.compose_btn.setEnabled(True)
            self.prompt_input.setEnabled(True)

    def get_prompt(self) -> str:
        """Returns the current prompt text."""
        return self.prompt_input.toPlainText()

    def clear_prompt(self):
        """Clears the prompt input field."""
        self.prompt_input.clear()

    # === Internal Methods ===

    def _handle_submit(self):
        """Handle the compose button click or Enter key."""
        prompt = self.get_prompt().strip()
        if not prompt:
            return

        # Show loading state
        self.set_loading(True)

        # Store prompt and clear input
        current_prompt = prompt
        self.clear_prompt()

        # Simulate async processing with QTimer (2 second delay)
        QTimer.singleShot(2000, lambda: self._process_complete(current_prompt))

    def _process_complete(self, prompt: str):
        """Called when processing is complete."""
        # Get the summary from the handler
        summary = self.on_prompt_submit(prompt)

        # Update UI
        self.set_loading(False)
        self.add_entry(prompt, summary)


def main():
    """Entry point for the Maestro application."""
    app = QApplication(sys.argv)

    # Set application-wide font (classical serif)
    font = QFont("Palatino", 11)
    if not font.exactMatch():
        font = QFont("Georgia", 11)
        if not font.exactMatch():
            font = QFont("Times New Roman", 11)
    app.setFont(font)

    window = MaestroWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
