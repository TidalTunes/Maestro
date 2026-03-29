from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maestroxml import Score, musicxml_string_to_python, musicxml_to_python


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[list[dict[str, object]], bool]] = []

    def apply_actions(
        self, actions: list[dict[str, object]], *, fail_on_partial: bool = True
    ) -> dict[str, object]:
        self.calls.append((actions, fail_on_partial))
        return {
            "command_count": len(actions),
            "all_ok": True,
            "results": [{"ok": True} for _ in actions],
        }


class MaestroXMLTests(unittest.TestCase):
    def golden(self, name: str) -> str:
        return (ROOT / "tests" / "golden" / name).read_text(encoding="utf-8")

    def exec_generated(self, code: str) -> Score:
        namespace: dict[str, object] = {}
        exec(code, namespace)
        score = namespace.get("score")
        self.assertIsInstance(score, Score)
        return score

    def build_hello_world(self) -> Score:
        score = Score(title="Hello World", composer="Composer")
        flute = score.add_part("Flute", instrument="flute")
        score.measure(1)
        score.time_signature("4/4")
        score.key_signature("C major")
        flute.tempo(96, text="Brightly")
        flute.notes("quarter", ["C5", "D5", "E5", "F5"])
        return score

    def build_quartet(self) -> Score:
        score = Score(title="My Piece", composer="Me")
        violin1 = score.add_part("Violin I", instrument="violin")
        violin2 = score.add_part("Violin II", instrument="violin")
        viola = score.add_part("Viola", instrument="viola")
        cello = score.add_part("Cello", instrument="cello")

        score.measure(1)
        score.time_signature("4/4")
        score.key_signature("C major")
        violin1.notes("quarter", ["C4", "E4", "G4"])
        violin1.notes("eighth", ["A4", "B4"])
        violin1.rest("quarter")

        score.measure(2)
        violin1.note("whole", "C5")

        chord = ["G3", "B4", "D5"]
        for number in range(3, 9):
            score.measure(number)
            cello.note("whole", chord[0])
            viola.note("whole", chord[1])
            violin2.note("whole", chord[2])

        return score

    def build_piano(self) -> Score:
        score = Score(title="Piano Sketch")
        piano = score.add_part("Piano", instrument="piano")

        score.measure(1)
        score.time_signature("4/4")
        score.key_signature("G major")

        right = piano.voice(1, staff=1)
        left = piano.voice(1, staff=2)

        right.notes("quarter", ["G4", "A4", "B4", "D5"])
        left.note("half", "G2")
        left.note("half", "D3")
        return score

    def build_notations(self) -> Score:
        score = Score(title="Notation Study")
        violin = score.add_part("Violin", instrument="violin")

        score.measure(1)
        score.time_signature("3/4")
        score.key_signature("D major")
        violin.tempo(72, text="Adagio")
        violin.dynamic("mp")
        violin.text("dolce")
        violin.note(
            "quarter",
            "A4",
            tie="start",
            slur="start",
            articulations=["staccato"],
        )
        violin.note("quarter", "B4")
        violin.note("quarter", "C#5")

        score.measure(2)
        violin.note(
            "quarter",
            "A4",
            tie="stop",
            slur="stop",
            articulations=["accent"],
        )
        violin.rest("quarter")
        violin.chord("quarter", ["D5", "F#5", "A5"])
        return score

    def build_repeats(self) -> Score:
        score = Score(title="Repeat Study")
        flute = score.add_part("Flute", instrument="flute")

        score.measure(1)
        score.time_signature("2/4")
        flute.repeat_start()
        flute.notes("quarter", ["C5", "D5"])

        score.measure(2)
        flute.ending(1, "start")
        flute.notes("quarter", ["E5", "F5"])

        score.measure(3)
        flute.ending(1, "stop")
        flute.repeat_end(times=2)
        flute.notes("quarter", ["G5", "A5"])

        score.measure(4)
        flute.ending(2, "start")
        flute.notes("quarter", ["B5", "C6"])

        score.measure(5)
        flute.ending(2, "stop")
        flute.notes("quarter", ["D6", "E6"])
        return score

    def build_duration_math(self) -> Score:
        score = Score(title="Math Test")
        flute = score.add_part("Flute", instrument="flute")
        score.measure(1)
        score.time_signature("4/4")
        score.key_signature("A minor")
        flute.note("quarter", "F#5", dots=1)
        flute.note("eighth", "Bb4", tuplet=(3, 2))
        flute.note("eighth", "C5", tuplet=(3, 2))
        flute.note("eighth", "D5", tuplet=(3, 2))
        return score

    def test_hello_world_score_maps_to_bridge_actions(self) -> None:
        score = self.build_hello_world()

        self.assertEqual(
            score.to_actions(),
            [
                {"kind": "set_header_text", "type": "title", "text": "Hello World"},
                {"kind": "set_header_text", "type": "composer", "text": "Composer"},
                {"kind": "set_meta_tag", "tag": "composer", "value": "Composer"},
                {
                    "kind": "add_time_signature",
                    "numerator": 4,
                    "denominator": 4,
                    "tick": 0,
                    "staff": 0,
                },
                {"kind": "add_key_signature", "key": 0, "tick": 0, "staff": 0},
                {
                    "kind": "add_tempo",
                    "bpm": 96,
                    "text": "Brightly",
                    "tick": 0,
                    "staff": 0,
                },
                {
                    "kind": "add_note",
                    "pitch": "C5",
                    "duration": "quarter",
                    "tick": 0,
                    "staff": 0,
                    "voice": 0,
                },
                {
                    "kind": "add_note",
                    "pitch": "D5",
                    "duration": "quarter",
                    "tick": 480,
                    "staff": 0,
                    "voice": 0,
                },
                {
                    "kind": "add_note",
                    "pitch": "E5",
                    "duration": "quarter",
                    "tick": 960,
                    "staff": 0,
                    "voice": 0,
                },
                {
                    "kind": "add_note",
                    "pitch": "F5",
                    "duration": "quarter",
                    "tick": 1440,
                    "staff": 0,
                    "voice": 0,
                },
            ],
        )
        self.assertEqual(score.unsupported_features(), [])

    def test_string_quartet_actions_include_structure_and_staff_routing(self) -> None:
        score = self.build_quartet()
        actions = score.to_actions()

        add_part_actions = [action for action in actions if action["kind"] == "add_part"]
        self.assertEqual(
            add_part_actions,
            [
                {"kind": "add_part", "instrumentId": "violin"},
                {"kind": "add_part", "instrumentId": "viola"},
                {"kind": "add_part", "instrumentId": "violoncello"},
            ],
        )
        self.assertIn({"kind": "append_measures", "count": 7}, actions)

        note_actions = [action for action in actions if action["kind"] == "add_note"]
        self.assertIn(
            {
                "kind": "add_note",
                "pitch": "G3",
                "duration": "whole",
                "tick": 3840,
                "staff": 3,
                "voice": 0,
            },
            note_actions,
        )
        self.assertIn(
            {
                "kind": "add_note",
                "pitch": "D5",
                "duration": "whole",
                "tick": 3840,
                "staff": 1,
                "voice": 0,
            },
            note_actions,
        )

    def test_piano_multistaff_routes_left_hand_to_second_staff(self) -> None:
        score = self.build_piano()
        note_actions = [action for action in score.to_actions() if action["kind"] == "add_note"]

        self.assertIn(
            {
                "kind": "add_note",
                "pitch": "G2",
                "duration": "half",
                "tick": 0,
                "staff": 1,
                "voice": 0,
            },
            note_actions,
        )
        self.assertIn(
            {
                "kind": "add_note",
                "pitch": "D3",
                "duration": "half",
                "tick": 960,
                "staff": 1,
                "voice": 0,
            },
            note_actions,
        )

    def test_notations_map_supported_marks_and_report_unsupported_spanners(self) -> None:
        score = self.build_notations()
        actions = score.to_actions()

        self.assertEqual(score.unsupported_features(), ["slurs", "ties"])
        self.assertIn(
            {"kind": "add_dynamic", "text": "mp", "tick": 0, "staff": 0},
            actions,
        )
        self.assertIn(
            {"kind": "add_staff_text", "text": "dolce", "tick": 0, "staff": 0},
            actions,
        )
        self.assertIn(
            {
                "kind": "add_articulation",
                "tick": 0,
                "staff": 0,
                "voice": 0,
                "symbol": "articStaccatoAbove",
            },
            actions,
        )
        self.assertIn(
            {
                "kind": "add_chord",
                "pitches": ["D5", "F#5", "A5"],
                "duration": "quarter",
                "tick": 2400,
                "staff": 0,
                "voice": 0,
            },
            actions,
        )

    def test_repeats_are_reported_and_keep_repeat_count_hint(self) -> None:
        score = self.build_repeats()
        actions = score.to_actions()

        self.assertEqual(
            score.unsupported_features(),
            ["repeat end barlines", "repeat start barlines", "volta endings"],
        )
        self.assertIn(
            {"kind": "modify_measure", "tick": 1920, "repeatCount": 2},
            actions,
        )

    def test_write_matches_to_string(self) -> None:
        score = self.build_hello_world()
        expected = score.to_string()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "write_test.json"
            returned = score.write(path)
            self.assertEqual(returned, path)
            self.assertEqual(path.read_text(encoding="utf-8"), expected)
            self.assertIsInstance(json.loads(expected), list)

    def test_apply_uses_client_with_generated_actions(self) -> None:
        score = self.build_hello_world()
        client = FakeClient()

        result = score.apply(client)

        self.assertEqual(result["command_count"], len(score.to_actions()))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][0], score.to_actions())
        self.assertTrue(client.calls[0][1])

    def test_pitch_key_and_duration_math(self) -> None:
        score = self.build_duration_math()
        actions = score.to_actions()

        self.assertIn(
            {"kind": "add_key_signature", "key": 0, "tick": 0, "staff": 0},
            actions,
        )
        self.assertIn(
            {
                "kind": "add_note",
                "pitch": "F#5",
                "duration": "quarter",
                "dots": 1,
                "tick": 0,
                "staff": 0,
                "voice": 0,
            },
            actions,
        )
        self.assertIn(
            {
                "kind": "add_tuplet",
                "tick": 720,
                "staff": 0,
                "voice": 0,
                "actual": 3,
                "normal": 2,
                "totalDuration": "quarter",
            },
            actions,
        )
        self.assertIn(
            {
                "kind": "add_note",
                "pitch": "Bb4",
                "duration": "eighth",
                "tick": 720,
                "staff": 0,
                "voice": 0,
            },
            actions,
        )
        self.assertIn(
            {
                "kind": "add_note",
                "pitch": "D5",
                "duration": "eighth",
                "tick": 1040,
                "staff": 0,
                "voice": 0,
            },
            actions,
        )

    def test_musicxml_string_to_python_recreates_hello_world_builder(self) -> None:
        xml_text = self.golden("hello_world.musicxml")
        code = musicxml_string_to_python(xml_text)

        self.assertIn("from maestroxml import Score", code)
        self.assertIn("flute = score.add_part(", code)
        self.assertIn('instrument="flute"', code)
        self.assertIn('score.time_signature("4/4")', code)

        score = self.exec_generated(code)
        self.assertEqual(score.to_actions(), self.build_hello_world().to_actions())

    def test_musicxml_string_to_python_recreates_multistaff_and_repeats_builder(self) -> None:
        fixtures = {
            "piano_backup.musicxml": self.build_piano,
            "repeats.musicxml": self.build_repeats,
            "notations.musicxml": self.build_notations,
        }
        for fixture_name, builder in fixtures.items():
            with self.subTest(fixture=fixture_name):
                code = musicxml_string_to_python(self.golden(fixture_name))
                score = self.exec_generated(code)
                self.assertEqual(score.to_actions(), builder().to_actions())

    def test_musicxml_to_python_reads_path(self) -> None:
        xml_text = self.golden("quartet.musicxml")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quartet.musicxml"
            path.write_text(xml_text, encoding="utf-8")
            code = musicxml_to_python(path)

        self.assertIn("score = Score(", code)
        self.assertIn("score.measure(8)", code)

        score = self.exec_generated(code)
        self.assertEqual(score.to_actions(), self.build_quartet().to_actions())

    def test_musicxml_to_python_ignores_unsupported_elements(self) -> None:
        xml_text = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0">
  <part-list>
    <score-part id="P1">
      <part-name>Flute</part-name>
      <score-instrument id="P1-I1">
        <instrument-name>Flute</instrument-name>
      </score-instrument>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>1</divisions>
        <time>
          <beats>4</beats>
          <beat-type>4</beat-type>
        </time>
        <key>
          <fifths>0</fifths>
          <mode>major</mode>
        </key>
        <clef>
          <sign>G</sign>
          <line>2</line>
        </clef>
      </attributes>
      <harmony>
        <root>
          <root-step>C</root-step>
        </root>
      </harmony>
      <note>
        <pitch>
          <step>C</step>
          <octave>5</octave>
        </pitch>
        <duration>4</duration>
        <voice>1</voice>
        <type>whole</type>
        <lyric>
          <text>la</text>
        </lyric>
      </note>
    </measure>
  </part>
</score-partwise>
"""
        code = musicxml_string_to_python(xml_text)

        self.assertNotIn("harmony", code)
        self.assertNotIn("lyric", code)

        score = self.exec_generated(code)
        self.assertEqual(
            score.to_actions(),
            [
                {
                    "kind": "add_time_signature",
                    "numerator": 4,
                    "denominator": 4,
                    "tick": 0,
                    "staff": 0,
                },
                {"kind": "add_key_signature", "key": 0, "tick": 0, "staff": 0},
                {
                    "kind": "add_note",
                    "pitch": "C5",
                    "duration": "whole",
                    "tick": 0,
                    "staff": 0,
                    "voice": 0,
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
