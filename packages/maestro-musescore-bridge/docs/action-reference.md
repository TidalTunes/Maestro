# Action Reference

This page documents the `kind` values accepted by `apply_actions()` and helper methods.

## Targeting Fields (Common)

Most actions support these target fields:

- `tick`: absolute tick position in score timeline
- `staff` or `staffIdx`: target staff index (0-based)
- `voice`: target voice index (0-based)

`staff` is translated to plugin command `staffIdx`.

## Duration Values

Where durations are used, valid names are:

- `whole`
- `half`
- `quarter`
- `eighth`
- `16th`
- `32nd`
- `64th`

Optional `dots` may be used for dotted durations.

## Supported Actions

### Notes / Rests / Sequences

- `add_note`
  - fields: `pitch`, `duration`, optional `dots`, `tick`, `staff`, `voice`
- `add_chord`
  - fields: `pitches` (array), `duration`, optional `dots`, `tick`, `staff`, `voice`
- `add_rest`
  - fields: `duration`, optional `dots`, `tick`, `staff`, `voice`
- `write_sequence`
  - fields: `events`, optional `tick`, optional `measure`, optional `staff`, optional `voice`
  - event shapes:
    - note: `{ "pitch": "C4", "duration": "quarter", "dots": 0 }`
    - chord: `{ "pitches": ["C4", "E4", "G4"], "duration": "half" }`
    - rest: `{ "type": "rest", "duration": "quarter" }`

### Element Modification

- `modify_note`
  - fields: `tick`, `staff`, `voice`, optional `noteIndex`
  - optional property fields: `tpc`, `tpc1`, `tpc2`, `veloOffset`, `tuning`, `small`, `ghost`, `play`, `headGroup`, `headType`, `accidentalType`
- `modify_chord`
  - fields: `tick`, `staff`, `voice`
  - optional property fields: `stemDirection`, `noStem`, `beamMode`, `small`, `staffMove`
- `modify_measure`
  - fields: `tick`
  - optional property fields: `repeatCount`, `userStretch`, `irregular`

### Score Structure / Metadata

- `append_measures`
  - fields: `count`
- `add_part`
  - fields: one of `instrumentId`, `musicXmlId`, or `instrumentName`
- `set_header_text`
  - fields: `type`, `text`
- `set_meta_tag`
  - fields: `tag`, `value`

### Signatures / Tempo / Clef

- `add_time_signature`
  - fields: `numerator`, `denominator`, `tick`, optional `staff`
- `add_key_signature`
  - fields: `key`, `tick`, optional `staff`, optional `all_staves`
  - `key` may be numeric fifths or key name string (`C`, `G`, `Bb`, etc.)
  - when `all_staves` is true, the bridge applies the key signature across every staff in the score
- `add_clef`
  - fields: `tick`, optional `staff`, optional `clefType`
- `add_tempo`
  - fields: `bpm`, optional `text`, `tick`, optional `staff`

### Dynamics / Articulation / Symbols

- `add_dynamic`
  - fields: `text`, `tick`, optional `staff`
- `add_articulation`
  - fields: `tick`, optional `staff`, optional `voice`, optional `symbol`, optional `direction`
- `add_fermata`
  - fields: `tick`, optional `staff`, optional `voice`
- `add_arpeggio`
  - fields: `tick`, optional `staff`, optional `voice`, optional `subtype`
- `add_breath`
  - fields: `tick`, optional `staff`
- `add_tuplet`
  - fields: `tick`, optional `staff`, optional `voice`, optional `actual`, optional `normal`, optional `totalDuration`

### Text / Lyrics

- `add_staff_text`
  - fields: `text`, `tick`, optional `staff`, optional `fontSize`, optional `fontFace`, optional `placement`
- `add_system_text`
  - fields: `text`, `tick`
- `add_rehearsal_mark`
  - fields: `text`, `tick`, optional `staff`
- `add_expression_text`
  - fields: `text`, `tick`, optional `staff`
- `add_lyrics`
  - fields: `text`, `tick`, optional `staff`, optional `voice`, optional `verse`
- `write_lyrics`
  - fields: `syllables` (array), `tick`, optional `staff`, optional `voice`, optional `verse`
- `add_fingering`
  - fields: `text`, `tick`, optional `staff`, optional `voice`
- `add_harmony`
  - fields: `text`, `tick`, optional `staff`
  - current behavior: intentionally blocked and returns safe error

### Layout

- `add_layout_break`
  - fields: `tick`, optional `breakType`
  - `breakType`: `0` line, `1` page, `2` section
- `add_spacer`
  - fields: `tick`, optional `staff`, optional `space`

## Error Behavior

- Invalid action kind raises Python `ValueError` before request is sent.
- Plugin-side failures appear per-action in `results`.
- If request-level `ok=false`, Python raises `BridgeResponseError` unless `fail_on_partial=False` was used and plugin returns `ok=true`.
