# Lightweight Humming Detector

This package now lives under `packages/humming-detector` and exposes a single public API:

```python
from maestro_humming_detector import transcribe_humming

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

## Important Modules

- `src/maestro_humming_detector/api.py`: stable public entrypoint
- `src/maestro_humming_detector/_pipeline.py`: pitch tracking and note segmentation pipeline
- `src/maestro_humming_detector/humming_tester.py`: small recorder/test utility
- `tests/test_detector.py`: detector behavior tests
- `tests/test_humming_tester.py`: recorder-controller tests

## Boundaries

- Keep humming/audio analysis here.
- Do not put FastAPI endpoint logic here.
- Do not put OpenAI prompting logic here.
- The service should consume this package through its public API rather than reimplementing detector logic.

## Install

```bash
python -m pip install -e packages/humming-detector
```

## Manual Recorder

For a tiny popup recorder that sends microphone input directly into the detector:

```bash
python -m maestro_humming_detector.humming_tester
```

It opens a small window with `Record` and `Stop`. Press `Record`, hum, press `Stop`, and the detected note string appears immediately in the window. You can repeat that loop as many times as you want.

## Run Tests

```bash
python -m unittest discover -s packages/humming-detector/tests
```
