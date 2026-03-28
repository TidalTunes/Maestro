from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import app.agent as agent_module
from app.config import get_settings
from app.context import ReferenceLoadError


STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"

app = FastAPI(title="MaestroXML Prompt-to-MusicXML")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class GenerateRequest(BaseModel):
    api_key: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class GenerateResponse(BaseModel):
    filename: str
    python_code: str
    musicxml: str


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(payload: GenerateRequest):
    try:
        result = await asyncio.to_thread(
            agent_module.generate_musicxml_from_prompt,
            payload.prompt,
            payload.api_key,
            get_settings(),
        )
    except agent_module.AgentError as exc:
        return JSONResponse(
            status_code=422,
            content={"error": str(exc), "python_code": exc.python_code or ""},
        )
    except ReferenceLoadError as exc:
        return JSONResponse(status_code=500, content={"error": str(exc), "python_code": ""})

    return GenerateResponse(
        filename=result.filename,
        python_code=result.python_code,
        musicxml=result.musicxml,
    )


@app.get("/healthz")
async def healthcheck() -> JSONResponse:
    return JSONResponse({"ok": True})
