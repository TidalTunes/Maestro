from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .guard import validate_generated_code


RUNNER_SCRIPT = """
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

script_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

spec = importlib.util.spec_from_file_location("generated_maestro_score", script_path)
if spec is None or spec.loader is None:
    raise RuntimeError("Unable to load generated score module.")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

build_score = getattr(module, "build_score", None)
if build_score is None or not callable(build_score):
    raise RuntimeError("Generated code must define build_score(output_path).")

build_score(str(output_path))
""".strip()


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


def build_generation_instructions(reference_corpus: str) -> str:
    return (
        "You are a specialist Python code generator for the maestroxml package.\n\n"
        "<instruction_priority>\n"
        "- Follow the Maestro references exactly when they conflict with user preferences.\n"
        "- Stay within maestroxml's supported MusicXML subset.\n"
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
        "- Supported duration names are whole, half, quarter, eighth, 16th, 32nd, 64th.\n"
        "- Allowed aliases are 8th, sixteenth, thirty-second, sixty-fourth.\n"
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

        env = {
            "PYTHONPATH": str(maestroxml_src_root),
            "PYTHONIOENCODING": "utf-8",
        }

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    RUNNER_SCRIPT,
                    str(generated_script),
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
