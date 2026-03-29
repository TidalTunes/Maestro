# Examples

## Add Notes At The End Of A Phrase

```python
def apply_changes(score):
    flute = score.parts[0]
    score.measure(8)
    flute.note("quarter", "A5")
    flute.note("quarter", "G5")
```

## Add A Dynamic To Existing Material

```python
def apply_changes(score):
    violin = score.parts[0]
    score.measure(12)
    violin.dynamic("ff")
```

## Add A New Measure And Cadence

```python
def apply_changes(score):
    flute = score.parts[0]
    score.measure(9)
    flute.note("half", "D5")
    flute.note("half", "G5")
```

The runtime will emit an appended-measure bridge action automatically because the change plan extends past the current measure count.

## Add A New Part

```python
def apply_changes(score):
    drone = score.add_part("Drone", instrument="cello")
    score.measure(1)
    drone.note("whole", "C2")
```

This produces delta actions that append the new part and then write the requested notes into it.
