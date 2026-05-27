from __future__ import annotations

import json

from arcticcad.prompts import REVIEW_TRANSLATION_SYSTEM_PROMPT, VISION_REVIEW_SYSTEM_PROMPT, build_review_text


def test_vision_review_prompt_requires_chinese_and_design_bug_review():
    assert "简体中文" in VISION_REVIEW_SYSTEM_PROMPT
    assert "需求" in VISION_REVIEW_SYSTEM_PROMPT
    assert "错位" in VISION_REVIEW_SYSTEM_PROMPT
    assert "方向" in VISION_REVIEW_SYSTEM_PROMPT
    assert "codeDesignBugs" in VISION_REVIEW_SYSTEM_PROMPT
    assert "用户需求匹配是第一优先级" in VISION_REVIEW_SYSTEM_PROMPT
    assert "非建筑对象" in VISION_REVIEW_SYSTEM_PROMPT
    assert "必须始终返回数组" in VISION_REVIEW_SYSTEM_PROMPT


def test_review_text_includes_requirement_context_and_new_report_fields():
    payload = json.loads(
        build_review_text(
            prompt="请审图",
            code="module.exports = { main }",
            review_mode="review",
            user_requirement_context="用户要求入口朝南并包含坡屋面。",
        )
    )

    assert payload["userRequirementContext"] == "用户要求入口朝南并包含坡屋面。"
    assert payload["language"] == "所有输出字段必须是简体中文。"
    assert "先判断渲染效果与用户需求是否匹配。" in payload["reviewPriority"]
    assert "requirementMatch" in payload["outputFormat"]
    assert "codeDesignBugs" in payload["outputFormat"]


def test_review_translation_prompt_preserves_report_shape():
    assert "简体中文" in REVIEW_TRANSLATION_SYSTEM_PROMPT
    assert "保持原 JSON 字段结构" in REVIEW_TRANSLATION_SYSTEM_PROMPT
    assert "risks.level" in REVIEW_TRANSLATION_SYSTEM_PROMPT
