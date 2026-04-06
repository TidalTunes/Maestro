from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .guard import validate_generated_code, validate_generated_edit_code


class AgentError(RuntimeError):
    """Raised when prompt-to-MusicXML generation fails."""

    def __init__(self, message: str, python_code: str | None = None) -> None:
        super().__init__(message)
        self.python_code = python_code


@dataclass(frozen=True)
class GeneratedMusicXML:
    filename: str
    python_code: str
    musicxml: str


def _module_src_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _bridge_src_root(maestroxml_src_root: Path) -> Path | None:
    packages_root = maestroxml_src_root.resolve().parents[1]
    candidate = packages_root / "maestro-musescore-bridge" / "src"
    if candidate.is_dir():
        return candidate
    return None


def _runner_command() -> list[str]:
    explicit_runner = os.environ.get("MAESTRO_RUNTIME_RUNNER", "").strip()
    if explicit_runner:
        return [explicit_runner]

    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().with_name("maestro-runtime-runner")
        if candidate.is_file():
            return [str(candidate)]
        raise AgentError("Frozen Maestro build is missing the runtime runner helper.")

    return [sys.executable, "-m", "maestro_agent_core.runtime_runner"]


def _execution_env(maestroxml_src_root: Path) -> dict[str, str]:
    module_src_root = _module_src_root()
    maestroxml_src_root = maestroxml_src_root.resolve()
    bridge_src_root = _bridge_src_root(maestroxml_src_root)

    pythonpath_parts = [str(module_src_root), str(maestroxml_src_root)]
    if bridge_src_root is not None:
        pythonpath_parts.append(str(bridge_src_root))

    existing_pythonpath = os.environ.get("PYTHONPATH", "").strip()
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)

    env = dict(os.environ)
    env["MAESTRO_AGENT_CORE_SRC_DIR"] = str(module_src_root)
    env["MAESTRO_MAESTROXML_SRC_DIR"] = str(maestroxml_src_root)
    if bridge_src_root is not None:
        env["MAESTRO_BRIDGE_SRC_DIR"] = str(bridge_src_root)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def build_generation_instructions(reference_corpus: str) -> str:
    return (
        "You are a specialist Python code generator for the maestroxml package.\n\n"
        "<instruction_priority>\n"
        "- Follow the Maestro references exactly when they conflict with user preferences.\n"
        "- Stay within maestroxml's supported MusicXML subset.\n"
        "- Prefer naturals and single sharps/flats over double-sharp or double-flat spellings unless the user explicitly asks for them.\n"
        "- If the user requests unsupported notation, simplify to the closest supported result.\n"
        "</instruction_priority>\n\n"
        "<code_contract>\n"
        "- Return runnable Python 3.13+ source code.\n"
        "- Return only Python. No Markdown fences.\n"
        "- Define exactly one public function named build_score(output_path).\n"
        "- build_score(output_path) must create a fresh maestroxml Score and write MusicXML to output_path.\n"
        "- Allowed imports: from maestroxml import ... and optionally from pathlib import Path.\n"
        "- Do not import os, subprocess, json, requests, sys, typing, or any other module.\n"
        "- Do not read files, inspect environment variables, open network connections, invoke subprocesses, or execute dynamic code.\n"
        "- Use loops and helper data structures inside build_score when the musical material repeats.\n"
        "- If title or composer are missing, choose short tasteful defaults.\n"
        "- If applicable, cellos should be denoted as Violoncello.\n"
        "</code_contract>\n\n"
        "<duration_contract>\n"
        "- Supported base duration names are whole, half, quarter, eighth, 16th, 32nd, 64th.\n"
        "- Allowed aliases are 8th, sixteenth, thirty-second, sixty-fourth.\n"
        "- Dotted phrases such as dotted quarter, double dotted half, and double-dotted eighth are supported and map to dots automatically.\n"
        "- Never invent duration labels such as note, beat, quarter note, or quarter-note.\n"
        "</duration_contract>\n\n"
        "<reference_material>\n"
        f"{reference_corpus}\n"
        "</reference_material>"
    )


def build_edit_generation_instructions(reference_corpus: str) -> str:
    return (
        "You are a specialist Python edit generator for the maestroxml package.\n\n"
        "<instruction_priority>\n"
        "- Follow the Maestro references exactly when they conflict with user preferences.\n"
        "- The current score context is reference material that shows the live score as code.\n"
        "- During execution, score and the named part/voice globals refer to a blank maestroxml change plan with the same existing structure.\n"
        "- Add only the requested changes. Do not recreate the existing score content.\n"
        "- Prefer naturals and single sharps/flats over double-sharp or double-flat spellings unless the user explicitly asks for them.\n"
        "- If the user requests unsupported notation, simplify to the closest supported result.\n"
        "</instruction_priority>\n\n"
        "<code_contract>\n"
        "- Return runnable Python 3.13+ source code.\n"
        "- Return only Python. No Markdown fences.\n"
        "- Define exactly one public function named apply_changes(score).\n"
        "- apply_changes(score) will run in a module that already defines score and the named part/voice globals shown in the current score context.\n"
        "- score starts as an empty change plan with the same part, staff, voice, and measure structure as the live score.\n"
        "- Add only the requested note, rest, chord, direction, time/key, measure, or part changes to that change plan.\n"
        "- Do not recreate existing notes, rests, chords, directions, parts, or measures unless the user explicitly asks to change them.\n"
        "- Mutate the supplied score in place.\n"
        "- Do not create a replacement score and do not return a value.\n"
        "- Do not import any modules.\n"
        "- Do not call score.apply(), score.write(), score.to_actions(), score.to_string(), or score.to_batch().\n"
        "- Do not read files, inspect environment variables, open network connections, invoke subprocesses, or execute dynamic code.\n"
        "- Use loops and helper data structures inside apply_changes(score) when the edit repeats.\n"
        "- Use score.measure(...) before adding events or directions.\n"
        "</code_contract>\n\n"
        "<duration_contract>\n"
        "- Supported base duration names are whole, half, quarter, eighth, 16th, 32nd, 64th.\n"
        "- Allowed aliases are 8th, sixteenth, thirty-second, sixty-fourth.\n"
        "- Dotted phrases such as dotted quarter, double dotted half, and double-dotted eighth are supported and map to dots automatically.\n"
        "- Never invent duration labels such as note, beat, quarter note, or quarter-note.\n"
        "</duration_contract>\n\n"
        "<reference_material>\n"
        f"{reference_corpus}\n"
        "</reference_material>"
    )


def build_model_input(prompt: str, hummed_notes: str = "") -> str:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise AgentError("The musical prompt cannot be empty.")

    sections = [
        "<user_prompt>",
        cleaned_prompt,
        "</user_prompt>",
    ]

    cleaned_hummed_notes = hummed_notes.strip()
    if cleaned_hummed_notes:
        sections.extend(
            [
                "",
                "<hummed_melody_context>",
                "The user hummed the following notes into the microphone. Treat this as supplemental melodic and rhythmic context for the requested piece:",
                cleaned_hummed_notes,
                "</hummed_melody_context>",
            ]
        )

    return "\n".join(sections)


def build_edit_model_input(
    prompt: str,
    current_score_python: str,
    hummed_notes: str = "",
) -> str:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise AgentError("The musical prompt cannot be empty.")

    cleaned_score_python = current_score_python.strip()
    if not cleaned_score_python:
        raise AgentError("The current score context cannot be empty.")

    sections = [
        "<user_prompt>",
        cleaned_prompt,
        "</user_prompt>",
    ]

    cleaned_hummed_notes = hummed_notes.strip()
    if cleaned_hummed_notes:
        sections.extend(
            [
                "",
                "<hummed_melody_context>",
                "The user hummed the following notes into the microphone. Treat this as supplemental melodic and rhythmic context for the requested edit:",
                cleaned_hummed_notes,
                "</hummed_melody_context>",
            ]
        )

    sections.extend(
        [
            "",
            "<current_score_python_context>",
            "The following Python represents the user's current score in maestroxml form.",
            "Treat it as reference context for naming, layout, measures, and musical material.",
            "During execution, score and the same named part/voice globals point to a blank maestroxml change plan with matching structure.",
            "Reuse those globals to add only the requested changes.",
            cleaned_score_python,
            "</current_score_python_context>",
        ]
    )

    return "\n".join(sections)


def execute_generated_code(
    python_code: str,
    filename_stem: str,
    *,
    maestroxml_src_root: Path,
    execution_timeout_seconds: int,
) -> tuple[str, str]:
    validate_generated_code(python_code)

    with tempfile.TemporaryDirectory(prefix="maestroxml-agent-") as directory:
        temp_dir = Path(directory)
        generated_script = temp_dir / "generated_score.py"
        output_path = temp_dir / f"{filename_stem}.musicxml"
        generated_script.write_text(python_code, encoding="utf-8")

        env = _execution_env(maestroxml_src_root)

        try:
            completed = subprocess.run(
                _runner_command() + ["generate", str(generated_script), str(output_path)],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                timeout=execution_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentError(
                f"Generated code timed out after {execution_timeout_seconds} seconds."
            ) from exc

        if completed.returncode != 0:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "Unknown execution failure."
            )
            raise AgentError(f"Generated code failed while writing MusicXML:\n{detail}")

        if not output_path.exists():
            raise AgentError("Generated code finished without producing a MusicXML file.")

        return output_path.name, output_path.read_text(encoding="utf-8")


def execute_generated_edit_code(
    python_code: str,
    current_score_python: str,
    *,
    maestroxml_src_root: Path,
    execution_timeout_seconds: int,
) -> list[dict[str, object]]:
    validate_generated_edit_code(python_code)

    cleaned_score_python = current_score_python.strip()
    if not cleaned_score_python:
        raise AgentError("The current score context cannot be empty.")

    with tempfile.TemporaryDirectory(prefix="maestroxml-edit-agent-") as directory:
        temp_dir = Path(directory)
        base_script = temp_dir / "current_score.py"
        edit_script = temp_dir / "generated_edits.py"
        output_path = temp_dir / "generated_actions.json"

        base_script.write_text(cleaned_score_python + "\n", encoding="utf-8")
        edit_script.write_text(python_code, encoding="utf-8")

        env = _execution_env(maestroxml_src_root)

        try:
            completed = subprocess.run(
                _runner_command()
                + [
                    "edit",
                    str(base_script),
                    str(edit_script),
                    str(output_path),
                ],
                capture_output=True,
                cwd=temp_dir,
                env=env,
                text=True,
                timeout=execution_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgentError(
                f"Generated edit code timed out after {execution_timeout_seconds} seconds."
            ) from exc

        if completed.returncode != 0:
            detail = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "Unknown execution failure."
            )
            raise AgentError(f"Generated edit code failed while building bridge actions:\n{detail}")

        if not output_path.exists():
            raise AgentError("Generated edit code finished without producing bridge actions.")

        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AgentError("Generated edit code produced invalid action JSON.") from exc

        if not isinstance(payload, list):
            raise AgentError("Generated edit code must produce a JSON array of bridge actions.")

        return payload


def extract_output_text(response: object) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    collected: list[str] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            content_type = getattr(content, "type", None)
            if content_type == "output_text":
                text = getattr(content, "text", None)
                if isinstance(text, str):
                    collected.append(text)
            elif content_type == "refusal":
                refusal = getattr(content, "refusal", None)
                if isinstance(refusal, str) and refusal.strip():
                    raise AgentError(refusal.strip())

    joined = "".join(collected).strip()
    if not joined:
        raise AgentError("OpenAI returned no text output.")
    return joined


def sanitize_filename_stem(prompt: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "_", prompt.strip().lower())
    collapsed = collapsed.strip("_")
    if not collapsed:
        return "generated_score"
    return collapsed[:60].strip("_") or "generated_score"


def response_status_message(response: object) -> str:
    details = getattr(response, "incomplete_details", None)
    reason = getattr(details, "reason", None)
    if reason == "max_output_tokens":
        return "OpenAI stopped before finishing the code because the response hit its token budget."
    status = getattr(response, "status", None)
    if reason:
        return f"OpenAI returned an incomplete response ({reason})."
    return f"OpenAI returned an incomplete response with status {status!r}."
