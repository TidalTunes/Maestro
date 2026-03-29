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

from app.agent import AgentError, GeneratedScoreCode, build_model_input
from app.config import Settings
from app.context import ReferenceLoadError, load_reference_corpus
from app.guard import CodeGuardError, validate_generated_code
from app.humming import HummingService
from app.main import app


def make_settings(root: Path, docs_dir: Path) -> Settings:
    return Settings(
        root_dir=root,
        maestro_docs_dir=docs_dir,
        openai_model="gpt-5.4",
        openai_reasoning_effort="low",
        openai_max_output_tokens=20000,
    )


class ReferenceLoaderTests(unittest.TestCase):
    def test_load_reference_corpus_uses_local_docs_only(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docs_dir = root / "docs"
            docs_dir.mkdir()

            (root / "README.md").write_text("repo readme", encoding="utf-8")
            (docs_dir / "getting-started.md").write_text("getting started", encoding="utf-8")
            (docs_dir / "api-reference.md").write_text("api ref", encoding="utf-8")
            (docs_dir / "examples.md").write_text("doc examples", encoding="utf-8")
            (docs_dir / "ignored.md").write_text("ignore me", encoding="utf-8")

            corpus = load_reference_corpus(make_settings(root, docs_dir))

        self.assertIn("repo readme", corpus)
        self.assertIn("getting started", corpus)
        self.assertNotIn("ignore me", corpus)

    def test_missing_required_reference_fails(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docs_dir = root / "docs"
            docs_dir.mkdir()
            (root / "README.md").write_text("repo readme", encoding="utf-8")
            with self.assertRaises(ReferenceLoadError):
                load_reference_corpus(make_settings(root, docs_dir))


class GuardTests(unittest.TestCase):
    def test_accepts_build_score_contract(self) -> None:
        validate_generated_code(
            "from maestroxml import Score\n"
            "def build_score():\n"
            "    score = Score(title='Etude')\n"
            "    part = score.add_part('Flute', instrument='flute')\n"
            "    score.measure(1)\n"
            "    part.note('quarter', 'C5')\n"
            "    return score\n"
        )

    def test_rejects_missing_build_score(self) -> None:
        with self.assertRaises(CodeGuardError):
            validate_generated_code(
                "from maestroxml import Score\n"
                "score = Score()\n"
            )

    def test_rejects_file_reads(self) -> None:
        with self.assertRaises(CodeGuardError):
            validate_generated_code(
                "from maestroxml import Score\n"
                "def build_score():\n"
                "    score = Score()\n"
                "    open('secret.txt').read()\n"
                "    return score\n"
            )

    def test_rejects_apply_calls(self) -> None:
        with self.assertRaises(CodeGuardError):
            validate_generated_code(
                "from maestroxml import Score\n"
                "def build_score():\n"
                "    score = Score()\n"
                "    score.apply()\n"
                "    return score\n"
            )

    def test_rejects_unsupported_duration_literals(self) -> None:
        with self.assertRaises(CodeGuardError):
            validate_generated_code(
                "from maestroxml import Score\n"
                "def build_score():\n"
                "    score = Score()\n"
                "    part = score.add_part('Flute', instrument='flute')\n"
                "    score.measure(1)\n"
                "    part.note('note', 'C5')\n"
                "    return score\n"
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


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.environ.pop("MAESTRO_DOCS_DIR", None)

    def test_generate_endpoint_returns_code_only(self) -> None:
        result = GeneratedScoreCode(
            python_code="from maestroxml import Score\n\ndef build_score():\n    return Score()\n",
        )
        with patch("app.main.agent_module.generate_score_code_from_prompt", return_value=result):
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
        self.assertEqual(set(payload), {"python_code"})
        self.assertIn("build_score", payload["python_code"])

    def test_generate_endpoint_returns_error_payload(self) -> None:
        with patch(
            "app.main.agent_module.generate_score_code_from_prompt",
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
        result = GeneratedScoreCode(
            python_code="from maestroxml import Score\n\ndef build_score():\n    return Score()\n",
        )
        with patch("app.main.agent_module.generate_score_code_from_prompt", return_value=result) as generate_mock:
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
