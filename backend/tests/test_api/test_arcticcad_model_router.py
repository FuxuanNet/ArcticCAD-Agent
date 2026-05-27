from __future__ import annotations

from arcticcad.domain import ReviewReport
from arcticcad.providers.model_router import normalize_review_report_data, report_needs_chinese_rewrite


def test_report_needs_chinese_rewrite_for_english_review():
    report = ReviewReport(
        summary="The rendered model matches the requested mechanical sleeve assembly.",
        drawingUnderstanding="The image shows concentric cylindrical layers and bearing balls.",
        requirementMatch="The model is mostly consistent with the user request.",
        risks=[],
    )

    assert report_needs_chinese_rewrite(report) is True


def test_report_does_not_rewrite_chinese_review():
    report = ReviewReport(
        summary="渲染模型与用户要求的机械套筒较为匹配。",
        drawingUnderstanding="图中可见同心圆环和滚珠结构。",
        requirementMatch="整体满足用户需求。",
        risks=[],
    )

    assert report_needs_chinese_rewrite(report) is False


def test_normalize_review_report_accepts_string_array_fields():
    data = normalize_review_report_data(
        {
            "summary": "审图完成。",
            "drawingUnderstanding": "图中可见模型。",
            "coldRegionNotes": "不适用于当前非建筑/非寒区工程对象。",
            "codeDesignBugs": None,
            "observations": "可见一个盒体。",
            "suggestedFixes": ["保持当前模型。"],
            "evidence": None,
            "risks": [{"level": "serious", "category": "比例", "description": "偏大"}],
        }
    )

    report = ReviewReport.model_validate(data)
    assert report.coldRegionNotes == ["不适用于当前非建筑/非寒区工程对象。"]
    assert report.observations == ["可见一个盒体。"]
    assert report.codeDesignBugs == []
    assert report.evidence == []
    assert report.risks[0].level == "medium"
