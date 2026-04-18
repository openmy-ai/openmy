from pathlib import Path
from unittest.mock import patch


def test_answer_with_synthesis_returns_llm_text_from_hits():
    from openmy.services.query.context_query import answer_with_synthesis

    query_result = {
        "kind": "project",
        "query": "OpenMy",
        "summary": "OpenMy 最近有 1 条当前上下文。",
        "current_hits": [
            {"type": "decision", "title": "先做 CLI", "date": "2026-04-18", "summary": "OpenMy 项目"},
        ],
        "history_hits": [],
        "evidence": [
            {"date": "2026-04-18", "scene_id": "s1", "quote": "今天决定先做 CLI"},
        ],
    }

    with patch("openmy.services.query.context_query.query_context", return_value=query_result), patch(
        "openmy.services.query.context_query._call_llm_for_answer",
        return_value="你最近决定先做 CLI。",
    ):
        result = answer_with_synthesis(
            data_root=Path("/tmp/fake"),
            question="我最近对 OpenMy 做过什么决定？",
        )

    assert result["answer"] == "你最近决定先做 CLI。"
    assert result["evidence"] == query_result["evidence"]
    assert result["query_result"]["kind"] == "project"


def test_answer_with_synthesis_no_hits_returns_fallback_without_llm():
    from openmy.services.query.context_query import answer_with_synthesis

    query_result = {
        "kind": "project",
        "query": "完全不存在的项目",
        "summary": "完全不存在的项目 最近有 0 条当前上下文。",
        "current_hits": [],
        "history_hits": [],
        "evidence": [],
    }

    with patch("openmy.services.query.context_query.query_context", return_value=query_result), patch(
        "openmy.services.query.context_query._call_llm_for_answer"
    ) as call_llm:
        result = answer_with_synthesis(
            data_root=Path("/tmp/fake"),
            question="完全不存在的东西？",
        )

    assert "没有找到" in result["answer"] or "暂无" in result["answer"]
    assert result["evidence"] == []
    call_llm.assert_not_called()


def test_answer_with_synthesis_llm_failure_falls_back_to_rendered_result():
    from openmy.services.query.context_query import answer_with_synthesis

    query_result = {
        "kind": "project",
        "query": "OpenMy",
        "summary": "OpenMy 最近有 1 条当前上下文。",
        "current_hits": [{"type": "decision", "title": "先做 CLI", "date": "2026-04-18"}],
        "history_hits": [],
        "evidence": [],
    }

    with patch("openmy.services.query.context_query.query_context", return_value=query_result), patch(
        "openmy.services.query.context_query._call_llm_for_answer",
        side_effect=RuntimeError("llm down"),
    ):
        result = answer_with_synthesis(
            data_root=Path("/tmp/fake"),
            question="OpenMy 干了啥？",
        )

    assert "OpenMy 最近有 1 条当前上下文。" in result["answer"]
    assert "当前命中" in result["answer"]
