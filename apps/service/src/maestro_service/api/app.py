from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import maestro_service.bootstrap.generator as generator_module
import maestro_service.bootstrap.humming as humming_module
from maestro_agent_core import AgentError
from maestro_service.bootstrap.config import get_settings


app = FastAPI(title="Maestro Service")
humming_service = humming_module.HummingService()


class GenerateRequest(BaseModel):
    api_key: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    hummed_notes: str = ""


class GenerateResponse(BaseModel):
    filename: str
    python_code: str
    musicxml: str


class ErrorResponse(BaseModel):
    error: str
    python_code: str = ""


class HummingStartResponse(BaseModel):
    recording: bool
    status: str


class HummingStopResponse(BaseModel):
    recording: bool
    hummed_notes: str
    status: str


@app.post("/api/generate", response_model=GenerateResponse, responses={422: {"model": ErrorResponse}})
async def generate(payload: GenerateRequest) -> GenerateResponse | JSONResponse:
    try:
        result = await asyncio.to_thread(
            generator_module.generate_musicxml_from_prompt,
            payload.prompt,
            payload.api_key,
            get_settings(),
            payload.hummed_notes,
        )
    except AgentError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": str(exc), "python_code": exc.python_code or ""},
        )

    return GenerateResponse(
        filename=result.filename,
        python_code=result.python_code,
        musicxml=result.musicxml,
    )


@app.post("/api/humming/start", response_model=HummingStartResponse)
async def start_humming() -> HummingStartResponse | JSONResponse:
    try:
        await asyncio.to_thread(humming_service.start_recording)
    except humming_module.HummingError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    return HummingStartResponse(
        recording=True,
        status="Recording... hum, then press Stop.",
    )


@app.post("/api/humming/stop", response_model=HummingStopResponse)
async def stop_humming() -> HummingStopResponse | JSONResponse:
    try:
        hummed_notes = await asyncio.to_thread(humming_service.stop_recording)
    except humming_module.HummingError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})

    status = "Humming captured." if hummed_notes else "No stable notes detected. Try again."
    return HummingStopResponse(
        recording=False,
        hummed_notes=hummed_notes,
        status=status,
    )


@app.get("/healthz")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"ok": True})
