from __future__ import annotations

import json
import re
from openai import APITimeoutError
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from openai import AsyncOpenAI

from arcticcad.config import AppConfig
from arcticcad.domain import JscadRunResult, ReviewReport
from arcticcad.prompts import (
    ASSET_RECONSTRUCTION_SYSTEM_PROMPT,
    CODE_SYSTEM_PROMPT,
    PLANNING_SYSTEM_PROMPT,
    REPAIR_SYSTEM_PROMPT,
    REVIEW_TRANSLATION_SYSTEM_PROMPT,
    VISION_REVIEW_SYSTEM_PROMPT,
    build_code_user_payload,
    build_asset_reconstruction_payload,
    build_planning_user_payload,
    build_repair_user_payload,
    build_review_text,
)


@dataclass(frozen=True)
class ModelResult:
    ok: bool
    provider: str
    code: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None
    reasoningContent: str | None = None


class ModelRouter:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def plan_intent(
        self,
        *,
        prompt: str,
        context: dict,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResult:
        if not self.config.llm.configured:
            return ModelResult(
                ok=False,
                provider=self.config.llm.provider,
                error="文本模型未配置：请设置 CADX_LLM_API_KEY 后再进行 Agent planning。",
            )

        try:
            response = await self._chat(
                model_config=self.config.llm,
                messages=[
                    {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
                    {"role": "user", "content": build_planning_user_payload(prompt=prompt, context=context)},
                ],
                temperature=0.0,
                on_progress=on_progress,
            )
            content, reasoning = response
            data = json.loads(extract_json(content) or "{}")
            intent = data.get("intent")
            if intent not in {"chat", "generate", "modify", "review", "ask_clarifying_question", "run_or_repair"}:
                return ModelResult(
                    ok=False,
                    provider=self.config.llm.provider,
                    error=f"模型返回了无效意图：{intent!r}。",
                    reasoningContent=reasoning,
                )
            return ModelResult(ok=True, provider=self.config.llm.provider, data=data, reasoningContent=reasoning)
        except Exception as exc:
            return ModelResult(ok=False, provider=self.config.llm.provider, error=f"Agent planning 调用失败：{exc}")

    async def complete_code(
        self,
        *,
        prompt: str,
        context: dict,
        skill: str,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResult:
        if not self.config.llm.configured:
            return ModelResult(
                ok=False,
                provider=self.config.llm.provider,
                error="文本模型未配置：请设置 CADX_LLM_API_KEY 后再生成 JSCAD。",
            )

        system = f"{CODE_SYSTEM_PROMPT}\n\n{skill}"
        user = build_code_user_payload(prompt=prompt, context=context)
        try:
            content, reasoning = await self._chat(
                model_config=self.config.llm,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                on_progress=on_progress,
            )
            code = extract_code(content)
            if not code.strip() or "module.exports" not in code:
                return ModelResult(
                    ok=False,
                    provider=self.config.llm.provider,
                    error="模型没有返回可运行的完整 JSCAD 程序。",
                    reasoningContent=reasoning,
                )
            return ModelResult(ok=True, provider=self.config.llm.provider, code=code, reasoningContent=reasoning)
        except Exception as exc:
            return ModelResult(ok=False, provider=self.config.llm.provider, error=f"文本模型调用失败：{exc}")

    async def reconstruct_from_asset(
        self,
        *,
        prompt: str,
        context: dict,
        asset: dict,
        summary: dict,
        raw_script_excerpt: str,
        mode: str,
        skill: str,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResult:
        if not self.config.llm.configured:
            return ModelResult(
                ok=False,
                provider=self.config.llm.provider,
                error="文本模型未配置：请设置 CADX_LLM_API_KEY 后再执行资产重建。",
            )

        system = f"{ASSET_RECONSTRUCTION_SYSTEM_PROMPT}\n\n{skill}"
        user = build_asset_reconstruction_payload(
            prompt=prompt,
            context=context,
            asset=asset,
            summary=summary,
            raw_script_excerpt=raw_script_excerpt,
            mode=mode,
        )
        try:
            content, reasoning = await self._chat(
                model_config=self.config.llm,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.15,
                on_progress=on_progress,
            )
            code = extract_code(content)
            if not code.strip() or "module.exports" not in code:
                return ModelResult(
                    ok=False,
                    provider=self.config.llm.provider,
                    error="资产重建模型没有返回可运行的完整 JSCAD 程序。",
                    reasoningContent=reasoning,
                )
            if asset.get("format") == "stl" and ("polyhedron" in code or "const points = [" in code):
                return ModelResult(
                    ok=False,
                    provider=self.config.llm.provider,
                    error="STL 重建结果包含网格 polyhedron 代码，已按规则拒绝写入。",
                    reasoningContent=reasoning,
                )
            return ModelResult(ok=True, provider=self.config.llm.provider, code=code, reasoningContent=reasoning)
        except Exception as exc:
            return ModelResult(ok=False, provider=self.config.llm.provider, error=f"资产重建模型调用失败：{exc}")

    async def _chat(
        self,
        *,
        model_config,
        messages: list[dict],
        temperature: float,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[str, str | None]:
        client = AsyncOpenAI(
            api_key=model_config.api_key,
            base_url=model_config.base_url,
            timeout=self.config.llm_timeout_seconds,
        )
        stream = await client.chat.completions.create(
            model=model_config.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = delta.content or ""
            reasoning = getattr(delta, "reasoning_content", None) or ""
            if content:
                content_parts.append(content)
                if on_progress:
                    await on_progress(content)
            if reasoning:
                reasoning_parts.append(reasoning)
        return "".join(content_parts), "".join(reasoning_parts) or None

    async def _vision_chat(
        self,
        *,
        messages: list[dict],
        temperature: float,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[str, str | None]:
        client = AsyncOpenAI(
            api_key=self.config.vision.api_key,
            base_url=self.config.vision.base_url,
            timeout=self.config.vision_timeout_seconds,
        )
        stream = await client.chat.completions.create(
            model=self.config.vision.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = delta.content or ""
            reasoning = getattr(delta, "reasoning_content", None) or ""
            if content:
                content_parts.append(content)
                if on_progress:
                    await on_progress(content)
            if reasoning:
                reasoning_parts.append(reasoning)
        return "".join(content_parts), "".join(reasoning_parts) or None

    async def repair_code(
        self,
        *,
        user_requirement: str,
        current_code: str,
        run_result: JscadRunResult,
        skill: str,
        repair_history: list[dict] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResult:
        if not self.config.llm.configured:
            return ModelResult(
                ok=False,
                provider=self.config.llm.provider,
                error="文本模型未配置，不能继续自动修复。请配置 CADX_LLM_API_KEY，或手动修改代码。",
            )

        user = build_repair_user_payload(
            user_requirement=user_requirement,
            current_code=current_code,
            run_result=run_result,
            repair_history=repair_history or [],
            skill=skill,
        )
        try:
            content, reasoning = await self._chat(
                model_config=self.config.llm,
                messages=[
                    {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
                temperature=0.1,
                on_progress=on_progress,
            )
            decision = extract_json(content)
            if decision:
                try:
                    data = json.loads(decision)
                    if data.get("decision") in {"stop_repair", "needs_user_input"}:
                        return ModelResult(ok=True, provider=self.config.llm.provider, data={"decision": data["decision"], "reason": str(data.get("reason") or "模型建议暂停。")}, reasoningContent=reasoning)
                except Exception:
                    pass
            code = extract_code(content)
            if not code.strip() or "module.exports" not in code:
                return ModelResult(ok=False, provider=self.config.llm.provider, error="修复模型没有返回可运行的完整 JSCAD 程序。", reasoningContent=reasoning)
            return ModelResult(ok=True, provider=self.config.llm.provider, data={"decision": "continue", "code": code, "reason": "模型生成修复版本。"}, reasoningContent=reasoning)
        except Exception as exc:
            return ModelResult(ok=False, provider=self.config.llm.provider, error=f"修复模型调用失败：{exc}")

    async def review_image(
        self,
        *,
        prompt: str,
        code: str,
        image_base64: str | None = None,
        review_mode: str = "review",
        user_requirement_context: str = "",
    ) -> ReviewReport:
        result = await self.review_image_result(
            prompt=prompt,
            code=code,
            image_base64=image_base64,
            review_mode=review_mode,
            user_requirement_context=user_requirement_context,
        )
        if not result.ok or not result.data:
            raise RuntimeError(result.error or "视觉模型审图失败。")
        return ReviewReport.model_validate(result.data)

    async def review_image_result(
        self,
        *,
        prompt: str,
        code: str,
        image_base64: str | None = None,
        review_mode: str = "review",
        user_requirement_context: str = "",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> ModelResult:
        if not self.config.vision.configured:
            return ModelResult(
                ok=False,
                provider=self.config.vision.provider,
                error="视觉模型未配置：请设置 CADX_LLM_VISION_API_KEY 后再审图。",
        )

        try:
            content: list[dict] = []
            if image_base64:
                content.append({"type": "image_url", "image_url": {"url": image_base64, "detail": "low"}})
            content.append(
                {
                    "type": "text",
                    "text": build_review_text(
                        prompt=prompt,
                        code=code,
                        review_mode=review_mode,
                        user_requirement_context=user_requirement_context,
                    ),
                }
            )
            raw, reasoning = await self._vision_chat(
                messages=[
                    {
                        "role": "system",
                        "content": VISION_REVIEW_SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": content},
                ],
                temperature=0.2,
                on_progress=on_progress,
            )
            data = json.loads(extract_json(raw) or "{}")
            report = ReviewReport.model_validate(normalize_review_report_data(data))
            if report_needs_chinese_rewrite(report):
                translated_raw, _ = await self._vision_chat(
                    messages=[
                        {"role": "system", "content": REVIEW_TRANSLATION_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps(report.model_dump(mode="json"), ensure_ascii=False),
                        },
                    ],
                    temperature=0.0,
                )
                translated_data = json.loads(extract_json(translated_raw) or "{}")
                report = ReviewReport.model_validate(normalize_review_report_data(translated_data))
            return ModelResult(ok=True, provider=self.config.vision.provider, data=report.model_dump(mode="json"), reasoningContent=reasoning)
        except (TimeoutError, APITimeoutError) as exc:
            return ModelResult(
                ok=False,
                provider=self.config.vision.provider,
                error=f"视觉模型审图超时，请减少截图尺寸或稍后重试。({exc})",
            )
        except Exception as exc:
            return ModelResult(ok=False, provider=self.config.vision.provider, error=f"视觉模型调用失败：{exc}")


def extract_code(text: str) -> str:
    match = re.search(r"```(?:js|javascript)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text.strip()


def report_needs_chinese_rewrite(report: ReviewReport) -> bool:
    text = " ".join(_collect_text_values(report.model_dump(mode="json")))
    letters = len(re.findall(r"[A-Za-z]", text))
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    return letters >= 40 and letters > chinese


def normalize_review_report_data(value: dict[str, Any]) -> dict[str, Any]:
    data = dict(value or {})
    data["summary"] = _string_or_default(data.get("summary"), "视觉模型未返回摘要。")
    data["drawingUnderstanding"] = _string_or_default(data.get("drawingUnderstanding"), "")
    data["requirementMatch"] = _string_or_default(data.get("requirementMatch"), "")
    data["recommendAutoFix"] = bool(data.get("recommendAutoFix", False))
    for key in ["coldRegionNotes", "codeDesignBugs", "observations", "suggestedFixes", "evidence"]:
        data[key] = _string_list(data.get(key))
    data["risks"] = _normalize_risks(data.get("risks"))
    return data


def _string_or_default(value: object, default: str) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [_string_or_default(item, "").strip() for item in value if _string_or_default(item, "").strip()]
    return [_string_or_default(value, "")]


def _normalize_risks(value: object) -> list[dict[str, str]]:
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    risks: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, str):
            risks.append({"level": "medium", "category": "审图提示", "description": item, "suggestion": ""})
            continue
        if not isinstance(item, dict):
            continue
        level = str(item.get("level") or "medium").lower()
        if level not in {"low", "medium", "high"}:
            level = "medium"
        risks.append(
            {
                "level": level,
                "category": _string_or_default(item.get("category"), "未分类"),
                "description": _string_or_default(item.get("description"), ""),
                "suggestion": _string_or_default(item.get("suggestion"), ""),
            }
        )
    return risks


def _collect_text_values(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_collect_text_values(item))
        return items
    if isinstance(value, dict):
        items: list[str] = []
        for item in value.values():
            items.extend(_collect_text_values(item))
        return items
    return []
