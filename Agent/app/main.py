from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import app.agent as agent_module
import app.humming as humming_module
from app.config import get_settings
from app.context import ReferenceLoadError


STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

app = FastAPI(title="MaestroXML Prompt-to-MuseScore")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
humming_service = humming_module.HummingService()


class GenerateRequest(BaseModel):
    api_key: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    hummed_notes: str = ""


class GenerateResponse(BaseModel):
    python_code: str


class HummingStartResponse(BaseModel):
    recording: bool
    status: str


class HummingStopResponse(BaseModel):
    recording: bool
    hummed_notes: str
    status: str


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest):
    try:
        result = await asyncio.to_thread(
            agent_module.generate_score_code_from_prompt,
            payload.prompt,
            payload.api_key,
            get_settings(),
            payload.hummed_notes,
        )
    except agent_module.AgentError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": str(exc), "python_code": exc.python_code or ""},
        )
    except ReferenceLoadError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc), "python_code": ""})

    return GenerateResponse(
        python_code=result.python_code,
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
