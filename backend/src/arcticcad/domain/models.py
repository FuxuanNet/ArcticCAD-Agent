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
    reviewMode: Literal["review", "observe_for_change"] = "review"
    userRequirement: str | None = None


class CreateProjectInput(BaseModel):
    name: str
    description: str | None = None
    region: str | None = None


class SnapshotInput(BaseModel):
    versionId: str
    conversationId: str | None = None
    imageBase64: str
    source: str = "canvas"


JsonDict = dict[str, Any]
