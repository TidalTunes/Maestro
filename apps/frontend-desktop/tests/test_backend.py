from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import os
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "apps" / "frontend-desktop" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from maestro_desktop import backend


class _FakeResponses:
    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class _FakeOpenAIClient:
    def __init__(self, response: object) -> None:
        self.responses = _FakeResponses(response)


class DesktopAgentBackendTests(unittest.TestCase):
    def test_generate_code_uses_agent_flow_with_current_settings(self) -> None:
        settings = object()
        result = backend.GeneratedScoreCode(python_code="def build_score():\n    return None\n")
        client = backend.DesktopAgentBackend(
            humming_session=Mock(),
            settings_factory=lambda: settings,
        )

        with patch.object(
            backend.legacy_agent_module,
            "generate_score_code_from_prompt",
            return_value=result,
        ) as generate_mock:
            response = client.generate_code("write a canon", "sk-test", "A4, quarter")

        self.assertIs(response, result)
        generate_mock.assert_called_once_with(
            "write a canon",
            "sk-test",
            settings,
            "A4, quarter",
        )

    def test_humming_calls_are_forwarded_to_service(self) -> None:
        humming_session = Mock()
        humming_session.stop_recording.return_value = backend.CapturedHumming(
            notes="C4, quarter",
            audio_path="/tmp/test.wav",
            duration_seconds=1.25,
        )
        client = backend.DesktopAgentBackend(
            humming_session=humming_session,
            settings_factory=lambda: object(),
        )

        client.start_humming()
        result = client.stop_humming()

        humming_session.start_recording.assert_called_once_with()
        humming_session.stop_recording.assert_called_once_with()
        self.assertEqual(result.notes, "C4, quarter")
        self.assertEqual(result.audio_path, "/tmp/test.wav")

    def test_apply_live_score_edit_runs_full_orchestration(self) -> None:
        settings = SimpleNamespace(
            root_dir=ROOT,
            maestro_skill_dir=ROOT / "skill",
            maestro_docs_dir=ROOT / "docs",
            maestroxml_src_dir=ROOT / "packages" / "maestroxml" / "src",
            openai_model="gpt-5.4",
            openai_reasoning_effort="low",
            openai_max_output_tokens=20000,
            execution_timeout_seconds=20,
        )
        bridge_client = Mock()
        bridge_client.export_musicxml.return_value = {
            "path": "/tmp/current-score.musicxml",
            "format": "musicxml",
        }
        bridge_client.apply_actions.return_value = {
            "command_count": 2,
            "all_ok": True,
            "results": [{"ok": True}, {"ok": True}],
        }

        response = SimpleNamespace(status="completed", output_text="def apply_changes(score):\n    pass\n")
        openai_client = _FakeOpenAIClient(response)
        transcriber = Mock(return_value="A4, quarter")
        client = backend.DesktopAgentBackend(
            humming_session=Mock(),
            settings_factory=lambda: object(),
            live_settings_factory=lambda: settings,
            bridge_client_factory=lambda: bridge_client,
            audio_transcriber=transcriber,
            openai_client_factory=lambda api_key: openai_client,
        )

        with patch.object(backend, "load_reference_corpus", return_value="refs") as load_refs_mock:
            with patch.object(
                backend,
                "musicxml_to_python",
                return_value="from maestroxml import Score\n\nscore = Score()\nflute = score.add_part('Flute')\n",
            ) as import_mock:
                with patch.object(
                    backend,
                    "execute_generated_edit_code",
                    return_value=[
                        {"kind": "add_note", "pitch": "C5", "duration": "quarter", "tick": 0},
                        {"kind": "add_dynamic", "text": "mf", "tick": 0},
                    ],
                ) as execute_mock:
                    with patch.object(Path, "is_file", return_value=True):
                        with patch.object(Path, "unlink", return_value=None):
                            result = client.apply_live_score_edit(
                                "make the ending louder",
                                audio_path="/tmp/hum.wav",
                                api_key="sk-test",
                            )

        self.assertEqual(result.action_count, 2)
        self.assertEqual(result.hummed_notes, "A4, quarter")
        self.assertIn("apply_changes", result.python_code)
        transcriber.assert_called_once_with(Path("/tmp/hum.wav"))
        bridge_client.export_musicxml.assert_called_once_with()
        bridge_client.apply_actions.assert_called_once()
        load_refs_mock.assert_called_once_with(
            settings.root_dir,
            settings.maestro_skill_dir,
            settings.maestro_docs_dir,
        )
        import_mock.assert_called_once_with(Path("/tmp/current-score.musicxml"))
        execute_mock.assert_called_once()
        self.assertEqual(openai_client.responses.calls[0]["model"], "gpt-5.4")

    def test_apply_live_score_edit_requires_env_api_key_by_default(self) -> None:
        client = backend.DesktopAgentBackend(
            humming_session=Mock(),
            settings_factory=lambda: object(),
        )

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(backend.LiveEditError):
                client.apply_live_score_edit("make it legato")

    def test_apply_live_score_edit_falls_back_to_bridge_snapshot_when_export_fails(self) -> None:
        settings = SimpleNamespace(
            root_dir=ROOT,
            maestro_skill_dir=ROOT / "skill",
            maestro_docs_dir=ROOT / "docs",
            maestroxml_src_dir=ROOT / "packages" / "maestroxml" / "src",
            openai_model="gpt-5.4",
            openai_reasoning_effort="low",
            openai_max_output_tokens=20000,
            execution_timeout_seconds=20,
        )
        bridge_client = Mock()
        bridge_client.export_musicxml.side_effect = backend.BridgeError(
            "Failed to export the open score to MusicXML."
        )
        bridge_client.score_info.return_value = {
            "title": "Sketch",
            "composer": "Tester",
            "nstaves": 2,
            "nmeasures": 2,
            "tpq": 480,
            "measure_starts": [0, 1920],
            "parts": [
                {
                    "partName": "Piano",
                    "shortName": "Pno.",
                    "instrumentId": "piano",
                    "startTrack": 0,
                    "endTrack": 8,
                }
            ],
        }
        bridge_client.read_score.return_value = {
            "events": [
                {
                    "tick": 0,
                    "staffIdx": 0,
                    "voice": 0,
                    "durN": 1,
                    "durD": 4,
                    "type": "chord",
                    "pitches": [60],
                },
                {
                    "tick": 480,
                    "staffIdx": 0,
                    "voice": 0,
                    "durN": 1,
                    "durD": 4,
                    "type": "rest",
                },
                {
                    "tick": 1920,
                    "staffIdx": 1,
                    "voice": 0,
                    "durN": 1,
                    "durD": 2,
                    "type": "chord",
                    "pitches": [48],
                },
            ]
        }
        bridge_client.apply_actions.return_value = {
            "command_count": 1,
            "all_ok": True,
            "results": [{"ok": True}],
        }

        response = SimpleNamespace(status="completed", output_text="def apply_changes(score):\n    pass\n")
        openai_client = _FakeOpenAIClient(response)
        client = backend.DesktopAgentBackend(
            humming_session=Mock(),
            settings_factory=lambda: object(),
            live_settings_factory=lambda: settings,
            bridge_client_factory=lambda: bridge_client,
            audio_transcriber=Mock(return_value=""),
            openai_client_factory=lambda api_key: openai_client,
        )

        with patch.object(backend, "load_reference_corpus", return_value="refs"):
            with patch.object(backend, "musicxml_to_python") as import_mock:
                with patch.object(
                    backend,
                    "execute_generated_edit_code",
                    return_value=[{"kind": "add_dynamic", "text": "mf", "tick": 0}],
                ) as execute_mock:
                    result = client.apply_live_score_edit("add a dynamic", api_key="sk-test")

        self.assertEqual(result.action_count, 1)
        import_mock.assert_not_called()
        bridge_client.export_musicxml.assert_called_once_with()
        bridge_client.score_info.assert_called_once_with()
        bridge_client.read_score.assert_called_once_with()
        execute_args = execute_mock.call_args.args
        current_score_python = execute_args[1]
        self.assertIn("score = Score(title='Sketch', composer='Tester')", current_score_python)
        self.assertIn("piano = score.add_part('Piano', instrument='piano', abbreviation='Pno.', staves=2)", current_score_python)
        self.assertIn("piano_staff_1_voice_1.note('quarter', 'C4')", current_score_python)
        self.assertIn("piano_staff_2_voice_1.note('half', 'C3')", current_score_python)


if __name__ == "__main__":
    unittest.main()
