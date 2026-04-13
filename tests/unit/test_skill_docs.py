#!/usr/bin/env python3
import re
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = PROJECT_ROOT / "skills"
TOTAL_SKILL = SKILLS_ROOT / "openmy" / "SKILL.md"
SUBSKILLS = [
    "openmy-install",
    "openmy-startup-context",
    "openmy-context-read",
    "openmy-context-query",
    "openmy-day-run",
    "openmy-day-view",
    "openmy-correction-apply",
    "openmy-status-review",
    "openmy-vocab-init",
    "openmy-profile-init",
    "openmy-health-check",
    "openmy-distill",
    "openmy-extract",
    "openmy-aggregate",
    "openmy-export",
    "openmy-screen-recognition",
]
REQUIRED_SECTIONS = ["## Purpose", "## Trigger", "## Action", "## Restrictions", "## Output"]


class TestSkillDocs(unittest.TestCase):
    def test_total_skill_and_subskills_exist(self):
        self.assertTrue(TOTAL_SKILL.exists(), TOTAL_SKILL)
        for skill_name in SUBSKILLS:
            self.assertTrue((SKILLS_ROOT / skill_name / "SKILL.md").exists(), skill_name)

    def test_total_skill_references_all_subskills(self):
        content = TOTAL_SKILL.read_text(encoding="utf-8")
        for skill_name in SUBSKILLS:
            self.assertIn(skill_name, content)

    def test_total_skill_declares_mandatory_reading_rules(self):
        content = TOTAL_SKILL.read_text(encoding="utf-8")
        self.assertIn("Mandatory Sub-Skill Reading", content)
        self.assertIn("day.run", content)
        self.assertIn("quick-start", content)
        self.assertIn("openmy-install/SKILL.md", content)

    def test_subskills_have_required_sections(self):
        for skill_name in SUBSKILLS:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for section in REQUIRED_SECTIONS:
                self.assertIn(section, content, f"{skill_name} missing {section}")

    def test_subskills_only_call_openmy_skill_json_contract(self):
        for skill_name in SUBSKILLS:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            commands = re.findall(r"`(openmy skill[^`]*)`", content)
            self.assertTrue(commands, f"{skill_name} does not declare any command")
            for command in commands:
                self.assertIn("--json", command, f"{skill_name} missing --json: {command}")

    def test_subskills_do_not_require_raw_file_edits(self):
        forbidden_patterns = [
            r"python3 -m openmy",
            r"cat\s+data/",
            r"vim\s+data/",
            r"nano\s+data/",
            r"edit raw evidence files directly",
            r"edit active_context\.json directly",
        ]
        for skill_name in SUBSKILLS:
            content = (SKILLS_ROOT / skill_name / "SKILL.md").read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                self.assertIsNone(re.search(pattern, content), f"{skill_name} matched forbidden pattern: {pattern}")

    def test_day_run_skill_has_reply_self_check_block(self):
        content = (SKILLS_ROOT / "openmy-day-run" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("自检规则", content)
        self.assertIn("因为没配 Gemini key", content)
        self.assertIn("后面两步整理我可以直接替你做，要继续吗？", content)


if __name__ == "__main__":
    unittest.main()
