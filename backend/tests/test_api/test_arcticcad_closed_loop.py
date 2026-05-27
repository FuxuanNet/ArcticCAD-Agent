from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from arcticcad.api import main as api_main
from arcticcad.application import orchestrator as orchestrator_module
from arcticcad.application import CadOrchestrator
from arcticcad.config import load_app_config
from arcticcad.domain import ChatRequest
from arcticcad.providers.model_router import ModelResult
from arcticcad.skills import SkillProvider
from arcticcad.storage import FileProjectStore


TEST_ONLY_JSCAD = """const { cuboid } = require('@jscad/modeling').primitives

function main() {
  return cuboid({ size: [1200, 800, 600] })
}

module.exports = { main }
"""


class UnitStubModelRouter:
    def __init__(self, *, planning_error: str | None = None, vision_error: str | None = None) -> None:
        self.planning_error = planning_error
        self.vision_error = vision_error
        self.last_review_image_base64: str | None = None
        self.last_review_requirement_context: str | None = None
        self.last_review_prompt: str | None = None

    async def plan_intent(self, *, prompt: str, context: dict, on_progress=None) -> ModelResult:
        if self.planning_error:
            return ModelResult(ok=False, provider="test-only", error=self.planning_error)
        text = prompt.strip()
        if text == "你好":
            return ModelResult(
                ok=True,
                provider="test-only",
                data={
                    "intent": "chat",
                    "confidence": 1,
                    "assistantMessage": "你好，我在。",
                    "reason": "test-only chat",
                },
            )
        if text == "生成模型":
            return ModelResult(
                ok=True,
                provider="test-only",
                data={
                    "intent": "ask_clarifying_question",
                    "confidence": 1,
                    "assistantMessage": "请补充建模对象和关键要求。",
                    "reason": "test-only clarification",
                },
            )
        return ModelResult(
            ok=True,
            provider="test-only",
            data={"intent": "generate", "confidence": 1, "assistantMessage": "", "reason": "test-only generate"},
        )

    async def complete_code(self, *, prompt: str, context: dict, skill: str, on_progress=None) -> ModelResult:
        return ModelResult(ok=True, provider="test-only", code=TEST_ONLY_JSCAD)

    async def repair_code(self, **kwargs) -> ModelResult:
        return ModelResult(
            ok=True,
            provider="test-only",
            data={"decision": "continue", "code": TEST_ONLY_JSCAD, "reason": "test-only repair"},
        )

    async def reconstruct_from_asset(self, **kwargs) -> ModelResult:
        asset = kwargs.get("asset") or {}
        if asset.get("format") == "stl" and kwargs.get("mode") == "direct_insert":
            return ModelResult(ok=False, provider="test-only", error="STL direct insert blocked.")
        return ModelResult(ok=True, provider="test-only", code=TEST_ONLY_JSCAD)

    async def review_image_result(self, **kwargs) -> ModelResult:
        self.last_review_image_base64 = kwargs.get("image_base64")
        self.last_review_requirement_context = kwargs.get("user_requirement_context")
        self.last_review_prompt = kwargs.get("prompt")
        if self.vision_error:
            return ModelResult(ok=False, provider="test-only", error=self.vision_error)
        return ModelResult(
            ok=True,
            provider="test-only",
            data={
                "summary": "测试审图报告。",
                "risks": [],
                "drawingUnderstanding": "测试用几何体。",
                "requirementMatch": "渲染结果基本匹配测试需求。",
                "codeDesignBugs": ["测试代码设计问题。"],
                "coldRegionNotes": ["测试备注。"],
                "recommendAutoFix": False,
                "observations": ["测试观察。"],
                "suggestedFixes": ["测试建议。"],
                "evidence": ["测试依据。"],
            },
        )


class SlowUnitStubModelRouter(UnitStubModelRouter):
    async def complete_code(self, *, prompt: str, context: dict, skill: str, on_progress=None) -> ModelResult:
        await asyncio.sleep(0.4)
        return await super().complete_code(prompt=prompt, context=context, skill=skill, on_progress=on_progress)


class TimeoutVisionStubModelRouter(UnitStubModelRouter):
    def __init__(self) -> None:
        super().__init__()
        self.config = SimpleNamespace(
            vision_timeout_seconds=0.2,
            vision=SimpleNamespace(provider="test-only"),
        )

    async def review_image_result(self, **kwargs) -> ModelResult:
        await asyncio.sleep(1)
        return await super().review_image_result(**kwargs)


def _client(tmp_path, monkeypatch, models: object | None = None, project_dir_name: str = "projects") -> TestClient:
    store = FileProjectStore(tmp_path / "projects")
    if project_dir_name != "projects":
        store = FileProjectStore(tmp_path / project_dir_name)
    orchestrator = CadOrchestrator(store, SkillProvider(api_main.config.project_root), models or UnitStubModelRouter())
    monkeypatch.setattr(api_main, "store", store)
    monkeypatch.setattr(api_main, "orchestrator", orchestrator)
    return TestClient(api_main.app)


def _events(response) -> list[dict]:
    events: list[dict] = []
    for block in response.text.strip().split("\n\n"):
        if not block.strip():
            continue
        data = "\n".join(line.removeprefix("data: ").strip() for line in block.splitlines() if line.startswith("data:"))
        if data:
            events.append(json.loads(data))
    return events


def test_empty_project_dir_creates_real_sample_project(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    projects = client.get("/api/projects").json()
    assert len(projects) == 1
    assert projects[0]["name"] == "高寒临建模块示例"

    conversations = client.get(f"/api/projects/{projects[0]['id']}/conversations").json()
    assert len(conversations) == 1
    assert conversations[0]["title"] == "示例对话"
    assert conversations[0]["messageCount"] == 2
    assert projects[0]["currentConversationId"] == conversations[0]["id"]

    messages = client.get(f"/api/conversations/{conversations[0]['id']}/messages").json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert all(message["conversationId"] == conversations[0]["id"] for message in messages)


def test_projects_conversation_and_precise_messages(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    projects = client.get("/api/projects").json()
    project_id = projects[0]["id"]
    conversation = client.post(f"/api/projects/{project_id}/conversations", json={"title": "指定对话"}).json()

    response = client.post(
        "/api/agent/chat",
        json={"projectId": project_id, "conversationId": conversation["id"], "message": "生成一个临建模块"},
    )

    assert response.status_code == 200
    messages = client.get(f"/api/conversations/{conversation['id']}/messages").json()
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert all(message["conversationId"] == conversation["id"] for message in messages)


def test_chat_sse_generates_version(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]

    response = client.post(
        "/api/agent/chat",
        json={
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "message": "生成 JSCAD",
        },
    )

    events = _events(response)
    assert "code_write_done" in [event["type"] for event in events]
    assert client.get(f"/api/projects/{project['id']}/versions").json()[0]["status"] == "draft"


def test_greeting_chat_does_not_generate_version(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    before = client.get(f"/api/projects/{project['id']}/versions").json()

    response = client.post(
        "/api/agent/chat",
        json={
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "message": "你好",
        },
    )

    events = _events(response)
    assert "assistant_message" in [event["type"] for event in events]
    assert "code_write_done" not in [event["type"] for event in events]
    after = client.get(f"/api/projects/{project['id']}/versions").json()
    assert [item["id"] for item in after] == [item["id"] for item in before]


def test_underspecified_generation_asks_question(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]

    response = client.post(
        "/api/agent/chat",
        json={
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "message": "生成模型",
        },
    )

    events = _events(response)
    assert "user_action_required" in [event["type"] for event in events]
    assert "code_write_done" not in [event["type"] for event in events]


def test_missing_llm_does_not_write_fallback_code(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        models=UnitStubModelRouter(planning_error="文本模型未配置：请设置 CADX_LLM_API_KEY 后再进行 Agent planning。"),
        project_dir_name="strict-projects",
    )
    project = client.get("/api/projects").json()[0]
    before = client.get(f"/api/projects/{project['id']}/versions").json()

    response = client.post(
        "/api/agent/chat",
        json={
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "message": "生成一个高寒临建模块，带坡屋面和桩基础",
        },
    )

    events = _events(response)
    assert "model_error" in [event["type"] for event in events]
    after = client.get(f"/api/projects/{project['id']}/versions").json()
    assert [item["id"] for item in after] == [item["id"] for item in before]


def test_render_success_marks_rendered(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    version_id = project["currentVersionId"]

    response = client.post(
        "/api/agent/render-result",
        json={
            "ok": True,
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "versionId": version_id,
            "autoRepairAttempt": 0,
            "geometrySummary": "1 geometry item returned",
        },
    )

    events = _events(response)
    assert [event["type"] for event in events] == ["tool_result", "done"]
    version = next(item for item in client.get(f"/api/projects/{project['id']}/versions").json() if item["id"] == version_id)
    assert version["status"] == "rendered"
    runs = client.get(f"/api/projects/{project['id']}/runs").json()
    assert runs[0]["versionId"] == version_id
    assert runs[0]["ok"] is True


def test_config_status_and_snapshots(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]

    status = client.get("/api/config/status").json()
    assert status["llm"]["status"] in {"configured", "missing"}
    assert status["llmTimeoutSeconds"] == api_main.config.llm_timeout_seconds
    assert status["visionTimeoutSeconds"] == api_main.config.vision_timeout_seconds

    snapshot = client.post(
        f"/api/projects/{project['id']}/snapshots",
        json={
            "versionId": project["currentVersionId"],
            "conversationId": project["currentConversationId"],
            "imageBase64": "data:image/png;base64,AAAA",
            "source": "test",
        },
    ).json()
    loaded = client.get(f"/api/projects/{project['id']}/snapshots/{snapshot['id']}").json()
    assert loaded["imageBase64"] is None
    assert loaded["mimeType"] == "image/png"
    assert loaded["byteSize"] == 3
    assert (tmp_path / "projects" / project["id"] / "snapshots" / loaded["filename"]).exists()
    assert client.get(f"/api/projects/{project['id']}/snapshots").json()[0]["id"] == snapshot["id"]

    delete_response = client.delete(f"/api/projects/{project['id']}/snapshots/{snapshot['id']}")
    assert delete_response.json()["ok"] is True
    assert client.get(f"/api/projects/{project['id']}/snapshots").json() == []
    assert not (tmp_path / "projects" / project["id"] / "snapshots" / loaded["filename"]).exists()


def test_cleanup_review_snapshots_only_removes_review_sources(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]

    keep = client.post(
        f"/api/projects/{project['id']}/snapshots",
        json={
            "versionId": project["currentVersionId"],
            "conversationId": project["currentConversationId"],
            "imageBase64": "data:image/png;base64,AAAA",
            "source": "canvas",
        },
    ).json()
    review = client.post(
        f"/api/projects/{project['id']}/snapshots",
        json={
            "versionId": project["currentVersionId"],
            "conversationId": project["currentConversationId"],
            "imageBase64": "data:image/png;base64,AAAA",
            "source": "review",
        },
    ).json()
    angle = client.post(
        f"/api/projects/{project['id']}/snapshots",
        json={
            "versionId": project["currentVersionId"],
            "conversationId": project["currentConversationId"],
            "imageBase64": "data:image/png;base64,AAAA",
            "source": "review-angle",
        },
    ).json()

    response = client.delete(f"/api/projects/{project['id']}/snapshots?source=review")
    assert response.json()["deleted"] == 2
    snapshots = client.get(f"/api/projects/{project['id']}/snapshots").json()
    assert [snapshot["id"] for snapshot in snapshots] == [keep["id"]]
    assert not (tmp_path / "projects" / project["id"] / "snapshots" / review["filename"]).exists()
    assert not (tmp_path / "projects" / project["id"] / "snapshots" / angle["filename"]).exists()


def test_upload_dxf_asset_extracts_entities_and_summary(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    dxf = """0
SECTION
2
ENTITIES
0
LINE
8
walls
10
0
20
0
11
100
21
0
0
CIRCLE
8
holes
10
50
20
50
40
10
0
LWPOLYLINE
8
profile
90
4
70
1
10
0
20
0
10
100
20
0
10
100
20
80
10
0
20
80
0
ENDSEC
0
EOF
"""

    response = client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": ("wall-plan.dxf", dxf.encode("utf-8"), "application/dxf")},
    )

    assert response.status_code == 200
    payload = response.json()
    asset = payload["asset"]
    summary = payload["summary"]
    assert asset["format"] == "dxf"
    assert asset["status"] == "parsed"
    assert summary["entityCounts"]["LINE"] == 1
    assert summary["entityCounts"]["CIRCLE"] == 1
    assert summary["entityCounts"]["LWPOLYLINE"] == 1
    assert "profile" in summary["layers"]
    assert summary["closedProfiles"]
    assert (tmp_path / "projects" / project["id"] / "assets" / asset["id"] / "original.dxf").exists()
    assert client.get(f"/api/projects/{project['id']}/assets").json()[0]["id"] == asset["id"]


def test_upload_stl_asset_stays_reference_mesh(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    stl = """solid cube
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 1 0 0
vertex 0 1 0
endloop
endfacet
endsolid cube
"""

    response = client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": ("cube.stl", stl.encode("utf-8"), "model/stl")},
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["format"] == "stl"
    assert summary["triangleCount"] == 1
    assert any("不会自动展开" in warning for warning in summary["warnings"])


def test_reconstruct_from_asset_writes_version(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    response = client.post(
        f"/api/projects/{project['id']}/assets",
        files={"file": ("line.dxf", b"0\nSECTION\n2\nENTITIES\n0\nLINE\n10\n0\n20\n0\n11\n10\n21\n0\n0\nENDSEC\n0\nEOF\n")},
    )
    asset_id = response.json()["asset"]["id"]

    rebuild = client.post(
        "/api/agent/reconstruct-from-asset",
        json={
            "projectId": project["id"],
            "assetId": asset_id,
            "conversationId": project["currentConversationId"],
            "prompt": "把导入线条重建成一段墙体草图",
            "mode": "reference_rebuild",
        },
    )

    events = _events(rebuild)
    assert "code_write_done" in [event["type"] for event in events]
    assert "render_request" in [event["type"] for event in events]


def test_review_loads_snapshot_file_by_id(tmp_path, monkeypatch):
    models = UnitStubModelRouter()
    client = _client(tmp_path, monkeypatch, models=models)
    project = client.get("/api/projects").json()[0]
    snapshot = client.post(
        f"/api/projects/{project['id']}/snapshots",
        json={
            "versionId": project["currentVersionId"],
            "conversationId": project["currentConversationId"],
            "imageBase64": "data:image/png;base64,AAAA",
            "source": "review",
        },
    ).json()

    response = client.post(
        "/api/agent/review",
        json={
            "projectId": project["id"],
            "versionId": project["currentVersionId"],
            "snapshotId": snapshot["id"],
            "reviewMode": "review",
            "userRequirement": "审查当前画布",
        },
    )

    events = _events(response)
    assert "vision_review" in [event["type"] for event in events]
    assert models.last_review_image_base64 == "data:image/png;base64,AAAA"
    assert "生成一个适合高寒地区临建模块" in (models.last_review_requirement_context or "")
    assert models.last_review_prompt == "审查当前画布"
    assert any(
        event["type"] == "tool_progress" and "已载入当前视角截图" in event.get("message", "")
        for event in events
    )


def test_review_uses_requested_conversation_as_requirement_context(tmp_path, monkeypatch):
    models = UnitStubModelRouter()
    client = _client(tmp_path, monkeypatch, models=models)
    project = client.get("/api/projects").json()[0]
    conversation = client.post(
        f"/api/projects/{project['id']}/conversations",
        json={"title": "机械轴承对话"},
    ).json()
    client.post(
        "/api/agent/chat",
        json={
            "projectId": project["id"],
            "conversationId": conversation["id"],
            "message": "生成一个机械多层轴承套筒，包含同心圆环、滚珠和右侧剖切块",
        },
    )

    response = client.post(
        "/api/agent/review",
        json={
            "projectId": project["id"],
            "versionId": client.get(f"/api/projects/{project['id']}/versions").json()[0]["id"],
            "conversationId": conversation["id"],
            "snapshotBase64": "data:image/png;base64,AAAA",
            "reviewMode": "review",
        },
    )

    events = _events(response)
    assert "vision_review" in [event["type"] for event in events]
    assert "机械多层轴承套筒" in (models.last_review_requirement_context or "")
    assert "高寒建筑草图" not in (models.last_review_prompt or "")


def test_first_render_failure_creates_repair_version(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    failed_version_id = project["currentVersionId"]

    response = client.post(
        "/api/agent/render-result",
        json={
            "ok": False,
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "versionId": failed_version_id,
            "autoRepairAttempt": 0,
            "error": {"kind": "api", "message": "cubiod is not a function"},
        },
    )

    events = _events(response)
    event_types = [event["type"] for event in events]
    assert event_types == [
        "render_error",
        "repair_start",
        "provider_status",
        "repair_decision",
        "code_patch",
        "code_write_start",
        "code_write_done",
        "repair_done",
        "render_request",
    ]
    versions = client.get(f"/api/projects/{project['id']}/versions").json()
    failed_version = next(item for item in versions if item["id"] == failed_version_id)
    repair_version = next(item for item in versions if item["id"] == events[6]["versionId"])
    assert failed_version["status"] == "error"
    assert repair_version["status"] == "draft"


def test_second_render_failure_stops_repair(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    version_id = project["currentVersionId"]

    response = client.post(
        "/api/agent/render-result",
        json={
            "ok": False,
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "versionId": version_id,
            "autoRepairAttempt": 1,
            "error": {"kind": "render", "message": "still failed"},
        },
    )

    events = _events(response)
    assert [event["type"] for event in events] == [
        "render_error",
        "repair_start",
        "provider_status",
        "repair_decision",
        "code_patch",
        "code_write_start",
        "code_write_done",
        "repair_done",
        "render_request",
    ]
    version = next(item for item in client.get(f"/api/projects/{project['id']}/versions").json() if item["id"] == version_id)
    assert version["status"] == "error"


def test_eighth_render_failure_requires_user_action(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    version_id = project["currentVersionId"]

    response = client.post(
        "/api/agent/render-result",
        json={
            "ok": False,
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "versionId": version_id,
            "autoRepairAttempt": 8,
            "error": {"kind": "render", "message": "still failed"},
        },
    )

    events = _events(response)
    assert [event["type"] for event in events] == ["render_error", "user_action_required", "repair_stopped", "done"]


def test_review_accepts_snapshot_and_returns_structured_report(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]

    response = client.post(
        "/api/agent/review",
        json={
            "projectId": project["id"],
            "versionId": project["currentVersionId"],
            "snapshotBase64": "data:image/png;base64,AAAA",
            "reviewMode": "review",
            "userRequirement": "审查当前画布",
        },
    )

    events = _events(response)
    review_event = next(event for event in events if event["type"] == "vision_review")
    assert review_event["provider"] == "test-only"
    review = review_event["report"]
    assert review["requirementMatch"]
    assert review["codeDesignBugs"]
    assert review["observations"]
    assert review["suggestedFixes"]
    assert review["evidence"]


def test_missing_vision_returns_visible_error(tmp_path, monkeypatch):
    client = _client(
        tmp_path,
        monkeypatch,
        models=UnitStubModelRouter(vision_error="视觉模型未配置：请设置 CADX_LLM_VISION_API_KEY 后再审图。"),
        project_dir_name="vision-projects",
    )
    project = client.get("/api/projects").json()[0]

    response = client.post(
        "/api/agent/review",
        json={
            "projectId": project["id"],
            "versionId": project["currentVersionId"],
            "snapshotBase64": "data:image/png;base64,AAAA",
            "reviewMode": "review",
            "userRequirement": "审查当前画布",
        },
    )

    events = _events(response)
    assert "vision_review" not in [event["type"] for event in events]
    assert "model_error" in [event["type"] for event in events]
    assert "user_action_required" in [event["type"] for event in events]


def test_vision_timeout_returns_visible_error(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "PROGRESS_HEARTBEAT_SECONDS", 0.1)
    client = _client(
        tmp_path,
        monkeypatch,
        models=TimeoutVisionStubModelRouter(),
        project_dir_name="vision-timeout-projects",
    )
    project = client.get("/api/projects").json()[0]

    response = client.post(
        "/api/agent/review",
        json={
            "projectId": project["id"],
            "versionId": project["currentVersionId"],
            "snapshotBase64": "data:image/png;base64,AAAA",
            "reviewMode": "review",
            "userRequirement": "审查当前画布",
        },
    )

    events = _events(response)
    assert "vision_review" not in [event["type"] for event in events]
    assert "provider_status" in [event["type"] for event in events]
    assert any("视觉模型审图超时" in event.get("message", "") for event in events)
    assert not any(
        event["type"] == "tool_progress" and "已等待 1 秒" in event.get("message", "")
        for event in events
    )


def test_sample_project_uses_bounded_rich_cold_region_code(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    project = client.get("/api/projects").json()[0]
    version = client.get(f"/api/projects/{project['id']}/versions").json()[0]
    code = version["code"]
    assert "length: 2600" in code
    assert "3000-unit visualization envelope" in code
    assert "frostDepth" in code
    assert "entry vestibule" in code
    assert "12000" not in code


def test_new_project_starts_without_code_version(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    project = client.post(
        "/api/projects",
        json={"name": "真实 AI 空项目", "description": "等待真实 AI 生成", "region": "高寒地区"},
    ).json()

    assert project["currentVersionId"] == ""
    assert client.get(f"/api/projects/{project['id']}/versions").json() == []


def test_default_model_timeout_is_thirty_minutes(monkeypatch):
    monkeypatch.delenv("CADX_LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("CADX_LLM_VISION_TIMEOUT_SECONDS", raising=False)
    assert load_app_config().llm_timeout_seconds == 1800
    assert load_app_config().vision_timeout_seconds == 120


def test_slow_generation_emits_progress_heartbeat(tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "PROGRESS_HEARTBEAT_SECONDS", 0.1)
    client = _client(tmp_path, monkeypatch, models=SlowUnitStubModelRouter())
    project = client.get("/api/projects").json()[0]

    response = client.post(
        "/api/agent/chat",
        json={
            "projectId": project["id"],
            "conversationId": project["currentConversationId"],
            "message": "生成 JSCAD",
        },
    )

    events = _events(response)
    assert any(event["type"] == "tool_progress" and event.get("tool") == "deepseek_jscad_generator" for event in events)
    assert "code_write_done" in [event["type"] for event in events]


def test_cancelled_generation_does_not_write_version(tmp_path):
    async def run() -> list[str]:
        store = FileProjectStore(tmp_path / "cancel-projects")
        project = store.create_sample_project()
        orchestrator = CadOrchestrator(store, SkillProvider(api_main.config.project_root), SlowUnitStubModelRouter())
        original_version_ids = [version.id for version in store.list_versions(project.id)]
        stream = orchestrator.chat(
            ChatRequest(
                projectId=project.id,
                conversationId=project.currentConversationId,
                message="生成 JSCAD",
            )
        )
        await stream.__anext__()
        await stream.aclose()
        return [version.id for version in store.list_versions(project.id)], original_version_ids

    version_ids, original_version_ids = asyncio.run(run())
    assert version_ids == original_version_ids
