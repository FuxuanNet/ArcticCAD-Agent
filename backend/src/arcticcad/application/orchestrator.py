from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Awaitable, Callable, TypeVar

from arcticcad.domain import AgentEvent, ChatRequest, JscadRunResult, ReviewRequest
from arcticcad.providers import ModelRouter
from arcticcad.skills import SkillProvider
from arcticcad.storage.file_store import FileProjectStore, new_id, utc_now


MAX_AUTO_REPAIR_ATTEMPTS = 8
PROGRESS_HEARTBEAT_SECONDS = 5
ProgressEmitter = Callable[[str], Awaitable[None]]
T = TypeVar("T")


class CadOrchestrator:
    def __init__(self, store: FileProjectStore, skills: SkillProvider, models: ModelRouter) -> None:
        self.store = store
        self.skills = skills
        self.models = models

    def _event(self, event_type: str, **payload: object) -> AgentEvent:
        return AgentEvent(id=new_id("event"), type=event_type, createdAt=utc_now(), **payload)

    async def _run_with_progress(
        self,
        *,
        tool: str,
        waiting_message: str,
        call: Callable[[ProgressEmitter], Awaitable[T]],
    ) -> AsyncIterator[AgentEvent | T]:
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        started = asyncio.get_running_loop().time()
        chunk_count = 0

        async def emit_progress(message: str) -> None:
            nonlocal chunk_count
            if message:
                chunk_count += 1

        async def heartbeat() -> None:
            while True:
                await asyncio.sleep(PROGRESS_HEARTBEAT_SECONDS)
                elapsed = int(asyncio.get_running_loop().time() - started)
                chunk_summary = f"，已收到响应片段 {chunk_count} 个" if chunk_count else ""
                await queue.put(
                    self._event(
                        "tool_progress",
                        tool=tool,
                        progress=None,
                        message=f"{waiting_message}，已等待 {elapsed} 秒{chunk_summary}。",
                    )
                )

        task = asyncio.create_task(call(emit_progress))
        heartbeat_task = asyncio.create_task(heartbeat())
        try:
            while True:
                if task.done():
                    break
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
            heartbeat_task.cancel()
            while not queue.empty():
                yield queue.get_nowait()
            elapsed = asyncio.get_running_loop().time() - started
            if elapsed >= 1:
                yield self._event(
                    "tool_progress",
                    tool=tool,
                    progress=None,
                    message=f"{tool} 已收到完整模型响应，正在解析结果。",
                )
            yield await task
        except asyncio.CancelledError:
            task.cancel()
            heartbeat_task.cancel()
            raise
        finally:
            heartbeat_task.cancel()

    async def chat(self, request: ChatRequest) -> AsyncIterator[AgentEvent]:
        project = self.store.get_project(request.projectId)
        conversation_id = request.conversationId or project.currentConversationId
        self.store.set_current_conversation(request.projectId, conversation_id)
        self.store.add_message(request.projectId, conversation_id, "user", request.message)

        versions = self.store.list_versions(request.projectId)
        current_version = next(
            (version for version in versions if version.id == (request.currentVersionId or project.currentVersionId)),
            versions[0] if versions else None,
        )
        context = {
            "project": project.model_dump(mode="json"),
            "currentVersion": current_version.model_dump(mode="json") if current_version else None,
        }

        yield self._event("thinking", message="正在判断本次消息是否需要生成、修改、审图或普通回复。")
        plan_result = None
        async for item in self._run_with_progress(
            tool="deepseek_agent_planner",
            waiting_message="DeepSeek 正在判断意图",
            call=lambda emit: self.models.plan_intent(prompt=request.message, context=context, on_progress=emit),
        ):
            if isinstance(item, AgentEvent):
                yield item
            else:
                plan_result = item
        assert plan_result is not None
        if plan_result.reasoningContent:
            yield self._event("thinking", provider=plan_result.provider, message=plan_result.reasoningContent)
        if not plan_result.ok or not plan_result.data:
            message = plan_result.error or "Agent planning 失败，未写入新版本。"
            self.store.add_message(request.projectId, conversation_id, "assistant", message)
            yield self._event("model_error", provider=plan_result.provider, message=message, error=message, recoverable=True)
            yield self._event("done", summary="Agent planning 失败，未写入新版本。")
            return

        plan = plan_result.data or {}
        intent = str(plan.get("intent") or "chat")
        assistant_message = str(plan.get("assistantMessage") or "")
        confidence = float(plan.get("confidence") or 0)
        yield self._event(
            "agent_plan",
            intent=intent,
            confidence=confidence,
            provider=plan_result.provider,
            error=plan_result.error,
            message=str(plan.get("reason") or "已完成意图判断。"),
        )

        if intent == "chat":
            reply = assistant_message or "我在。你可以描述要生成的模型、要修改的构件，或让我审查当前画布。"
            self.store.add_message(request.projectId, conversation_id, "assistant", reply)
            yield self._event("assistant_message", assistantMessage=reply, message=reply)
            yield self._event("done", summary="普通对话完成，未写入新版本。")
            return

        if intent == "ask_clarifying_question":
            reply = assistant_message or "请补充要建模的对象、关键构件或尺寸范围，我再生成可靠的 JSCAD 版本。"
            self.store.add_message(request.projectId, conversation_id, "assistant", reply)
            yield self._event("user_action_required", message=reply, reason="信息不足，需要用户补充需求。")
            yield self._event("assistant_message", assistantMessage=reply, message=reply)
            yield self._event("done", summary="已追问用户，未写入新版本。")
            return

        if intent == "review":
            reply = "请点击工作台顶部的“审图”按钮，我会保存当前画布截图并调用视觉模型审查。"
            self.store.add_message(request.projectId, conversation_id, "assistant", reply)
            yield self._event("assistant_message", assistantMessage=reply, message=reply)
            yield self._event("done", summary="已引导用户执行审图。")
            return

        if intent == "run_or_repair":
            reply = assistant_message or "请点击“运行”执行当前 JSCAD；若前端回传错误，我会进入自动修复闭环。"
            self.store.add_message(request.projectId, conversation_id, "assistant", reply)
            yield self._event("assistant_message", assistantMessage=reply, message=reply)
            yield self._event("render_request", reason="用户请求运行当前版本。")
            yield self._event("done", summary="已请求前端运行当前版本。")
            return

        skill, loaded = self.skills.load_skill("jscad-authoring")
        yield self._event(
            "skill_loading",
            skill="jscad-authoring",
            status="done" if loaded else "error",
            message=None if loaded else "未找到 jscad-authoring skill，已停止生成。",
        )
        if not loaded:
            message = "未找到 jscad-authoring skill，不能可靠生成 JSCAD。请修复技能配置后重试。"
            self.store.add_message(request.projectId, conversation_id, "assistant", message)
            yield self._event("model_error", provider="skill", message=message, error=message, recoverable=True)
            yield self._event("done", summary="技能加载失败，未写入新版本。")
            return

        yield self._event("tool_start", tool="deepseek_jscad_generator", inputSummary="生成或修改 JSCAD main.js。")
        result = None
        async for item in self._run_with_progress(
            tool="deepseek_jscad_generator",
            waiting_message="DeepSeek 正在生成 JSCAD",
            call=lambda emit: self.models.complete_code(prompt=request.message, context=context, skill=skill, on_progress=emit),
        ):
            if isinstance(item, AgentEvent):
                yield item
            else:
                result = item
        assert result is not None
        yield self._event(
            "provider_status",
            provider=result.provider,
            ok=result.ok,
            message="正在使用真实文本模型生成代码。",
            error=result.error,
        )
        if result.reasoningContent:
            yield self._event("thinking", provider=result.provider, message=result.reasoningContent)
        if not result.ok or not result.code:
            message = result.error or "模型生成失败，未写入新版本。"
            self.store.add_message(request.projectId, conversation_id, "assistant", message)
            yield self._event("model_error", provider=result.provider, message=message, error=message, recoverable=True)
            yield self._event("done", summary="代码生成失败，未写入新版本。")
            return

        code = result.code
        yield self._event("code_patch", language="jscad", code=code, summary="生成 JSCAD 草图代码。")
        yield self._event("code_write_start", target=f"projects/{request.projectId}/main.js")
        version = self.store.save_code_version(request.projectId, code, "AI 生成 JSCAD 草图。")
        yield self._event(
            "code_write_done",
            target=f"projects/{request.projectId}/main.js",
            versionId=version.id,
        )
        yield self._event("render_request", reason="新版本写入完成，等待前端执行 JSCAD。")
        self.store.add_message(request.projectId, conversation_id, "assistant", "已生成 JSCAD 版本并写入项目工作区。")
        yield self._event("done", summary="代码生成流程完成。")

    async def review(self, request: ReviewRequest) -> AsyncIterator[AgentEvent]:
        yield self._event("thinking", message="正在整理当前代码和高寒审图关注点。")
        versions = self.store.list_versions(request.projectId)
        version = next((item for item in versions if item.id == request.versionId), versions[0] if versions else None)
        image_base64 = request.snapshotBase64
        snapshot_message = "未提供截图，将执行仅代码审图。"
        if request.snapshotId:
            try:
                snapshot = self.store.get_snapshot(request.projectId, request.snapshotId)
                image_base64 = self.store.snapshot_data_url(request.projectId, request.snapshotId)
                byte_size = snapshot.get("byteSize")
                mime_type = snapshot.get("mimeType") or "image"
                size_text = f"{round(int(byte_size) / 1024, 1)} KB" if isinstance(byte_size, int) else "unknown size"
                snapshot_message = f"已载入当前视角截图：{mime_type}，{size_text}。"
            except Exception:
                snapshot_message = "读取截图文件失败，将执行仅代码审图。"
                image_base64 = None
        elif image_base64:
            snapshot_message = f"已收到前端内联截图：约 {round(len(image_base64) / 1024, 1)} KB。"
        yield self._event("tool_progress", tool="qwen_vision_review", progress=None, message=snapshot_message)
        result = None
        async for item in self._run_with_progress(
            tool="qwen_vision_review",
            waiting_message="视觉模型正在审查画布",
            call=lambda emit: self.models.review_image_result(
                prompt=request.userRequirement or "审查当前高寒建筑草图。",
                code=version.code if version else "",
                image_base64=image_base64,
                review_mode=request.reviewMode,
                on_progress=emit,
            ),
        ):
            if isinstance(item, AgentEvent):
                yield item
            else:
                result = item
        assert result is not None
        yield self._event(
            "provider_status",
            provider=result.provider,
            ok=result.ok,
            message="正在调用视觉模型审图。",
            error=result.error,
        )
        if result.reasoningContent:
            yield self._event("thinking", provider=result.provider, message=result.reasoningContent)
        if not result.ok or not result.data:
            message = result.error or "视觉模型审图失败。"
            yield self._event("model_error", provider=result.provider, message=message, error=message, recoverable=True)
            yield self._event("user_action_required", message=message, reason=message)
            yield self._event("done", summary="审图失败，未生成报告。")
            return

        from arcticcad.domain import ReviewReport

        report = ReviewReport.model_validate(result.data)
        yield self._event("vision_review", provider=result.provider, report=report)
        yield self._event("done", summary="审图报告已生成。")

    def _error_signature(self, result: JscadRunResult) -> str:
        if not result.error:
            return "unknown:"
        return f"{result.error.kind}:{result.error.message[:160]}"

    def _recent_repair_history(self, project_id: str, current_code: str, result: JscadRunResult) -> list[dict]:
        versions = self.store.list_versions(project_id)
        return [
            {
                "versionId": version.id,
                "status": version.status,
                "summary": version.summary,
                "sameCode": version.code.strip() == current_code.strip(),
            }
            for version in versions[:8]
        ] + [{"errorSignature": self._error_signature(result), "attempt": result.autoRepairAttempt}]

    async def submit_render_result_stream(self, result: JscadRunResult) -> AsyncIterator[AgentEvent]:
        project = self.store.save_render_result(result)
        _, version = self.store.find_project_for_version(result.versionId)

        if result.conversationId:
            self.store.set_current_conversation(project.id, result.conversationId)

        if result.ok:
            self.store.update_version_status(project.id, result.versionId, "rendered")
            yield self._event(
                "tool_result",
                tool="browser_jscad_runner",
                ok=True,
                resultSummary=result.geometrySummary or "JSCAD returned geometry.",
            )
            yield self._event("done", summary="JSCAD 运行成功，版本已标记为 rendered。")
            return

        self.store.update_version_status(project.id, result.versionId, "error")
        yield self._event(
            "render_error",
            errorKind=result.error.kind if result.error else "render",
            message=result.error.message if result.error else "JSCAD render failed.",
            stack=result.error.stack if result.error else None,
        )

        if result.autoRepairAttempt >= MAX_AUTO_REPAIR_ATTEMPTS:
            reason = f"自动修复已达到 {MAX_AUTO_REPAIR_ATTEMPTS} 轮，需要用户确认是否继续。"
            yield self._event("user_action_required", message=reason, reason=reason)
            yield self._event("repair_stopped", reason=reason)
            yield self._event("done", summary="自动修复暂停。")
            return

        versions = self.store.list_versions(project.id)
        errored_versions = [item for item in versions if item.status == "error"]
        if len(errored_versions) >= 2 and errored_versions[0].code.strip() == errored_versions[1].code.strip():
            reason = "连续修复版本代码无实质变化，自动修复暂停。"
            yield self._event("repair_decision", decision="needs_user_input", reason=reason)
            yield self._event("user_action_required", message=reason, reason=reason)
            yield self._event("repair_stopped", reason=reason)
            yield self._event("done", summary="自动修复暂停。")
            return

        yield self._event("repair_start", reason=f"第 {result.autoRepairAttempt + 1} 轮 JSCAD 自动修复开始。")
        skill, loaded = self.skills.load_skill("jscad-authoring")
        if not loaded:
            reason = "未找到 jscad-authoring skill，不能可靠执行自动修复。请修复技能配置后重试。"
            yield self._event("repair_decision", decision="needs_user_input", reason=reason)
            yield self._event("user_action_required", message=reason, reason=reason)
            yield self._event("repair_stopped", reason=reason)
            yield self._event("done", summary="自动修复暂停。")
            return
        messages = self.store.list_messages(result.conversationId or project.currentConversationId)
        last_user_message = next((message.content for message in reversed(messages) if message.role == "user"), "")
        repair_history = self._recent_repair_history(project.id, version.code, result)
        same_error_count = sum(
            1
            for item in repair_history
            if isinstance(item, dict) and item.get("errorSignature") == self._error_signature(result)
        )
        if same_error_count >= 2:
            repair_history.append(
                {
                    "warning": "The same error signature has appeared repeatedly. Decide whether repair still has value.",
                }
            )

        repair_result = None
        async for item in self._run_with_progress(
            tool="deepseek_jscad_repair",
            waiting_message="DeepSeek 正在修复 JSCAD",
            call=lambda emit: self.models.repair_code(
                user_requirement=last_user_message,
                current_code=version.code,
                run_result=result,
                skill=skill,
                repair_history=repair_history,
                on_progress=emit,
            ),
        ):
            if isinstance(item, AgentEvent):
                yield item
            else:
                repair_result = item
        assert repair_result is not None
        yield self._event(
            "provider_status",
            provider=repair_result.provider,
            ok=repair_result.ok,
            message="正在使用真实文本模型修复代码。",
            error=repair_result.error,
        )
        if repair_result.reasoningContent:
            yield self._event("thinking", provider=repair_result.provider, message=repair_result.reasoningContent)
        if not repair_result.ok or not repair_result.data:
            reason = repair_result.error or "修复模型调用失败，自动修复暂停。"
            yield self._event("repair_decision", decision="needs_user_input", reason=reason)
            yield self._event("user_action_required", message=reason, reason=reason)
            yield self._event("repair_stopped", reason=reason)
            yield self._event("done", summary="自动修复暂停。")
            return

        repair = repair_result.data
        decision = str(repair.get("decision") or "continue")
        reason = str(repair.get("reason") or "模型生成修复版本。")
        yield self._event("repair_decision", decision=decision, reason=reason)
        if decision in {"stop_repair", "needs_user_input"}:
            yield self._event("user_action_required", message=reason, reason=reason)
            yield self._event("repair_stopped", reason=reason)
            yield self._event("done", summary="自动修复暂停。")
            return

        repaired_code = str(repair.get("code") or "")
        if not repaired_code.strip() or repaired_code.strip() == version.code.strip():
            reason = "修复模型未产生有效代码变化，自动修复暂停。"
            yield self._event("user_action_required", message=reason, reason=reason)
            yield self._event("repair_stopped", reason=reason)
            yield self._event("done", summary="自动修复暂停。")
            return

        yield self._event("code_patch", language="jscad", code=repaired_code, summary="自动修复 JSCAD 运行错误。")
        yield self._event("code_write_start", target=f"projects/{project.id}/main.js")
        repair_version = self.store.save_repair_version(project.id, repaired_code, "自动修复 JSCAD 运行错误。")
        yield self._event("code_write_done", target=f"projects/{project.id}/main.js", versionId=repair_version.id)
        yield self._event("repair_done", versionId=repair_version.id, summary="已生成修复版本，等待再次运行。")
        yield self._event("render_request", reason="修复版本写入完成，请前端再次执行 JSCAD。")
