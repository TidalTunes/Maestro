from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from maestroxml import Score, musicxml_string_to_python, musicxml_to_python


class MaestroXMLTests(unittest.TestCase):
    def golden(self, name: str) -> str:
        return (ROOT / "tests" / "golden" / name).read_text(encoding="utf-8")

    def parse(self, xml_text: str) -> ET.Element:
        return ET.fromstring(xml_text.split("\n", 2)[2])

    def exec_generated(self, code: str) -> Score:
        namespace: dict[str, object] = {}
        exec(code, namespace)
        score = namespace.get("score")
        self.assertIsInstance(score, Score)
        return score

    def test_hello_world_score_matches_golden(self) -> None:
        score = Score(title="Hello World", composer="Composer")
        flute = score.add_part("Flute", instrument="flute")

        score.measure(1)
        score.time_signature("4/4")
        score.key_signature("C major")
        flute.tempo(96, text="Brightly")
        flute.notes("quarter", ["C5", "D5", "E5", "F5"])

        actual = score.to_string()
        self.assertMultiLineEqual(actual, self.golden("hello_world.musicxml"))

        root = self.parse(actual)
        self.assertEqual(root.findtext("./part-list/score-part/part-name"), "Flute")
        self.assertEqual(root.findtext("./part/measure/attributes/time/beats"), "4")
        self.assertEqual(len(root.findall(".//measure")), 1)

    def test_string_quartet_workflow_matches_golden(self) -> None:
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

        actual = score.to_string()
        self.assertMultiLineEqual(actual, self.golden("quartet.musicxml"))

        root = self.parse(actual)
        measures = root.findall("./part[@id='P1']/measure")
        self.assertEqual([measure.attrib["number"] for measure in measures], [str(i) for i in range(1, 9)])
        self.assertEqual(len(root.findall("./part[@id='P2']/measure")), 8)

    def test_piano_multistaff_uses_backup(self) -> None:
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

        actual = score.to_string()
        self.assertMultiLineEqual(actual, self.golden("piano_backup.musicxml"))

        root = self.parse(actual)
        self.assertEqual(root.findtext(".//backup/duration"), "4")
        self.assertEqual(root.findtext(".//attributes/staves"), "2")
        self.assertEqual(len(root.findall(".//note/staff")), 2)

    def test_notations_and_directions_match_golden(self) -> None:
        score = Score(title="Notation Study")
        violin = score.add_part("Violin", instrument="violin")

        score.measure(1)
        score.time_signature("3/4")
        score.key_signature("D major")
        violin.tempo(72, text="Adagio")
        violin.dynamic("mp")
        violin.text("dolce")
        violin.note("quarter", "A4", tie="start", slur="start", articulations=["staccato"])
        violin.note("quarter", "B4")
        violin.note("quarter", "C#5")

        score.measure(2)
        violin.note("quarter", "A4", tie="stop", slur="stop", articulations=["accent"])
        violin.rest("quarter")
        violin.chord("quarter", ["D5", "F#5", "A5"])

        actual = score.to_string()
        self.assertMultiLineEqual(actual, self.golden("notations.musicxml"))

        root = self.parse(actual)
        self.assertIsNotNone(root.find(".//direction/direction-type/metronome"))
        self.assertEqual(len(root.findall(".//notations/slur")), 2)
        self.assertEqual(len(root.findall(".//notations/tied")), 2)

    def test_repeats_and_endings_match_golden(self) -> None:
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

        actual = score.to_string()
        self.assertMultiLineEqual(actual, self.golden("repeats.musicxml"))

        root = self.parse(actual)
        self.assertEqual(root.find("./part/measure/barline/repeat").attrib["direction"], "forward")
        endings = root.findall(".//ending")
        self.assertEqual([ending.attrib["number"] for ending in endings], ["1", "1", "2", "2"])

    def test_write_matches_to_string(self) -> None:
        score = Score(title="Write Test")
        flute = score.add_part("Flute", instrument="flute")
        score.measure(1)
        score.time_signature("4/4")
        flute.note("whole", "C5")

        expected = score.to_string()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "write_test.musicxml"
            returned = score.write(path)
            self.assertEqual(returned, path)
            self.assertEqual(path.read_text(encoding="utf-8"), expected)

    def test_pitch_key_and_duration_math(self) -> None:
        score = Score(title="Math Test")
        flute = score.add_part("Flute", instrument="flute")
        score.measure(1)
        score.time_signature("4/4")
        score.key_signature("A minor")
        flute.note("quarter", "F#5", dots=1)
        flute.note("eighth", "Bb4", tuplet=(3, 2))
        flute.note("eighth", "C5", tuplet=(3, 2))
        flute.note("eighth", "D5", tuplet=(3, 2))

        root = self.parse(score.to_string())
        self.assertEqual(root.findtext(".//key/fifths"), "0")
        self.assertEqual(root.findtext(".//key/mode"), "minor")
        self.assertEqual(root.findtext(".//divisions"), "6")

        notes = root.findall(".//note")
        self.assertEqual(notes[0].findtext("pitch/alter"), "1")
        self.assertEqual(notes[0].findtext("duration"), "9")
        self.assertEqual(notes[1].findtext("pitch/alter"), "-1")
        self.assertEqual([note.findtext("duration") for note in notes[1:]], ["2", "2", "2"])
        self.assertEqual(notes[1].findtext("time-modification/actual-notes"), "3")
        self.assertEqual(notes[1].findtext("time-modification/normal-notes"), "2")

    def test_musicxml_string_to_python_round_trips_hello_world(self) -> None:
        xml_text = self.golden("hello_world.musicxml")
        code = musicxml_string_to_python(xml_text)

        self.assertIn("from maestroxml import Score", code)
        self.assertIn("flute = score.add_part(", code)
        self.assertIn('instrument="flute"', code)
        self.assertIn('score.time_signature("4/4")', code)

        score = self.exec_generated(code)
        self.assertEqual(score.to_string(), xml_text)

    def test_musicxml_string_to_python_round_trips_multistaff_and_repeats(self) -> None:
        for fixture_name in ("piano_backup.musicxml", "repeats.musicxml", "notations.musicxml"):
            with self.subTest(fixture=fixture_name):
                xml_text = self.golden(fixture_name)
                code = musicxml_string_to_python(xml_text)
                score = self.exec_generated(code)
                self.assertEqual(score.to_string(), xml_text)

    def test_musicxml_to_python_reads_path(self) -> None:
        xml_text = self.golden("quartet.musicxml")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quartet.musicxml"
            path.write_text(xml_text, encoding="utf-8")
            code = musicxml_to_python(path)

        self.assertIn("score = Score(", code)
        self.assertIn('score.measure(8)', code)
        score = self.exec_generated(code)
        self.assertEqual(score.to_string(), xml_text)

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
        root = self.parse(score.to_string())
        self.assertEqual(root.findtext(".//note/pitch/step"), "C")
        self.assertIsNone(root.find(".//lyric"))


if __name__ == "__main__":
    unittest.main()
