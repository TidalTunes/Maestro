from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import sys
import unittest

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.agent import (
    AgentError,
    GeneratedMusicXML,
    build_model_input,
    execute_generated_code,
    sanitize_filename_stem,
)
from app.config import Settings
from app.context import ReferenceLoadError, load_reference_corpus
from app.guard import CodeGuardError, validate_generated_code
from app.humming import HummingService
from app.main import app


def make_settings(root: Path, skill_dir: Path, docs_dir: Path) -> Settings:
    return Settings(
        root_dir=root,
        maestro_skill_dir=skill_dir,
        maestro_docs_dir=docs_dir,
        openai_model="gpt-5.4",
        openai_reasoning_effort="low",
        openai_max_output_tokens=20000,
        execution_timeout_seconds=10,
    )


class ReferenceLoaderTests(unittest.TestCase):
    def test_load_reference_corpus_uses_curated_files(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docs_dir = root / "docs"
            skill_dir = root / "skill"
            references_dir = skill_dir / "references"
            docs_dir.mkdir()
            references_dir.mkdir(parents=True)

            (root / "README.md").write_text("repo readme", encoding="utf-8")
            (docs_dir / "getting-started.md").write_text("getting started", encoding="utf-8")
            (docs_dir / "api-reference.md").write_text("api ref", encoding="utf-8")
            (docs_dir / "examples.md").write_text("doc examples", encoding="utf-8")
            (docs_dir / "ignored.md").write_text("ignore me", encoding="utf-8")
            (skill_dir / "SKILL.md").write_text("skill body", encoding="utf-8")
            (references_dir / "api-patterns.md").write_text("skill api", encoding="utf-8")
            (references_dir / "examples.md").write_text("skill examples", encoding="utf-8")
            (skill_dir / "agents").mkdir()
            (skill_dir / "agents" / "openai.yaml").write_text("unused", encoding="utf-8")

            corpus = load_reference_corpus(make_settings(root, skill_dir, docs_dir))

        self.assertIn("repo readme", corpus)
        self.assertIn("getting started", corpus)
        self.assertIn("skill api", corpus)
        self.assertNotIn("ignore me", corpus)
        self.assertNotIn("unused", corpus)

    def test_missing_required_reference_fails(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docs_dir = root / "docs"
            skill_dir = root / "skill"
            docs_dir.mkdir()
            skill_dir.mkdir()
            (root / "README.md").write_text("repo readme", encoding="utf-8")
            with self.assertRaises(ReferenceLoadError):
                load_reference_corpus(make_settings(root, skill_dir, docs_dir))


class GuardTests(unittest.TestCase):
    def test_accepts_build_score_contract(self) -> None:
        validate_generated_code(
            "from maestroxml import Score\n"
            "def build_score(output_path):\n"
            "    score = Score(title='Etude')\n"
            "    part = score.add_part('Flute', instrument='flute')\n"
            "    score.measure(1)\n"
            "    part.note('quarter', 'C5')\n"
            "    score.write(output_path)\n"
        )

    def test_rejects_missing_build_score(self) -> None:
        with self.assertRaises(CodeGuardError):
            validate_generated_code(
                "from maestroxml import Score\n"
                "score = Score()\n"
                "score.write('out.musicxml')\n"
            )

    def test_rejects_file_reads(self) -> None:
        with self.assertRaises(CodeGuardError):
            validate_generated_code(
                "from pathlib import Path\n"
                "from maestroxml import Score\n"
                "def build_score(output_path):\n"
                "    Path('secret.txt').read_text()\n"
                "    score = Score()\n"
                "    score.write(output_path)\n"
            )

    def test_rejects_unsupported_duration_literals(self) -> None:
        with self.assertRaises(CodeGuardError):
            validate_generated_code(
                "from maestroxml import Score\n"
                "def build_score(output_path):\n"
                "    score = Score()\n"
                "    part = score.add_part('Flute', instrument='flute')\n"
                "    score.measure(1)\n"
                "    part.note('note', 'C5')\n"
                "    score.write(output_path)\n"
            )


class PromptInputTests(unittest.TestCase):
    def test_build_model_input_appends_hummed_notes_context(self) -> None:
        payload = build_model_input("write a short prelude", "A4, quarter\nB4, quarter")

        self.assertIn("write a short prelude", payload)
        self.assertIn("The user hummed the following notes into the microphone.", payload)
        self.assertIn("A4, quarter\nB4, quarter", payload)

    def test_build_model_input_requires_prompt(self) -> None:
        with self.assertRaises(AgentError):
            build_model_input("   ", "A4, quarter")


class ExecutionTests(unittest.TestCase):
    def test_execute_generated_code_runs_with_fake_maestroxml(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            src_dir = root / "src" / "maestroxml"
            docs_dir = root / "docs"
            skill_dir = root / "skill"
            src_dir.mkdir(parents=True)
            docs_dir.mkdir()
            skill_dir.mkdir()
            (root / "README.md").write_text("repo readme", encoding="utf-8")
            (docs_dir / "getting-started.md").write_text("getting started", encoding="utf-8")
            (docs_dir / "api-reference.md").write_text("api ref", encoding="utf-8")
            (docs_dir / "examples.md").write_text("doc examples", encoding="utf-8")
            (skill_dir / "SKILL.md").write_text("skill body", encoding="utf-8")
            references_dir = skill_dir / "references"
            references_dir.mkdir()
            (references_dir / "api-patterns.md").write_text("skill api", encoding="utf-8")
            (references_dir / "examples.md").write_text("skill examples", encoding="utf-8")
            (src_dir / "__init__.py").write_text(
                "class Score:\n"
                "    def __init__(self, *args, **kwargs):\n"
                "        pass\n"
                "    def add_part(self, *args, **kwargs):\n"
                "        return self\n"
                "    def measure(self, *args, **kwargs):\n"
                "        return self\n"
                "    def note(self, *args, **kwargs):\n"
                "        pass\n"
                "    def write(self, path):\n"
                "        from pathlib import Path\n"
                "        Path(path).write_text('<score-partwise/>', encoding='utf-8')\n",
                encoding="utf-8",
            )

            filename, musicxml = execute_generated_code(
                "from maestroxml import Score\n"
                "def build_score(output_path):\n"
                "    score = Score()\n"
                "    part = score.add_part('Flute', instrument='flute')\n"
                "    score.measure(1)\n"
                "    part.note('quarter', 'C5')\n"
                "    score.write(output_path)\n",
                sanitize_filename_stem("Flute solo"),
                make_settings(root, skill_dir, docs_dir),
            )

        self.assertEqual(filename, "flute_solo.musicxml")
        self.assertEqual(musicxml, "<score-partwise/>")


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        for key in ["MAESTRO_SKILL_DIR", "MAESTRO_SKILL_PATH", "MAESTRO_DOCS_DIR"]:
            os.environ.pop(key, None)

    def test_generate_endpoint_returns_code_and_musicxml(self) -> None:
        result = GeneratedMusicXML(
            filename="test_piece.musicxml",
            python_code="from maestroxml import Score\n\ndef build_score(output_path):\n    pass\n",
            musicxml="<score-partwise version='4.0'/>",
        )
        with patch("app.main.agent_module.generate_musicxml_from_prompt", return_value=result):
            response = self.client.post(
                "/api/generate",
                json={
                    "api_key": "sk-test",
                    "prompt": "write a flute solo",
                    "hummed_notes": "A4, quarter",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filename"], "test_piece.musicxml")
        self.assertIn("build_score", payload["python_code"])
        self.assertIn("<score-partwise", payload["musicxml"])

    def test_generate_endpoint_returns_error_payload(self) -> None:
        with patch(
            "app.main.agent_module.generate_musicxml_from_prompt",
            side_effect=AgentError("validation failed", "bad code"),
        ):
            response = self.client.post(
                "/api/generate",
                json={"api_key": "sk-test", "prompt": "write a flute solo"},
            )

        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["error"], "validation failed")
        self.assertEqual(payload["python_code"], "bad code")

    def test_generate_endpoint_forwards_hummed_notes(self) -> None:
        result = GeneratedMusicXML(
            filename="test_piece.musicxml",
            python_code="from maestroxml import Score\n\ndef build_score(output_path):\n    pass\n",
            musicxml="<score-partwise version='4.0'/>",
        )
        with patch("app.main.agent_module.generate_musicxml_from_prompt", return_value=result) as generate_mock:
            response = self.client.post(
                "/api/generate",
                json={
                    "api_key": "sk-test",
                    "prompt": "write a flute solo",
                    "hummed_notes": "A4, quarter",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(generate_mock.call_args.args[3], "A4, quarter")

    def test_humming_start_endpoint_starts_recording(self) -> None:
        with patch("app.main.humming_service.start_recording") as start_mock:
            response = self.client.post("/api/humming/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Recording... hum, then press Stop.")
        start_mock.assert_called_once_with()

    def test_humming_stop_endpoint_returns_detected_notes(self) -> None:
        with patch("app.main.humming_service.stop_recording", return_value="A4, quarter") as stop_mock:
            response = self.client.post("/api/humming/stop")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hummed_notes"], "A4, quarter")
        stop_mock.assert_called_once_with()


class FakeController:
    def __init__(self) -> None:
        self.is_recording = False

    def start_recording(self) -> None:
        self.is_recording = True

    def stop_recording(self) -> str:
        self.is_recording = False
        return "C4, quarter"


class HummingServiceTests(unittest.TestCase):
    def test_service_round_trip_stores_last_notes(self) -> None:
        service = HummingService(controller_factory=FakeController)

        service.start_recording()
        notes = service.stop_recording()

        self.assertEqual(notes, "C4, quarter")
        self.assertEqual(service.last_notes, "C4, quarter")
        self.assertFalse(service.is_recording)


if __name__ == "__main__":
    unittest.main()
