# Lightweight Humming Detector

This package stays standalone inside `Agent/detector` and exposes a single public API:

```python
from Agent.detector import transcribe_humming

result = transcribe_humming("my_hum.wav")
print(result)
```

The detector:

- loads audio as mono at 16 kHz
- trims leading/trailing silence
- applies light pre-emphasis and amplitude normalization
- tracks pitch with `librosa.pyin`
- suppresses fake notes with voiced-probability and RMS gating
- smooths vibrato with a short median filter
- segments notes on large pitch jumps or longer voiced gaps
- estimates coarse rhythm labels (`16th`, `eighth`, `quarter`, `half`, `whole`)

Output is newline-delimited text such as:

```text
A4, quarter
Bb4, eighth
C5, eighth
```

If no stable hummed notes are found, `transcribe_humming` returns an empty string.

## Install

```bash
python -m pip install -r Agent/detector/requirements.txt
```

## Manual Recorder

For a tiny popup recorder that sends microphone input directly into the detector:

```bash
python -m Agent.detector.humming_tester
```

It opens a small window with `Record` and `Stop`. Press `Record`, hum, press `Stop`, and the detected note string appears immediately in the window. You can repeat that loop as many times as you want.

## Run Tests

```bash
python -m unittest discover -s Agent/detector/tests
```
