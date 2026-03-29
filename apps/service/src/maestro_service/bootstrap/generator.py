from __future__ import annotations

from maestro_agent_core import (
    AgentError,
    CodeGuardError,
    GeneratedMusicXML,
    build_generation_instructions,
    build_model_input,
    execute_generated_code,
    extract_output_text,
    response_status_message,
    sanitize_filename_stem,
    validate_generated_code,
)
from maestro_agent_core.context import ReferenceLoadError, load_reference_corpus

from .config import ServiceSettings


def generate_musicxml_from_prompt(
    prompt: str,
    api_key: str,
    settings: ServiceSettings,
    hummed_notes: str = "",
) -> GeneratedMusicXML:
    python_code = generate_python_code(prompt, api_key, settings, hummed_notes=hummed_notes)
    try:
        validate_generated_code(python_code)
        filename, musicxml = execute_generated_code(
            python_code,
            sanitize_filename_stem(prompt),
            maestroxml_src_root=settings.maestroxml_src_dir,
            execution_timeout_seconds=settings.execution_timeout_seconds,
        )
    except (AgentError, CodeGuardError) as exc:
        raise AgentError(str(exc), python_code) from exc

    return GeneratedMusicXML(
        filename=filename,
        python_code=python_code,
        musicxml=musicxml,
    )


def generate_python_code(
    prompt: str,
    api_key: str,
    settings: ServiceSettings,
    hummed_notes: str = "",
) -> str:
    if not api_key.strip():
        raise AgentError("An OpenAI API key is required.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AgentError(
            "The OpenAI Python SDK is not installed. Install service dependencies first."
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

    return extract_output_text(response)
