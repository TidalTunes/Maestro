from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.context import ReferenceLoadError, load_reference_corpus
from app.guard import CodeGuardError, validate_generated_code


class AgentError(RuntimeError):
    """Raised when prompt-to-code generation fails."""

    def __init__(self, message: str, python_code: str | None = None) -> None:
        super().__init__(message)
        self.python_code = python_code


@dataclass(frozen=True)
class GeneratedScoreCode:
    python_code: str


def build_generation_instructions(reference_corpus: str) -> str:
    return (
        "You are a specialist Python code generator for the current maestroxml package.\n\n"
        "<instruction_priority>\n"
        "- Follow the local Maestro references exactly.\n"
        "- The current maestroxml workflow is bridge-backed and targets live MuseScore scores.\n"
        "- Older MusicXML-export guidance is obsolete unless the local references explicitly describe an import helper.\n"
        "- If the user requests unsupported notation, simplify to the closest supported result.\n"
        "</instruction_priority>\n\n"
        "<code_contract>\n"
        "- Return runnable Python 3.13+ source code.\n"
        "- Return only Python. No Markdown fences.\n"
        "- Define exactly one public function named build_score().\n"
        "- build_score() must create and return a populated maestroxml Score object.\n"
        "- Do not call score.apply(), score.write(), score.to_actions(), score.to_string(), or score.to_batch() inside build_score().\n"
        "- Allowed imports: from maestroxml import ... only.\n"
        "- Do not import pathlib, os, subprocess, json, requests, sys, typing, or any other module.\n"
        "- Do not read files, inspect environment variables, open network connections, invoke subprocesses, or execute dynamic code.\n"
        "- Use loops and helper data structures inside build_score() when the musical material repeats.\n"
        "- If title or composer are missing, choose short tasteful defaults.\n"
        "- If applicable, cellos should be denoted as Violoncello.\n"
        "</code_contract>\n\n"
        "<bridge_guidance>\n"
        "- Compose with Score, Part, and voice(...) as usual.\n"
        "- The returned Score may later be inspected with to_actions()/to_string() or applied with apply() by another system.\n"
        "- Keep bridge limits in mind and avoid promising unsupported backend materialization.\n"
        "</bridge_guidance>\n\n"
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


def generate_score_code_from_prompt(
    prompt: str,
    api_key: str,
    settings: Settings,
    hummed_notes: str = "",
) -> GeneratedScoreCode:
    python_code = generate_python_code(prompt, api_key, settings, hummed_notes=hummed_notes)
    try:
        validate_generated_code(python_code)
    except CodeGuardError as exc:
        raise AgentError(str(exc), python_code) from exc

    return GeneratedScoreCode(python_code=python_code)


def generate_python_code(
    prompt: str,
    api_key: str,
    settings: Settings,
    hummed_notes: str = "",
) -> str:
    if not api_key.strip():
        raise AgentError("An OpenAI API key is required.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AgentError(
            "The OpenAI Python SDK is not installed. Install dependencies from requirements.txt first."
        ) from exc

    try:
        reference_corpus = load_reference_corpus(settings)
    except ReferenceLoadError as exc:
        raise AgentError(str(exc)) from exc

    client = OpenAI(api_key=api_key.strip())
    try:
        response = client.responses.create(
            model=settings.openai_model,
            instructions=build_generation_instructions(reference_corpus),
            input=build_model_input(prompt, hummed_notes),
            reasoning={"effort": settings.openai_reasoning_effort},
            max_output_tokens=settings.openai_max_output_tokens,
            store=False,
            text={"verbosity": "low"},
        )
    except Exception as exc:
        raise AgentError(f"OpenAI request failed: {exc}") from exc

    status = getattr(response, "status", None)
    if status not in {None, "completed"}:
        raise AgentError(_response_status_message(response))

    return extract_output_text(response)


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


def _response_status_message(response: object) -> str:
    details = getattr(response, "incomplete_details", None)
    reason = getattr(details, "reason", None)
    if reason == "max_output_tokens":
        return "OpenAI stopped before finishing the code because the response hit its token budget."
    status = getattr(response, "status", None)
    if reason:
        return f"OpenAI returned an incomplete response ({reason})."
    return f"OpenAI returned an incomplete response with status {status!r}."
