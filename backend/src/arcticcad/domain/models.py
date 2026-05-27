from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    description: str
    region: str
    status: Literal["active", "archived"] = "active"
    updatedAt: str
    currentVersionId: str
    currentConversationId: str


class CodeVersion(BaseModel):
    id: str
    projectId: str
    label: str
    summary: str
    code: str
    createdAt: str
    status: Literal["draft", "rendered", "error", "reviewed"] = "draft"


class AssetEntitySummary(BaseModel):
    id: str
    type: str
    layer: str | None = None
    points: list[list[float]] = Field(default_factory=list)
    center: list[float] | None = None
    radius: float | None = None
    startAngle: float | None = None
    endAngle: float | None = None
    closed: bool = False
    bounds: dict[str, list[float]] | None = None


class AssetSummary(BaseModel):
    format: Literal["dxf", "stl"]
    units: str | None = None
    bounds: dict[str, list[float]] | None = None
    layers: list[str] = Field(default_factory=list)
    entityCounts: dict[str, int] = Field(default_factory=dict)
    entities: list[AssetEntitySummary] = Field(default_factory=list)
    closedProfiles: list[dict[str, Any]] = Field(default_factory=list)
    triangleCount: int | None = None
    solidCount: int | None = None
    isLikelyWatertight: bool | None = None
    warnings: list[str] = Field(default_factory=list)
    rawScriptPath: str | None = None


class CadAsset(BaseModel):
    id: str
    projectId: str
    filename: str
    format: Literal["dxf", "stl"]
    status: Literal["uploaded", "parsed", "parse_error"] = "uploaded"
    byteSize: int
    originalPath: str
    summaryPath: str | None = None
    rawScriptPath: str | None = None
    createdAt: str
    updatedAt: str
    error: str | None = None


class Conversation(BaseModel):
    id: str
    projectId: str
    title: str
    messageCount: int = 0
    updatedAt: str


class ChatMessage(BaseModel):
    id: str
    conversationId: str
    role: Literal["user", "assistant", "system"]
    content: str
    createdAt: str


class ReviewRisk(BaseModel):
    level: Literal["low", "medium", "high"]
    category: str
    description: str
    suggestion: str


class ReviewReport(BaseModel):
    summary: str
    risks: list[ReviewRisk] = Field(default_factory=list)
    drawingUnderstanding: str
    requirementMatch: str = ""
    codeDesignBugs: list[str] = Field(default_factory=list)
    coldRegionNotes: list[str] = Field(default_factory=list)
    recommendAutoFix: bool = False
    observations: list[str] = Field(default_factory=list)
    suggestedFixes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class AgentEvent(BaseModel):
    id: str
    type: str
    createdAt: str
    message: str | None = None
    skill: str | None = None
    status: str | None = None
    tool: str | None = None
    inputSummary: str | None = None
    progress: int | None = None
    ok: bool | None = None
    resultSummary: str | None = None
    language: str | None = None
    code: str | None = None
    summary: str | None = None
    target: str | None = None
    versionId: str | None = None
    reason: str | None = None
    errorKind: str | None = None
    stack: str | None = None
    provider: str | None = None
    report: ReviewReport | None = None
    recoverable: bool | None = None
    decision: str | None = None
    intent: str | None = None
    confidence: float | None = None
    error: str | None = None
    assistantMessage: str | None = None


class JscadError(BaseModel):
    kind: Literal["syntax", "api", "geometry", "render", "export"]
    message: str
    stack: str | None = None
    line: int | None = None
    column: int | None = None


class JscadRunResult(BaseModel):
    ok: bool
    versionId: str
    projectId: str | None = None
    conversationId: str | None = None
    autoRepairAttempt: int = 0
    geometrySummary: str | None = None
    error: JscadError | None = None


class ChatRequest(BaseModel):
    projectId: str
    message: str
    currentVersionId: str | None = None
    viewportSnapshotId: str | None = None
    conversationId: str | None = None


class ReviewRequest(BaseModel):
    projectId: str
    versionId: str
    snapshotId: str | None = None
    snapshotBase64: str | None = None
    conversationId: str | None = None
    reviewMode: Literal["review", "observe_for_change"] = "review"
    userRequirement: str | None = None


class CreateProjectInput(BaseModel):
    name: str
    description: str | None = None
    region: str | None = None


class AssetRebuildRequest(BaseModel):
    projectId: str
    assetId: str
    prompt: str
    mode: Literal["reference_rebuild", "direct_insert"] = "reference_rebuild"
    currentVersionId: str | None = None
    conversationId: str | None = None


class SnapshotInput(BaseModel):
    versionId: str
    conversationId: str | None = None
    imageBase64: str
    source: str = "canvas"
    camera: dict[str, Any] | None = None
    note: str | None = None


JsonDict = dict[str, Any]
