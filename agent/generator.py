from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from maestro_agent_core import AgentError as CoreAgentError
from maestro_agent_core import extract_output_text as extract_output_text_from_response
from maestro_agent_core import response_status_message
from maestro_agent_core.context import ReferenceLoadError, load_reference_corpus


CANONICAL_DURATION_NAMES = {
    "whole": "whole",
    "half": "half",
    "quarter": "quarter",
    "eighth": "eighth",
    "8th": "eighth",
    "16th": "16th",
    "sixteenth": "16th",
    "32nd": "32nd",
    "thirty-second": "32nd",
    "thirty second": "32nd",
    "64th": "64th",
    "sixty-fourth": "64th",
    "sixty fourth": "64th",
}
DOTTED_DURATION_PREFIXES = (
    "single dotted ",
    "double dotted ",
    "triple dotted ",
    "dotted ",
)
NOTE_METHOD_NAMES = {"note", "notes", "rest", "chord"}
DISALLOWED_CALL_NAMES = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "input",
    "breakpoint",
    "open",
}
DISALLOWED_ATTRIBUTE_CALLS = {
    "apply",
    "chmod",
    "chown",
    "hardlink_to",
    "mkdir",
    "open",
    "popen",
    "read_bytes",
    "read_text",
    "remove",
    "rename",
    "replace",
    "rmdir",
    "run",
    "symlink_to",
    "system",
    "to_actions",
    "to_batch",
    "to_string",
    "touch",
    "unlink",
    "write",
    "write_bytes",
    "write_text",
}
ALLOWED_IMPORTS = {"__future__", "maestroxml"}


class AgentError(RuntimeError):
    """Raised when prompt-to-score generation fails."""

    def __init__(self, message: str, python_code: str | None = None) -> None:
        super().__init__(message)
        self.python_code = python_code


@dataclass(frozen=True)
class GeneratedScoreCode:
    python_code: str


@dataclass(frozen=True)
class ScoreGenerationSettings:
    root_dir: Path
    maestro_skill_dir: Path
    maestro_docs_dir: Path
    openai_model: str
    openai_reasoning_effort: str
    openai_max_output_tokens: int


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


def generate_score_code_from_prompt(
    prompt: str,
    api_key: str,
    settings: ScoreGenerationSettings,
    hummed_notes: str = "",
) -> GeneratedScoreCode:
    python_code = generate_python_code(prompt, api_key, settings, hummed_notes=hummed_notes)
    try:
        _validate_generated_score_code(python_code)
    except AgentError:
        raise
    except Exception as exc:
        raise AgentError(str(exc), python_code=python_code) from exc

    return GeneratedScoreCode(python_code=python_code)


def generate_python_code(
    prompt: str,
    api_key: str,
    settings: ScoreGenerationSettings,
    hummed_notes: str = "",
) -> str:
    if not api_key.strip():
        raise AgentError("An OpenAI API key is required.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AgentError(
            "The OpenAI Python SDK is not installed. Install the desktop dependencies first."
        ) from exc

    try:
        reference_corpus = load_reference_corpus(
            settings.root_dir,
            settings.maestro_skill_dir,
            settings.maestro_docs_dir,
        )
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
        raise AgentError(response_status_message(response))

    try:
        return extract_output_text_from_response(response)
    except CoreAgentError as exc:
        raise AgentError(str(exc)) from exc


def _root_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_name(node.value)
    return None


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _validate_duration_literal(value: str, source: str) -> None:
    normalized = " ".join(value.strip().lower().replace("-", " ").split())
    for prefix in DOTTED_DURATION_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
            break

    if normalized not in CANONICAL_DURATION_NAMES:
        supported = ", ".join(sorted(CANONICAL_DURATION_NAMES))
        raise AgentError(
            f"Unsupported duration literal {value!r} in generated code ({source}). "
            "Supported duration names: "
            f"{supported}. Dotted forms such as 'dotted quarter' are also allowed."
        )


def _validate_generated_score_code(code: str) -> None:
    stripped = code.strip()
    if not stripped:
        raise AgentError("The model returned an empty response instead of Python code.")
    if "```" in code:
        raise AgentError("The model returned Markdown fences; raw Python source was required.")

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise AgentError(f"Generated Python is not syntactically valid: {exc.msg}") from exc

    public_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    build_score_functions = [node for node in public_functions if node.name == "build_score"]
    if len(build_score_functions) != 1:
        raise AgentError("Generated code must define exactly one build_score() function.")

    if len(public_functions) != 1:
        raise AgentError("Generated code must not define helper functions outside build_score().")

    build_score = build_score_functions[0]
    if build_score.args.args or build_score.args.kwonlyargs or build_score.args.vararg or build_score.args.kwarg:
        raise AgentError("build_score must not accept any arguments.")

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef)):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        raise AgentError("Generated code must not execute statements at import time.")

    has_maestroxml_import = False
    has_build_score_return = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in ALLOWED_IMPORTS:
                    raise AgentError(f"Disallowed import in generated code: {alias.name}")
                if root == "maestroxml":
                    has_maestroxml_import = True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root not in ALLOWED_IMPORTS:
                raise AgentError(f"Disallowed import in generated code: {module}")
            if root == "maestroxml":
                has_maestroxml_import = True
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            if call_name in DISALLOWED_CALL_NAMES:
                raise AgentError(f"Disallowed function call in generated code: {call_name}")
            if call_name.startswith("os.") or call_name.startswith("subprocess."):
                raise AgentError(f"Disallowed function call in generated code: {call_name}")
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in NOTE_METHOD_NAMES and node.args:
                    duration = _string_constant(node.args[0])
                    if duration is not None:
                        _validate_duration_literal(duration, f"{node.func.attr}(...) call")
                if node.func.attr in DISALLOWED_ATTRIBUTE_CALLS:
                    raise AgentError(f"Disallowed attribute call in generated code: {node.func.attr}")
                root = _root_name(node.func.value)
                if root in {"subprocess", "shutil", "socket"}:
                    raise AgentError(f"Disallowed module usage in generated code: {root}.{node.func.attr}")
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if _string_constant(key) == "duration":
                    duration = _string_constant(value)
                    if duration is not None:
                        _validate_duration_literal(duration, "duration field")
        elif isinstance(node, ast.Return) and node.value is not None:
            has_build_score_return = True

    if not has_maestroxml_import:
        raise AgentError("Generated code must import `maestroxml`.")
    if not has_build_score_return:
        raise AgentError("build_score() must return the populated Score.")
