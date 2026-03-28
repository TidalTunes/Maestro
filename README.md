# Maestro

AI Compose Assistant for MuseScore 4

A floating overlay GUI panel for AI-assisted music composition.

## Features

- Floating, always-on-top window that matches MuseScore 4's aesthetic
- Classical serif typography (Palatino/Georgia)
- Wavy text input effect
- Animated music staff loading indicator with rippling notes
- Typewriter effect for AI responses
- Draggable window with minimize/close controls

## Installation

```bash
pip install PyQt6
python maestro_gui.py
```

## Usage

1. Run the application
2. Type your composition request in the input field
3. Press Enter or click the arrow button to submit
4. Watch the music staff animation while processing
5. View the AI response in the summary area

## API

```python
# Override this method to connect your AI backend
def on_prompt_submit(self, prompt_text: str) -> str:
    # Your AI call here
    return summary_text

# Public methods
window.set_loading(True/False)  # Toggle loading animation
window.set_summary(text)        # Update summary display
window.get_prompt()             # Get current input text
window.clear_history()          # Clear conversation history
```

## License

MIT
