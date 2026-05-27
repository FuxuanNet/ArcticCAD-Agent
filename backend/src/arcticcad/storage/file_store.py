from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from typing import Literal

from arcticcad.domain import (
    AssetSummary,
    CadAsset,
    ChatMessage,
    CodeVersion,
    Conversation,
    CreateProjectInput,
    JscadRunResult,
    Project,
    SnapshotInput,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


INITIAL_JSCAD = """const { cuboid, cylinder } = require('@jscad/modeling').primitives
const { translate, rotateX } = require('@jscad/modeling').transforms
const { union, subtract } = require('@jscad/modeling').booleans

const params = {
  realSizeNote: 'Prototype represents an 8.4m x 4.2m module scaled to fit a 3000-unit visualization envelope.',
  visualScale: 2600 / 8400,
  length: 2600,
  width: 1300,
  wallHeight: 930,
  roofRise: 300,
  wallThickness: 75,
  insulationThickness: 60,
  pileRadius: 60,
  pileHeight: 600,
  frostDepth: 430,
  vestibuleDepth: 400,
}

function part(name, shape) {
  shape.properties = { ...(shape.properties || {}), name }
  return shape
}

function createCabinShell() {
  const outer = cuboid({ size: [params.length, params.width, params.wallHeight] })
  const inner = translate(
    [0, 0, params.wallThickness],
    cuboid({
      size: [
        params.length - params.wallThickness * 2,
        params.width - params.wallThickness * 2,
        params.wallHeight,
      ],
    }),
  )
  return part('insulated cabin shell', subtract(outer, inner))
}

function createInsulationBand() {
  return part(
    'visible exterior insulation layer',
    translate([0, 0, 80], cuboid({
      size: [
        params.length + params.insulationThickness * 2,
        params.width + params.insulationThickness * 2,
        params.wallHeight - 160,
      ],
    })),
  )
}

function createSnowShedRoof() {
  const deck = translate(
    [0, 0, params.wallHeight + params.roofRise * 0.35],
    cuboid({ size: [params.length + 200, params.width + 170, 75] }),
  )
  const leftSlope = translate(
    [0, -params.width * 0.26, params.wallHeight + params.roofRise * 0.62],
    rotateX(-0.24, cuboid({ size: [params.length + 250, params.width * 0.58, 60] })),
  )
  const rightSlope = translate(
    [0, params.width * 0.26, params.wallHeight + params.roofRise * 0.62],
    rotateX(0.24, cuboid({ size: [params.length + 250, params.width * 0.58, 60] })),
  )
  const ridge = translate([0, 0, params.wallHeight + params.roofRise], cuboid({ size: [params.length + 270, 55, 55] }))
  return [part('snow shedding sloped roof deck', deck), part('left roof snow slope', leftSlope), part('right roof snow slope', rightSlope), part('roof ridge / snow split line', ridge)]
}

function createPileFoundation() {
  return [
    [-1100, -500],
    [0, -500],
    [1100, -500],
    [-1100, 500],
    [0, 500],
    [1100, 500],
  ].map(([x, y]) =>
    part('anti-frost pile foundation', translate([x, y, -params.pileHeight / 2], cylinder({ radius: params.pileRadius, height: params.pileHeight, segments: 24 }))),
  )
}

function createFrostDepthReference() {
  return part(
    'frost depth reference plane',
    translate([0, 0, -params.frostDepth], cuboid({ size: [params.length + 300, params.width + 300, 12] })),
  )
}

function createEntryAndWindBuffer() {
  const vestibule = translate(
    [-params.length / 2 - params.vestibuleDepth / 2, 0, 300],
    cuboid({ size: [params.vestibuleDepth, 500, 600] }),
  )
  const baffleA = translate([-params.length / 2 - 215, -380, 365], cuboid({ size: [300, 40, 730] }))
  const baffleB = translate([-params.length / 2 - 215, 380, 365], cuboid({ size: [300, 40, 730] }))
  return [part('entry vestibule buffer', vestibule), part('wind baffle north', baffleA), part('wind baffle south', baffleB)]
}

function main() {
  return union(
    createInsulationBand(),
    createCabinShell(),
    ...createSnowShedRoof(),
    ...createPileFoundation(),
    createFrostDepthReference(),
    ...createEntryAndWindBuffer(),
  )
}

module.exports = { main }
"""


class FileProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        return self.root / project_id

    def _json_path(self, project_id: str, name: str) -> Path:
        return self._project_dir(project_id) / name

    def _snapshot_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "snapshots"

    def _asset_dir(self, project_id: str, asset_id: str) -> Path:
        return self._project_dir(project_id) / "assets" / asset_id

    @staticmethod
    def _read_list(path: Path) -> list[dict]:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def list_projects(self) -> list[Project]:
        projects: list[Project] = []
        for path in sorted(self.root.glob("*/metadata.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            projects.append(Project.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        if not projects:
            projects.append(self.create_sample_project())
        return projects

    def create_sample_project(self) -> Project:
        project_id = new_id("project")
        version_id = new_id("version")
        conversation_id = new_id("conversation")
        project_dir = self._project_dir(project_id)
        now = utc_now()
        project = Project(
            id=project_id,
            name="高寒临建模块示例",
            description="可继续编辑的后端示例项目。",
            region="黑龙江",
            updatedAt=now,
            currentVersionId=version_id,
            currentConversationId=conversation_id,
        )
        version = CodeVersion(
            id=version_id,
            projectId=project_id,
            label="v1",
            summary="示例初始版本。",
            code=INITIAL_JSCAD,
            createdAt=now,
            status="draft",
        )
        conversation = Conversation(
            id=conversation_id,
            projectId=project_id,
            title="示例对话",
            messageCount=2,
            updatedAt=now,
        )
        messages = [
            ChatMessage(
                id=new_id("message"),
                conversationId=conversation_id,
                role="user",
                content="生成一个适合高寒地区临建模块的 3D 草图，包含主体、桩基础和后续可扩展的屋面表达。",
                createdAt=now,
            ),
            ChatMessage(
                id=new_id("message"),
                conversationId=conversation_id,
                role="assistant",
                content="已创建可运行的 JSCAD 示例版本，包含主体体块和桩基础。你可以继续在这个对话中要求增加坡屋面、保温层或冻深参考线。",
                createdAt=now,
            ),
        ]
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.js").write_text(INITIAL_JSCAD, encoding="utf-8")
        self._write_json(project_dir / "metadata.json", project.model_dump(mode="json"))
        self._write_json(project_dir / "versions.json", [version.model_dump(mode="json")])
        self._write_json(project_dir / "conversations.json", [conversation.model_dump(mode="json")])
        self._write_json(project_dir / "messages.json", [message.model_dump(mode="json") for message in messages])
        self._write_json(project_dir / "runs.json", [])
        self._write_json(project_dir / "snapshots.json", [])
        self._write_json(project_dir / "assets.json", [])
        return project

    def create_project(self, data: CreateProjectInput) -> Project:
        project_id = new_id("project")
        conversation_id = new_id("conversation")
        project_dir = self._project_dir(project_id)
        now = utc_now()
        project = Project(
            id=project_id,
            name=data.name,
            description=data.description or "高寒建筑草图项目。",
            region=data.region or "高寒地区",
            updatedAt=now,
            currentVersionId="",
            currentConversationId=conversation_id,
        )
        conversation = Conversation(
            id=conversation_id,
            projectId=project_id,
            title="新建对话",
            messageCount=0,
            updatedAt=now,
        )
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.js").write_text("", encoding="utf-8")
        self._write_json(project_dir / "metadata.json", project.model_dump(mode="json"))
        self._write_json(project_dir / "versions.json", [])
        self._write_json(project_dir / "conversations.json", [conversation.model_dump(mode="json")])
        self._write_json(project_dir / "messages.json", [])
        self._write_json(project_dir / "runs.json", [])
        self._write_json(project_dir / "snapshots.json", [])
        self._write_json(project_dir / "assets.json", [])
        return project

    def get_project(self, project_id: str) -> Project:
        path = self._json_path(project_id, "metadata.json")
        if not path.exists():
            raise KeyError(project_id)
        return Project.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def save_project(self, project: Project) -> None:
        self._write_json(self._json_path(project.id, "metadata.json"), project.model_dump(mode="json"))

    def list_versions(self, project_id: str) -> list[CodeVersion]:
        return [CodeVersion.model_validate(item) for item in self._read_list(self._json_path(project_id, "versions.json"))]

    def list_conversations(self, project_id: str) -> list[Conversation]:
        return [
            Conversation.model_validate(item)
            for item in self._read_list(self._json_path(project_id, "conversations.json"))
        ]

    def create_conversation(self, project_id: str, title: str = "新建对话") -> Conversation:
        conversation = Conversation(
            id=new_id("conversation"),
            projectId=project_id,
            title=title,
            messageCount=0,
            updatedAt=utc_now(),
        )
        conversations = self._read_list(self._json_path(project_id, "conversations.json"))
        conversations.insert(0, conversation.model_dump(mode="json"))
        self._write_json(self._json_path(project_id, "conversations.json"), conversations)
        project = self.get_project(project_id)
        self.save_project(project.model_copy(update={"currentConversationId": conversation.id, "updatedAt": utc_now()}))
        return conversation

    def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        for project in self.list_projects():
            messages = [
                ChatMessage.model_validate(item)
                for item in self._read_list(self._json_path(project.id, "messages.json"))
            ]
            matched = [message for message in messages if message.conversationId == conversation_id]
            if matched:
                return matched
        return []

    def add_message(self, project_id: str, conversation_id: str, role: str, content: str) -> ChatMessage:
        message = ChatMessage(
            id=new_id("message"),
            conversationId=conversation_id,
            role=role,  # type: ignore[arg-type]
            content=content,
            createdAt=utc_now(),
        )
        path = self._json_path(project_id, "messages.json")
        messages = self._read_list(path)
        messages.append(message.model_dump(mode="json"))
        self._write_json(path, messages)

        conversations = self.list_conversations(project_id)
        updated = []
        for conversation in conversations:
            if conversation.id == conversation_id:
                conversation = conversation.model_copy(
                    update={"messageCount": conversation.messageCount + 1, "updatedAt": utc_now()}
                )
            updated.append(conversation.model_dump(mode="json"))
        self._write_json(self._json_path(project_id, "conversations.json"), updated)
        return message

    def set_current_conversation(self, project_id: str, conversation_id: str) -> None:
        project = self.get_project(project_id)
        self.save_project(project.model_copy(update={"currentConversationId": conversation_id, "updatedAt": utc_now()}))

    def save_code_version(self, project_id: str, code: str, summary: str) -> CodeVersion:
        versions = self.list_versions(project_id)
        version = CodeVersion(
            id=new_id("version"),
            projectId=project_id,
            label=f"v{len(versions) + 1}",
            summary=summary,
            code=code,
            createdAt=utc_now(),
            status="draft",
        )
        versions.insert(0, version)
        self._write_json(
            self._json_path(project_id, "versions.json"),
            [item.model_dump(mode="json") for item in versions],
        )
        project_dir = self._project_dir(project_id)
        (project_dir / "main.js").write_text(code, encoding="utf-8")
        project = self.get_project(project_id)
        self.save_project(project.model_copy(update={"currentVersionId": version.id, "updatedAt": utc_now()}))
        return version

    def find_project_for_version(self, version_id: str) -> tuple[Project, CodeVersion]:
        for project in self.list_projects():
            for version in self.list_versions(project.id):
                if version.id == version_id:
                    return project, version
        raise KeyError(version_id)

    def update_version_status(
        self,
        project_id: str,
        version_id: str,
        status: Literal["draft", "rendered", "error", "reviewed"],
    ) -> CodeVersion:
        versions = self.list_versions(project_id)
        updated: list[CodeVersion] = []
        matched: CodeVersion | None = None
        for version in versions:
            if version.id == version_id:
                version = version.model_copy(update={"status": status})
                matched = version
            updated.append(version)
        if matched is None:
            raise KeyError(version_id)
        self._write_json(
            self._json_path(project_id, "versions.json"),
            [item.model_dump(mode="json") for item in updated],
        )
        project = self.get_project(project_id)
        self.save_project(project.model_copy(update={"updatedAt": utc_now()}))
        return matched

    def save_repair_version(self, project_id: str, code: str, summary: str) -> CodeVersion:
        return self.save_code_version(project_id, code, summary)

    def save_render_result(self, result: JscadRunResult) -> Project:
        if result.projectId:
            project = self.get_project(result.projectId)
        else:
            project, _ = self.find_project_for_version(result.versionId)

        path = self._json_path(project.id, "runs.json")
        runs = self._read_list(path)
        runs.insert(0, {"createdAt": utc_now(), **result.model_dump(mode="json")})
        self._write_json(path, runs)
        return project

    def list_runs(self, project_id: str) -> list[dict]:
        return self._read_list(self._json_path(project_id, "runs.json"))

    @staticmethod
    def _decode_data_url(data_url: str) -> tuple[str, bytes, str]:
        if not data_url.startswith("data:") or ";base64," not in data_url:
            raise ValueError("Snapshot image must be a base64 data URL.")
        header, encoded = data_url.split(",", 1)
        mime = header.removeprefix("data:").split(";", 1)[0] or "image/png"
        extension = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/webp": "webp",
        }.get(mime, "bin")
        return mime, base64.b64decode(encoded), extension

    def snapshot_data_url(self, project_id: str, snapshot_id: str) -> str:
        snapshot = self.get_snapshot(project_id, snapshot_id)
        if snapshot.get("imageBase64"):
            return str(snapshot["imageBase64"])
        filename = snapshot.get("filename")
        mime = str(snapshot.get("mimeType") or "image/png")
        if not filename:
            raise KeyError(snapshot_id)
        image_path = self._snapshot_dir(project_id) / str(filename)
        if not image_path.exists():
            raise KeyError(snapshot_id)
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    def save_snapshot(self, project_id: str, data: SnapshotInput) -> dict:
        snapshot_id = new_id("snapshot")
        mime, image_bytes, extension = self._decode_data_url(data.imageBase64)
        filename = f"{snapshot_id}.{extension}"
        image_path = self._snapshot_dir(project_id) / filename
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(image_bytes)
        snapshot = {
            "id": snapshot_id,
            "projectId": project_id,
            "versionId": data.versionId,
            "conversationId": data.conversationId,
            "filename": filename,
            "mimeType": mime,
            "byteSize": len(image_bytes),
            "imageBase64": None,
            "source": data.source,
            "camera": data.camera,
            "note": data.note,
            "createdAt": utc_now(),
        }
        path = self._json_path(project_id, "snapshots.json")
        snapshots = self._read_list(path)
        snapshots.insert(0, snapshot)
        self._write_json(path, snapshots)
        return snapshot

    def get_snapshot(self, project_id: str, snapshot_id: str) -> dict:
        for snapshot in self._read_list(self._json_path(project_id, "snapshots.json")):
            if snapshot.get("id") == snapshot_id:
                return snapshot
        raise KeyError(snapshot_id)

    def list_snapshots(self, project_id: str) -> list[dict]:
        return self._read_list(self._json_path(project_id, "snapshots.json"))

    def delete_snapshot(self, project_id: str, snapshot_id: str) -> None:
        path = self._json_path(project_id, "snapshots.json")
        snapshots = self._read_list(path)
        kept: list[dict] = []
        matched: dict | None = None
        for snapshot in snapshots:
            if snapshot.get("id") == snapshot_id:
                matched = snapshot
            else:
                kept.append(snapshot)
        if matched is None:
            raise KeyError(snapshot_id)
        filename = matched.get("filename")
        if filename:
            image_path = self._snapshot_dir(project_id) / str(filename)
            if image_path.exists():
                image_path.unlink()
        self._write_json(path, kept)

    def delete_review_snapshots(self, project_id: str) -> int:
        self.get_project(project_id)
        deleted = 0
        for snapshot in list(self._read_list(self._json_path(project_id, "snapshots.json"))):
            if snapshot.get("source") in {"review", "review-angle"}:
                self.delete_snapshot(project_id, str(snapshot.get("id")))
                deleted += 1
        return deleted

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename).name.strip() or "asset"
        return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name)[:120] or "asset"

    def save_asset_upload(self, project_id: str, filename: str, content: bytes) -> CadAsset:
        self.get_project(project_id)
        safe_name = self._safe_filename(filename)
        suffix = Path(safe_name).suffix.lower().lstrip(".")
        if suffix not in {"dxf", "stl"}:
            raise ValueError("Only DXF and STL files are supported.")
        asset_id = new_id("asset")
        asset_dir = self._asset_dir(project_id, asset_id)
        asset_dir.mkdir(parents=True, exist_ok=True)
        original_name = f"original.{suffix}"
        original_path = asset_dir / original_name
        original_path.write_bytes(content)
        now = utc_now()
        asset = CadAsset(
            id=asset_id,
            projectId=project_id,
            filename=safe_name,
            format=suffix,  # type: ignore[arg-type]
            status="uploaded",
            byteSize=len(content),
            originalPath=f"assets/{asset_id}/{original_name}",
            createdAt=now,
            updatedAt=now,
        )
        self._write_asset(project_id, asset)
        return asset

    def _write_asset(self, project_id: str, asset: CadAsset) -> None:
        asset_dir = self._asset_dir(project_id, asset.id)
        self._write_json(asset_dir / "metadata.json", asset.model_dump(mode="json"))
        assets = [CadAsset.model_validate(item) for item in self._read_list(self._json_path(project_id, "assets.json"))]
        updated = [item for item in assets if item.id != asset.id]
        updated.insert(0, asset)
        self._write_json(self._json_path(project_id, "assets.json"), [item.model_dump(mode="json") for item in updated])

    def update_asset_parse_result(
        self,
        project_id: str,
        asset_id: str,
        *,
        summary: AssetSummary | None = None,
        raw_script: str | None = None,
        error: str | None = None,
    ) -> CadAsset:
        asset = self.get_asset(project_id, asset_id)
        asset_dir = self._asset_dir(project_id, asset_id)
        summary_path: str | None = asset.summaryPath
        raw_script_path: str | None = asset.rawScriptPath
        if raw_script is not None:
            (asset_dir / "converted.raw.js").write_text(raw_script, encoding="utf-8")
            raw_script_path = f"assets/{asset_id}/converted.raw.js"
        if summary is not None:
            if raw_script_path and not summary.rawScriptPath:
                summary = summary.model_copy(update={"rawScriptPath": raw_script_path})
            self._write_json(asset_dir / "summary.json", summary.model_dump(mode="json"))
            summary_path = f"assets/{asset_id}/summary.json"
        status = "parsed" if summary is not None and error is None else "parse_error"
        updated = asset.model_copy(
            update={
                "status": status,
                "summaryPath": summary_path,
                "rawScriptPath": raw_script_path,
                "error": error,
                "updatedAt": utc_now(),
            }
        )
        self._write_asset(project_id, updated)
        return updated

    def list_assets(self, project_id: str) -> list[CadAsset]:
        self.get_project(project_id)
        return [CadAsset.model_validate(item) for item in self._read_list(self._json_path(project_id, "assets.json"))]

    def get_asset(self, project_id: str, asset_id: str) -> CadAsset:
        metadata_path = self._asset_dir(project_id, asset_id) / "metadata.json"
        if metadata_path.exists():
            return CadAsset.model_validate(json.loads(metadata_path.read_text(encoding="utf-8")))
        for asset in self.list_assets(project_id):
            if asset.id == asset_id:
                return asset
        raise KeyError(asset_id)

    def get_asset_summary(self, project_id: str, asset_id: str) -> AssetSummary | None:
        summary_path = self._asset_dir(project_id, asset_id) / "summary.json"
        if not summary_path.exists():
            return None
        return AssetSummary.model_validate(json.loads(summary_path.read_text(encoding="utf-8")))

    def asset_content_path(self, project_id: str, asset_id: str, kind: str = "original") -> Path:
        asset = self.get_asset(project_id, asset_id)
        if kind == "raw":
            if not asset.rawScriptPath:
                raise KeyError(asset_id)
            return self._project_dir(project_id) / asset.rawScriptPath
        return self._project_dir(project_id) / asset.originalPath
