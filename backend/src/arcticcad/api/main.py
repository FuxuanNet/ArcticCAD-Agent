from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from arcticcad.application import CadOrchestrator
from arcticcad.config import load_app_config, masked_status
from arcticcad.domain import ChatRequest, CreateProjectInput, JscadRunResult, ReviewRequest, SnapshotInput
from arcticcad.providers import ModelRouter
from arcticcad.skills import SkillProvider
from arcticcad.storage import FileProjectStore

config = load_app_config()
store = FileProjectStore(config.projects_dir)
orchestrator = CadOrchestrator(store, SkillProvider(config.project_root), ModelRouter(config))

app = FastAPI(title="ArcticCAD-Agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(iterator: AsyncIterator[object]) -> StreamingResponse:
    async def stream() -> AsyncIterator[str]:
        try:
            async for event in iterator:
                payload = event.model_dump(mode="json", exclude_none=True)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            raise

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/config/status")
def config_status() -> dict:
    return {
        "llm": {
            "provider": config.llm.provider,
            "baseUrl": config.llm.base_url,
            "model": config.llm.model,
            "status": masked_status(config.llm.api_key),
        },
        "vision": {
            "provider": config.vision.provider,
            "baseUrl": config.vision.base_url,
            "model": config.vision.model,
            "status": masked_status(config.vision.api_key),
        },
        "projectsDir": str(config.projects_dir),
        "llmTimeoutSeconds": config.llm_timeout_seconds,
    }


@app.get("/api/projects")
def list_projects() -> list[dict]:
    return [project.model_dump(mode="json") for project in store.list_projects()]


@app.post("/api/projects")
def create_project(input_data: CreateProjectInput) -> dict:
    return store.create_project(input_data).model_dump(mode="json")


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    try:
        return store.get_project(project_id).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.get("/api/projects/{project_id}/versions")
def list_versions(project_id: str) -> list[dict]:
    return [version.model_dump(mode="json") for version in store.list_versions(project_id)]


@app.get("/api/projects/{project_id}/runs")
def list_runs(project_id: str) -> list[dict]:
    try:
        store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return store.list_runs(project_id)


@app.post("/api/projects/{project_id}/snapshots")
def save_snapshot(project_id: str, payload: SnapshotInput) -> dict:
    try:
        store.get_project(project_id)
        return store.save_snapshot(project_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.get("/api/projects/{project_id}/snapshots/{snapshot_id}")
def get_snapshot(project_id: str, snapshot_id: str) -> dict:
    try:
        return store.get_snapshot(project_id, snapshot_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Snapshot not found") from exc


@app.get("/api/projects/{project_id}/snapshots")
def list_snapshots(project_id: str) -> list[dict]:
    try:
        store.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    return store.list_snapshots(project_id)


@app.get("/api/projects/{project_id}/conversations")
def list_conversations(project_id: str) -> list[dict]:
    return [conversation.model_dump(mode="json") for conversation in store.list_conversations(project_id)]


@app.post("/api/projects/{project_id}/conversations")
def create_conversation(project_id: str, payload: dict | None = None) -> dict:
    title = str((payload or {}).get("title") or "新建对话")
    return store.create_conversation(project_id, title).model_dump(mode="json")


@app.get("/api/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str) -> list[dict]:
    return [message.model_dump(mode="json") for message in store.list_messages(conversation_id)]


@app.post("/api/agent/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    return sse(orchestrator.chat(request))


@app.post("/api/agent/review")
def review(request: ReviewRequest) -> StreamingResponse:
    return sse(orchestrator.review(request))


@app.post("/api/agent/render-result")
def submit_render_result(result: JscadRunResult) -> StreamingResponse:
    return sse(orchestrator.submit_render_result_stream(result))


def run() -> None:
    uvicorn.run("arcticcad.api.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
