from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest


ROOT = Path(__file__).resolve().parents[3]
for extra in (
    ROOT / "packages" / "agent-core" / "src",
    ROOT / "packages" / "maestroxml" / "src",
):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from maestro_agent_core import (
    AgentError,
    CodeGuardError,
    build_model_input,
    execute_generated_code,
    sanitize_filename_stem,
    validate_generated_code,
)
from maestro_agent_core.context import ReferenceLoadError, load_reference_corpus


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

            corpus = load_reference_corpus(root, skill_dir, docs_dir)

        self.assertIn("repo readme", corpus)
        self.assertIn("getting started", corpus)
        self.assertIn("skill api", corpus)
        self.assertNotIn("ignore me", corpus)

    def test_missing_required_reference_fails(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docs_dir = root / "docs"
            skill_dir = root / "skill"
            docs_dir.mkdir()
            skill_dir.mkdir()
            (root / "README.md").write_text("repo readme", encoding="utf-8")
            with self.assertRaises(ReferenceLoadError):
                load_reference_corpus(root, skill_dir, docs_dir)


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
            src_dir.mkdir(parents=True)
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
                maestroxml_src_root=root / "src",
                execution_timeout_seconds=10,
            )

        self.assertEqual(filename, "flute_solo.musicxml")
        self.assertEqual(musicxml, "<score-partwise/>")


if __name__ == "__main__":
    unittest.main()
