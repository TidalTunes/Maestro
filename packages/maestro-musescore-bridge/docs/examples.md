# Examples

## Minimal Ping + Note

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()
print(client.ping())

client.add_note(pitch="C4", duration="quarter", tick=0, staff=0, voice=0)
```

## Short Melody In One Batch

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()
batch = client.batch()

batch.append_measures(count=4)
batch.add_time_signature(numerator=4, denominator=4, tick=0, staff=0)
batch.add_key_signature(key="C", tick=0, staff=0)
batch.add_tempo(bpm=96, text="Andante", tick=0, staff=0)

notes = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"]
for i, pitch in enumerate(notes):
    batch.add_note(
        pitch=pitch,
        duration="quarter",
        tick=i * 480,
        staff=0,
        voice=0,
    )

result = client.apply_batch(batch)
print(result)
```

## Lyrics + Dynamics

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()
batch = client.batch()

batch.add_dynamic(text="mp", tick=0, staff=0)
batch.add_expression_text(text="dolce", tick=0, staff=0)
batch.write_lyrics(
    syllables=["la", "la", "la", "la"],
    tick=0,
    staff=0,
    voice=0,
    verse=0,
)

print(client.apply_batch(batch, fail_on_partial=False))
```

## Applying Raw Actions From File

`actions.json`:

```json
[
  {
    "kind": "add_note",
    "pitch": "C4",
    "duration": "quarter",
    "tick": 0,
    "staff": 0,
    "voice": 0
  },
  {
    "kind": "add_dynamic",
    "text": "mf",
    "tick": 0,
    "staff": 0
  }
]
```

Run:

```bash
maestro-musescore-bridge apply-json ./actions.json
```

## Error-Tolerant Execution (Partial Allowed)

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()

actions = [
    {"kind": "add_note", "pitch": "C4", "duration": "quarter", "tick": 0, "staff": 0, "voice": 0},
    {"kind": "add_harmony", "text": "Cmaj7", "tick": 0, "staff": 0},
]

result = client.apply_actions(actions, fail_on_partial=False)
print(result["all_ok"])   # False
print(result["results"])  # Per-action status entries
```

## Direct Command Mode (Advanced)

```python
from maestro_musescore_bridge import MuseScoreBridgeClient

client = MuseScoreBridgeClient()

commands = [
    {"op": "appendMeasures", "count": 2},
    {"op": "addNote", "pitch": "C4", "duration": "quarter", "tick": 0, "staffIdx": 0, "voice": 0},
]

print(client.apply_commands(commands))
```

Use direct commands only when action mapping is insufficient; action mode is preferred.
