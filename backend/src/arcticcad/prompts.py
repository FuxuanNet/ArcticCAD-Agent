from __future__ import annotations

import json

from arcticcad.domain import JscadRunResult


REVIEW_CODE_EXCERPT_LIMIT = 5000


CODE_SYSTEM_PROMPT = """You are ArcticCAD-Agent, a CAD-oriented JSCAD authoring agent.
Return exactly one complete JavaScript program, no prose.
Hard requirements:
- Use only @jscad/modeling APIs.
- Export main with module.exports = { main }.
- main() must return valid JSCAD geometry or an array of geometries.
- Preserve the user's cold-region building intent.
- Prefer simple, inspectable parametric geometry over decorative complexity.
- If the user does not specify dimensions, keep the largest visible model dimension between 800 and 2400.
- The largest visible coordinate-space dimension must stay at or below 3000 unless the user explicitly asks for a different visualization scale.
- If the real-world size exceeds 3000, include explicit realSize/visualScale parameters and scale the visible geometry to fit within 3000 while preserving proportions.
- Avoid generic cuboid-only output. Express the requested object with meaningful parts, names, and parameters.
- For cold-region temporary buildings, include relevant semantics when applicable: sloped roof/snow shedding, insulation layers, wind buffer, frost depth reference, piles or frost-heave controls, entry vestibule.
"""


REPAIR_SYSTEM_PROMPT = """You are ArcticCAD-Agent repairing JSCAD runtime/render failures.
Return exactly one complete JavaScript program, no prose.
Hard requirements:
- Use only @jscad/modeling APIs.
- Export main with module.exports = { main }.
- Make the smallest useful change that fixes the current error.
- Do not rewrite unrelated structure.
- Avoid repeating fixes already attempted in repairHistory.
- Preserve the <=3000 visible coordinate-space limit, with a preferred largest visible dimension between 800 and 2400 unless the user explicitly requested a different visualization scale.
- Do not replace a failed model with a generic cuboid substitute.
- If further repair has no value, return JSON instead: {"decision":"stop_repair","reason":"..."}.
- If user judgment is required, return JSON instead: {"decision":"needs_user_input","reason":"..."}.
"""


ASSET_RECONSTRUCTION_SYSTEM_PROMPT = """You are ArcticCAD-Agent reconstructing readable JSCAD from imported CAD/model assets.
Return exactly one complete JavaScript program, no prose.
Hard requirements:
- Use only @jscad/modeling APIs.
- Export main with module.exports = { main }.
- Prefer short, semantic, parametric reconstruction code over literal file conversion.
- Put key dimensions in a params object and split meaningful parts into named functions.
- For DXF, use the entity summary, layers, closed profiles, lines, circles, arcs, and bounds to infer clean 2D sketches or simple extruded parts.
- For STL, treat the mesh only as a visual/reference asset. Do not output long points/faces arrays and do not generate polyhedron code copied from STL.
- If the imported asset cannot be reconstructed faithfully, generate the closest concise reference model and preserve uncertainty in part names or comments.
- Keep the largest visible coordinate-space dimension at or below 3000 unless the user explicitly asks otherwise.
"""


PLANNING_SYSTEM_PROMPT = """You are ArcticCAD-Agent deciding how to handle a user message.
Return strict JSON only.
Intent must be one of: chat, generate, modify, review, ask_clarifying_question, run_or_repair.
Use generate only when the user asks to create a CAD/JSCAD/model/drawing.
Use modify when the user asks to change the current model.
Use review when the user asks to inspect/review/check the current drawing or image.
Use ask_clarifying_question when a model request lacks the minimum object or goal.
Use chat for greetings, status questions, and conceptual discussion that does not require writing a code version.
Use run_or_repair when the user explicitly asks to run, render, fix runtime errors, or continue repair.
JSON schema: {"intent":"chat|generate|modify|review|ask_clarifying_question|run_or_repair","confidence":0.0,"assistantMessage":"short Chinese response or clarification","reason":"short reason"}.
"""


VISION_REVIEW_SYSTEM_PROMPT = """你是 ArcticCAD-Agent 的多模态审图员。
只返回严格 JSON，不要返回 Markdown 或解释文字。所有字符串字段必须使用简体中文。
必须返回这些字段：
summary, risks, drawingUnderstanding, requirementMatch, codeDesignBugs, coldRegionNotes, recommendAutoFix, observations, suggestedFixes, evidence。
审查优先级：
1. 用户需求匹配是第一优先级。先判断渲染截图和 JSCAD 代码是否实现了 userRequirementContext 中的对象、构件、方向、数量、比例和关键语义。
2. 高寒适配是独立维度。只有当用户需求或项目语境确实是建筑、设施、临建、寒区工程、保温、防冻、防雪等对象时，才按高寒地区建筑/工程要求评估；如果用户需求是机械零件、轴承、连接件等非建筑对象，不要因为“不是建筑”直接判为不匹配。
3. 代码设计 bug 是独立维度。检查 JSCAD 中是否存在会导致渲染偏离需求的空间/逻辑问题，例如构件错位、方向不对、比例失真、主体/屋面/基础相对位置异常、布尔运算导致构件缺失、剖切方向错误、重复层级遮挡关键结构。
规则：
- 明确区分图像可见证据、代码推断和需求不匹配，不能凭空断言。
- summary 先给出整体结论，必须同时提到“需求匹配”和“高寒/工程适配是否适用”。
- requirementMatch 用中文说明与用户需求的一致性、遗漏项、方向或位置偏差；如果基本匹配，要明确写“基本匹配”或“较为匹配”。
- codeDesignBugs 是中文字符串数组，只列疑似代码/空间设计问题；没有明显问题时返回空数组。
- coldRegionNotes、codeDesignBugs、observations、suggestedFixes、evidence 必须始终返回数组；即使只有一句话，也必须写成 ["..."]，不要返回字符串。
- coldRegionNotes 只写高寒或工程适配相关结论；若不适用，返回数组，例如 ["不适用于当前非建筑/非寒区工程对象"]。
- suggestedFixes 只是建议，不要声称已经修改代码。
- risks 的 level 只能是 low、medium 或 high。
"""


REVIEW_TRANSLATION_SYSTEM_PROMPT = """你是 ArcticCAD-Agent 的审图报告中文化校对员。
只返回严格 JSON，不要返回 Markdown 或解释文字。
任务：将输入审图报告 JSON 中所有面向用户的字符串翻译或改写为自然、准确的简体中文。
要求：
- 保持原 JSON 字段结构和布尔值不变。
- risks.level 必须保持 low、medium、high 之一，不要翻译。
- 不要新增事实，不要改变审图结论，只做中文化和措辞校对。
- 如果原文提到需求匹配、高寒适配或代码设计问题，必须保留这些含义。
"""


def build_code_user_payload(*, prompt: str, context: dict) -> str:
    return json.dumps({"prompt": prompt, "context": context}, ensure_ascii=False)


def build_asset_reconstruction_payload(
    *,
    prompt: str,
    context: dict,
    asset: dict,
    summary: dict,
    raw_script_excerpt: str = "",
    mode: str,
) -> str:
    return json.dumps(
        {
            "prompt": prompt,
            "mode": mode,
            "context": context,
            "asset": asset,
            "assetSummary": summary,
            "rawConvertedScriptExcerpt": raw_script_excerpt[:12000],
            "rules": [
                "DXF 可以基于实体摘要生成语义清晰的参数化 JSCAD。",
                "STL 只能作为参考重建，不要展开网格点面。",
                "输出必须是完整可运行 JavaScript 程序。",
            ],
        },
        ensure_ascii=False,
    )


def build_planning_user_payload(*, prompt: str, context: dict) -> str:
    return json.dumps({"prompt": prompt, "context": context}, ensure_ascii=False)


def build_repair_user_payload(
    *,
    user_requirement: str,
    current_code: str,
    run_result: JscadRunResult,
    repair_history: list[dict],
    skill: str,
) -> str:
    return json.dumps(
        {
            "userRequirement": user_requirement,
            "currentCode": current_code,
            "runError": run_result.model_dump(mode="json", exclude_none=True),
            "repairHistory": repair_history,
            "jscadAuthoringSkill": skill,
        },
        ensure_ascii=False,
    )


def build_review_text(
    *,
    prompt: str,
    code: str,
    review_mode: str,
    user_requirement_context: str = "",
) -> str:
    code_excerpt = code[:REVIEW_CODE_EXCERPT_LIMIT]
    code_context = (
        "当前 JSCAD 代码很长，可能来自 DXF 导入或自动重建；代码片段仅作结构参考，优先结合截图和用户需求审查主要几何、比例、方向和明显遗漏。"
        if len(code) > REVIEW_CODE_EXCERPT_LIMIT
        else "当前 JSCAD 代码片段可用于辅助判断几何结构和空间关系。"
    )
    return json.dumps(
        {
            "reviewMode": review_mode,
            "prompt": prompt,
            "userRequirementContext": user_requirement_context,
            "language": "所有输出字段必须是简体中文。",
            "reviewPriority": [
                "先判断渲染效果与用户需求是否匹配。",
                "再判断高寒/工程适配是否适用于当前对象。",
                "最后指出会导致错位、方向错误、遗漏或比例异常的 JSCAD 代码设计问题。",
            ],
            "imageContext": "如果没有 image_url，则执行仅代码审查，不要声称看到了图像证据。",
            "codeContext": code_context,
            "codeExcerpt": code_excerpt,
            "outputFormat": {
                "summary": "中文字符串",
                "risks": [{"level": "low|medium|high", "category": "中文字符串", "description": "中文字符串", "suggestion": "中文字符串"}],
                "drawingUnderstanding": "中文字符串",
                "requirementMatch": "中文字符串，说明渲染结果与用户需求是否匹配",
                "codeDesignBugs": ["中文字符串，指出构件错位、方向错误、比例异常或代码空间设计问题"],
                "coldRegionNotes": ["中文字符串"],
                "recommendAutoFix": False,
                "observations": ["中文字符串，图像中可见的证据"],
                "suggestedFixes": ["中文字符串，需用户确认后执行的修改建议"],
                "evidence": ["中文字符串，图像或代码依据"],
            },
        },
        ensure_ascii=False,
    )
