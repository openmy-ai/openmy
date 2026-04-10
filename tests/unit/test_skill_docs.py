#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT_ROOT / "skills"
TOTAL_SKILL = SKILLS_ROOT / "openmy" / "SKILL.md"
SUBSKILLS = [
    "openmy-startup-context",
    "openmy-context-read",
    "openmy-day-run",
    "openmy-day-view",
    "openmy-correction-apply",
    "openmy-status-review",
]
REQUIRED_SECTIONS = ["## 用途", "## 触发条件", "## 执行动作", "## 禁止事项", "## 输出说明"]


class TestSkillDocs(unittest.TestCase):
    def test_total_skill_and_subskills_exist(self):
        self.assertTrue(TOTAL_SKILL.exists(), TOTAL_SKILL)
        for skill_name in SUBSKILLS:
            self.assertTrue((SKILLS_ROOT / skill_name / "SKILL.md").exists(), skill_name)

    def test_total_skill_references_all_subskills(self):
        content = TOTAL_SKILL.read_text(encoding="utf-8")
        for skill_name in SUBSKILLS:
            self.assertIn(skill_name, content)

    def test_subskills_have_required_sections(self):
        for skill_name in SUBSKILLS:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for section in REQUIRED_SECTIONS:
                self.assertIn(section, content, f"{skill_name} 缺少 {section}")

    def test_subskills_only_call_openmy_skill_json_contract(self):
        for skill_name in SUBSKILLS:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            commands = re.findall(r"`([^`]*openmy[^`]*)`", content)
            self.assertTrue(commands, f"{skill_name} 没有声明执行动作")
            for command in commands:
                self.assertIn("openmy skill", command, f"{skill_name} 出现了非 skill 入口: {command}")
                self.assertIn("--json", command, f"{skill_name} 缺少 --json: {command}")

    def test_subskills_do_not_require_user_terminal_or_raw_file_edits(self):
        forbidden_patterns = [
            r"python3 -m openmy",
            r"cat\s+data/",
            r"vim\s+data/",
            r"nano\s+data/",
            r"直接编辑 raw evidence 文件",
            r"直接改 active_context\.json",
        ]
        for skill_name in SUBSKILLS:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                self.assertIsNone(re.search(pattern, content), f"{skill_name} 命中禁令: {pattern}")


if __name__ == "__main__":
    unittest.main()
