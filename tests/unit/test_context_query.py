#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openmy.services.query.context_query import query_context


class TestContextQuery(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def seed_workspace(self, root: Path) -> Path:
        data_root = root / "data"
        data_root.mkdir(parents=True, exist_ok=True)

        self.write_json(
            data_root / "active_context.json",
            {
                "schema_version": "active_context.v1",
                "generated_at": "2026-04-10T21:00:00+08:00",
                "status_line": "最近主要推进 OpenMy；当前有 2 个待办未闭环；高频互动对象是 张总。",
                "stable_profile": {
                    "identity": {"canonical_name": "test_user"},
                    "communication_contract": {},
                    "key_people_registry": [
                        {
                            "id": "entity_zhang",
                            "entity_id": "zhang_zong",
                            "display_name": "张总",
                            "aliases": ["张总"],
                            "confidence": 0.92,
                            "source_rank": "aggregate",
                        }
                    ],
                },
                "core_memory": {
                    "focus_projects": [
                        {
                            "id": "project_openmy",
                            "project_id": "project_openmy",
                            "title": "OpenMy",
                            "current_goal": "默认转写后端切到 faster-whisper",
                            "next_actions": ["补 Agent 查询接口"],
                            "confidence": 0.95,
                            "current_state": "active",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "project.aggregate",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        }
                    ],
                    "open_loops": [
                        {
                            "id": "loop_readme",
                            "loop_id": "loop_readme",
                            "title": "重写 README",
                            "loop_type": "todo",
                            "status": "open",
                            "confidence": 0.9,
                            "current_state": "active",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "intent",
                                    "scene_id": "scene_001",
                                    "quote": "今天把 README 重写一下。",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        }
                    ],
                    "active_decisions": [
                        {
                            "id": "decision_fw",
                            "decision_id": "decision_fw",
                            "decision": "默认先走 faster-whisper。",
                            "topic": "OpenMy",
                            "confidence": 0.88,
                            "current_state": "active",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "intent.decision",
                                    "scene_id": "scene_001",
                                    "quote": "默认先走 faster-whisper。",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        }
                    ],
                    "key_people": [
                        {
                            "id": "entity_zhang",
                            "entity_id": "zhang_zong",
                            "display_name": "张总",
                            "aliases": ["张总"],
                            "confidence": 0.92,
                            "source_rank": "aggregate",
                        }
                    ],
                    "current_focus": ["默认转写后端切换", "Agent 查询接口"],
                },
                "rolling_context": {
                    "active_projects": [
                        {
                            "id": "project_openmy",
                            "project_id": "project_openmy",
                            "title": "OpenMy",
                            "status": "active",
                            "current_goal": "默认转写后端切到 faster-whisper",
                            "next_actions": ["补 Agent 查询接口"],
                            "last_touched_at": "2026-04-10T21:00:00+08:00",
                            "confidence": 0.95,
                            "current_state": "active",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "project.aggregate",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        }
                    ],
                    "open_loops": [
                        {
                            "id": "loop_readme",
                            "loop_id": "loop_readme",
                            "title": "重写 README",
                            "loop_type": "todo",
                            "status": "open",
                            "confidence": 0.9,
                            "current_state": "active",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "intent",
                                    "scene_id": "scene_001",
                                    "quote": "今天把 README 重写一下。",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        },
                        {
                            "id": "loop_call",
                            "loop_id": "loop_call",
                            "title": "给张总回电话",
                            "loop_type": "todo",
                            "status": "closed",
                            "confidence": 0.88,
                            "current_state": "closed",
                            "valid_until": "2026-04-10T18:00:00+08:00",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "intent",
                                    "scene_id": "scene_002",
                                    "quote": "已经给张总回过电话了。",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        },
                    ],
                    "recent_decisions": [
                        {
                            "id": "decision_fw",
                            "decision_id": "decision_fw",
                            "decision": "默认先走 faster-whisper。",
                            "topic": "OpenMy",
                            "effective_from": "2026-04-10T10:15:00+08:00",
                            "confidence": 0.88,
                            "current_state": "active",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "intent.decision",
                                    "scene_id": "scene_001",
                                    "quote": "默认先走 faster-whisper。",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        }
                    ],
                    "recent_events": [
                        {
                            "id": "event_fw",
                            "event_id": "event_fw",
                            "project": "OpenMy",
                            "summary": "默认转写后端切到 faster-whisper。",
                            "happened_at": "2026-04-10T10:20:00+08:00",
                            "time_label": "10:20",
                            "current_state": "past",
                            "provenance_refs": [
                                {
                                    "date": "2026-04-10",
                                    "kind": "meta.event",
                                    "scene_id": "scene_001",
                                    "source_path": "2026-04-10.meta.json",
                                }
                            ],
                        }
                    ],
                },
                "realtime_context": {"today_focus": ["默认转写后端切换"]},
                "quality": {},
            },
        )

        self.write_json(
            data_root / "2026-04-10" / "2026-04-10.meta.json",
            {
                "daily_summary": "今天主要把默认转写后端切到 faster-whisper，并补 Agent 查询。",
                "events": [
                    {
                        "event_id": "event_fw",
                        "time": "10:20",
                        "project": "OpenMy",
                        "summary": "默认转写后端切到 faster-whisper。",
                        "source_scene_id": "scene_001",
                        "provenance_refs": [
                            {
                                "date": "2026-04-10",
                                "kind": "meta.event",
                                "scene_id": "scene_001",
                                "source_path": "2026-04-10.meta.json",
                            }
                        ],
                    }
                ],
                "intents": [
                    {
                        "intent_id": "intent_readme",
                        "kind": "action_item",
                        "what": "重写 README",
                        "status": "open",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.91,
                        "evidence_quote": "今天把 README 重写一下。",
                        "source_scene_id": "scene_001",
                        "topic": "OpenMy",
                        "project_hint": "OpenMy",
                        "current_state": "active",
                        "valid_from": "2026-04-10T10:00:00+08:00",
                    },
                    {
                        "intent_id": "intent_call",
                        "kind": "action_item",
                        "what": "给张总回电话",
                        "status": "done",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.95,
                        "evidence_quote": "已经给张总回过电话了。",
                        "source_scene_id": "scene_002",
                        "topic": "合同对接",
                        "project_hint": "合同对接",
                        "current_state": "closed",
                        "valid_from": "2026-04-10T17:00:00+08:00",
                        "valid_until": "2026-04-10T18:00:00+08:00",
                    },
                    {
                        "intent_id": "intent_decision",
                        "kind": "decision",
                        "what": "默认先走 faster-whisper。",
                        "status": "active",
                        "who": {"kind": "user", "label": "老板"},
                        "confidence_label": "high",
                        "confidence_score": 0.88,
                        "evidence_quote": "默认先走 faster-whisper。",
                        "source_scene_id": "scene_001",
                        "topic": "OpenMy",
                        "project_hint": "OpenMy",
                        "current_state": "active",
                        "valid_from": "2026-04-10T10:15:00+08:00",
                    },
                ],
                "facts": [
                    {
                        "fact_id": "fact_fw",
                        "fact_type": "project_update",
                        "content": "OpenMy 默认转写后端改成 faster-whisper。",
                        "topic": "OpenMy",
                        "confidence_label": "high",
                        "confidence_score": 0.93,
                        "source_scene_id": "scene_001",
                        "evidence_quote": "默认先走 faster-whisper。",
                        "current_state": "active",
                    }
                ],
            },
        )

        self.write_json(
            data_root / "2026-04-10" / "scenes.json",
            {
                "scenes": [
                    {
                        "scene_id": "scene_001",
                        "time_start": "10:00",
                        "time_end": "10:30",
                        "summary": "讨论 OpenMy 的默认转写后端，决定先走 faster-whisper。",
                        "preview": "默认先走 faster-whisper。",
                        "role": {"addressed_to": "", "needs_review": False},
                    },
                    {
                        "scene_id": "scene_002",
                        "time_start": "17:00",
                        "time_end": "18:00",
                        "summary": "确认已经给张总回电话，合同细节对齐完了。",
                        "preview": "已经给张总回过电话了。",
                        "role": {"addressed_to": "张总", "needs_review": False},
                    },
                ]
            },
        )

        self.write_json(
            data_root / "2026-04-09" / "2026-04-09.meta.json",
            {
                "daily_summary": "昨天讨论 OpenMy 是否改成 FunASR。",
                "events": [
                    {
                        "event_id": "event_fun",
                        "time": "14:10",
                        "project": "OpenMy",
                        "summary": "评估改用 FunASR 作为默认中文本地转写。",
                        "source_scene_id": "scene_101",
                    }
                ],
                "facts": [
                    {
                        "fact_id": "fact_fun",
                        "fact_type": "project_update",
                        "content": "OpenMy 默认转写后端改成 FunASR。",
                        "topic": "OpenMy 默认转写后端",
                        "confidence_label": "high",
                        "confidence_score": 0.9,
                        "source_scene_id": "scene_101",
                        "evidence_quote": "默认改成 FunASR。",
                        "current_state": "past",
                        "valid_from": "2026-04-09T14:10:00+08:00",
                        "valid_until": "2026-04-10T10:19:59+08:00",
                    }
                ],
            },
        )
        self.write_json(
            data_root / "2026-04-09" / "scenes.json",
            {
                "scenes": [
                    {
                        "scene_id": "scene_101",
                        "time_start": "14:10",
                        "time_end": "14:30",
                        "summary": "讨论是否把默认本地转写换成 FunASR。",
                        "preview": "默认改成 FunASR。",
                        "role": {"addressed_to": "", "needs_review": False},
                    }
                ]
            },
        )
        return data_root

    def test_project_query_uses_active_context_and_meta(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = self.seed_workspace(Path(tmp_dir))

            result = query_context(data_root, kind="project", query="OpenMy")

            self.assertEqual(result["kind"], "project")
            self.assertIn("OpenMy", result["summary"])
            self.assertTrue(any(item["type"] == "project" and item["title"] == "OpenMy" for item in result["current_hits"]))
            self.assertTrue(any(item["type"] == "event" for item in result["history_hits"]))
            self.assertTrue(result["evidence"])
            self.assertTrue(result["daily_rollups"])
            self.assertIn("current", result["temporal_buckets"])

    def test_project_query_returns_cross_day_rollups_and_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = self.seed_workspace(Path(tmp_dir))

            result = query_context(data_root, kind="project", query="OpenMy")

            dates = {item["date"] for item in result["daily_rollups"]}
            self.assertIn("2026-04-10", dates)
            self.assertIn("2026-04-09", dates)
            self.assertTrue(result["conflicts"])
            self.assertTrue(any("FunASR" in json.dumps(item, ensure_ascii=False) for item in result["conflicts"]))

    def test_project_query_groups_hits_into_past_current_and_future(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = self.seed_workspace(Path(tmp_dir))

            result = query_context(data_root, kind="project", query="OpenMy")

            self.assertTrue(result["temporal_buckets"]["current"])
            self.assertTrue(result["temporal_buckets"]["past"])

    def test_person_query_returns_related_structured_hits(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = self.seed_workspace(Path(tmp_dir))

            result = query_context(data_root, kind="person", query="张总")

            joined = json.dumps(result, ensure_ascii=False)
            self.assertEqual(result["kind"], "person")
            self.assertIn("张总", joined)
            self.assertTrue(result["current_hits"] or result["history_hits"])
            self.assertTrue(result["evidence"])
            self.assertTrue(result["daily_rollups"])

    def test_open_query_only_returns_unclosed_items(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = self.seed_workspace(Path(tmp_dir))

            result = query_context(data_root, kind="open")

            titles = {item["title"] for item in result["current_hits"]}
            self.assertIn("重写 README", titles)
            self.assertNotIn("给张总回电话", titles)

    def test_closed_query_returns_recently_closed_items(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = self.seed_workspace(Path(tmp_dir))

            result = query_context(data_root, kind="closed")

            titles = {item["title"] for item in result["history_hits"]}
            self.assertIn("给张总回电话", titles)
            self.assertTrue(all(item["current_state"] == "closed" for item in result["history_hits"]))

    def test_evidence_query_traces_back_to_scene_and_quote(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data_root = self.seed_workspace(Path(tmp_dir))

            result = query_context(data_root, kind="evidence", query="faster-whisper")

            self.assertEqual(result["kind"], "evidence")
            self.assertTrue(any(item["scene_id"] == "scene_001" for item in result["evidence"]))
            self.assertTrue(any("faster-whisper" in (item.get("quote") or item.get("scene_summary") or "") for item in result["evidence"]))
            self.assertTrue(result["conflicts"])

    def test_project_query_uses_search_index_to_skip_irrelevant_days(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            data_root = self.seed_workspace(root)
            unrelated_dir = data_root / "2026-04-08"
            unrelated_dir.mkdir(parents=True, exist_ok=True)
            self.write_json(
                unrelated_dir / "2026-04-08.meta.json",
                {"daily_summary": "今天只是在看电影。", "events": [], "intents": [], "facts": [], "role_hints": []},
            )
            self.write_json(root / "search_index.json", {"schema_version": "openmy.search_index.v1", "days": []})
            self.write_json(
                data_root / "search_index.json",
                {
                    "schema_version": "openmy.search_index.v1",
                    "days": [
                        {
                            "date": "2026-04-10",
                            "daily_summary": "今天主要把默认转写后端切到 faster-whisper，并补 Agent 查询。",
                            "terms": {"project": ["OpenMy"], "person": ["张总"], "evidence": ["faster-whisper"], "closed": []},
                        },
                        {
                            "date": "2026-04-09",
                            "daily_summary": "讨论是否把默认本地转写换成 FunASR。",
                            "terms": {"project": ["OpenMy", "FunASR"], "person": [], "evidence": ["FunASR"], "closed": []},
                        },
                        {
                            "date": "2026-04-08",
                            "daily_summary": "今天只是在看电影。",
                            "terms": {"project": ["电影"], "person": [], "evidence": ["电影"], "closed": []},
                        },
                    ],
                },
            )

            from openmy.services.query import context_query as context_query_module

            original_load_json = context_query_module._load_json
            loaded_paths: list[str] = []

            def spy(path):
                loaded_paths.append(str(path))
                return original_load_json(path)

            with patch("openmy.services.query.context_query._load_json", side_effect=spy):
                result = query_context(data_root, kind="project", query="OpenMy")

            self.assertIn("OpenMy", result["summary"])
            self.assertFalse(any("2026-04-08.meta.json" in path for path in loaded_paths))


if __name__ == "__main__":
    unittest.main()
