from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import sys
import unittest

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[3]
for extra in (
    ROOT / "apps" / "service" / "src",
    ROOT / "packages" / "agent-core" / "src",
    ROOT / "packages" / "humming-detector" / "src",
    ROOT / "packages" / "maestroxml" / "src",
):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from maestro_agent_core import GeneratedMusicXML
from maestro_service.api.app import app


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_generate_endpoint_returns_code_and_musicxml(self) -> None:
        result = GeneratedMusicXML(
            filename="test_piece.musicxml",
            python_code="from maestroxml import Score\n\ndef build_score(output_path):\n    pass\n",
            musicxml="<score-partwise version='4.0'/>",
        )
        with patch("maestro_service.api.app.generator_module.generate_musicxml_from_prompt", return_value=result):
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
        from maestro_agent_core import AgentError

        with patch(
            "maestro_service.api.app.generator_module.generate_musicxml_from_prompt",
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
        with patch("maestro_service.api.app.generator_module.generate_musicxml_from_prompt", return_value=result) as generate_mock:
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
        with patch("maestro_service.api.app.humming_service.start_recording") as start_mock:
            response = self.client.post("/api/humming/start")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Recording... hum, then press Stop.")
        start_mock.assert_called_once_with()

    def test_humming_stop_endpoint_returns_notes(self) -> None:
        with patch("maestro_service.api.app.humming_service.stop_recording", return_value="A4, quarter"):
            response = self.client.post("/api/humming/stop")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["hummed_notes"], "A4, quarter")


if __name__ == "__main__":
    unittest.main()
