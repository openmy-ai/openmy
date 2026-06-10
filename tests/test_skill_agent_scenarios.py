"""Skill Agent 交互场景测试。

模拟新用户视角，验证 Skill 交互链路行为是否符合 SKILL.md 规范。
可由 Codex 或 pytest 直接执行。
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
OPENMY_CMD = [sys.executable, "-m", "openmy"]


@contextlib.contextmanager
def _isolated_env(*, env_lines: tuple[str, ...] = ()):
    """提供一套完全隔离的运行环境，避免测试之间互相污染。

    OpenMy CLI 启动时会清空所有 OPENMY_* / GEMINI_* 环境变量，只认项目根
    目录下的 .env（见 commands/common.clear_project_runtime_env）。因此要稳定
    控制 STT provider / key，必须给子进程一个独立的项目根（带 pyproject.toml
    和自己的 .env），否则就会读写共享的项目 .env，造成顺序敏感的污染。

    - OPENMY_PROJECT_ROOT：隔离项目根（决定它读哪个 .env，profile.set 也写到
      这里，不会动到真实仓库的 .env）。
    - OPENMY_DATA_DIR：隔离数据目录（status.get 的 total_days 来源，不再依赖
      仓库里残留的 data/ 目录）。

    两个变量都在 paths.py 模块导入时被读取，早于 clear，所以不会被清掉。
    """
    with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as data_dir:
        root = Path(root_dir)
        (root / "pyproject.toml").write_text("[project]\nname = 'openmy-test-sandbox'\n", encoding="utf-8")
        if env_lines:
            (root / ".env").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        env = {"OPENMY_PROJECT_ROOT": str(root), "OPENMY_DATA_DIR": str(data_dir)}
        yield env, Path(data_dir)


def _run_skill(
    action: str,
    *extra_args: str,
    data_root: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict:
    """Run a skill command and return parsed JSON output.

    data_root 通过 OPENMY_DATA_DIR 注入（产品实际读取的就是这个变量，
    早先这里误写成 OPENMY_DATA_ROOT，导致隔离不生效、测试之间共享项目
    data 目录互相污染）。
    """
    env = os.environ.copy()
    if data_root:
        env["OPENMY_DATA_DIR"] = data_root
    if extra_env:
        env.update(extra_env)
    cmd = [*OPENMY_CMD, "skill", action, "--json", *extra_args]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT, env=env)
    # Parse JSON from stdout, ignoring stderr
    stdout = result.stdout.strip()
    if not stdout:
        return {"ok": False, "error": "empty_output", "stderr": result.stderr}
    return json.loads(stdout)


# ──────────────────────────────────────────────────────────────────
# 场景 1：health.check 返回 stt_configured 字段
# ──────────────────────────────────────────────────────────────────

class TestHealthCheck:
    def test_stt_configured_field_exists(self):
        """health.check 必须返回 stt_configured 字段，让 Agent 判断是否需要走引擎选择流程。"""
        payload = _run_skill("health.check")
        assert payload["ok"] is True
        data = payload["data"]
        assert "stt_configured" in data, "health.check 缺少 stt_configured 字段"
        assert isinstance(data["stt_configured"], bool)

    def test_stt_providers_list(self):
        """health.check 必须列出所有可用引擎及 ready 状态。"""
        payload = _run_skill("health.check")
        providers = payload["data"]["stt_providers"]
        assert len(providers) >= 2, "至少应有 faster-whisper 和 funasr"
        names = [p["name"] for p in providers]
        assert "faster-whisper" in names
        assert "funasr" in names

    def test_agent_instructions_embedded(self):
        """health.check 必须嵌入 agent_instructions，让 pip 安装用户的 agent 也能拿到行为规则。"""
        payload = _run_skill("health.check")
        instructions = payload["data"]["agent_instructions"]
        assert "communication" in instructions
        assert "stt_engine_choice" in instructions
        assert "post_install" in instructions
        assert "forbidden" in instructions
        # 关键规则必须提到 HARD STOP
        assert "STOP" in instructions["stt_engine_choice"]


# ──────────────────────────────────────────────────────────────────
# 场景 2：context.query 所有 kind 不崩溃
# ──────────────────────────────────────────────────────────────────

class TestContextQuery:
    @pytest.mark.parametrize("kind", ["open", "closed"])
    def test_no_query_kinds(self, kind):
        """open 和 closed 不需要 --query，应返回 ok=true。"""
        payload = _run_skill("context.query", "--kind", kind)
        assert payload["ok"] is True, f"context.query --kind {kind} 失败: {payload.get('message')}"

    @pytest.mark.parametrize("kind", ["project", "person", "evidence"])
    def test_query_required_kinds(self, kind):
        """project/person/evidence 需要 --query，不传应返回 ok=false（而不是崩溃）。"""
        payload = _run_skill("context.query", "--kind", kind)
        assert payload["ok"] is False, f"context.query --kind {kind} 无 query 应失败"
        assert "query" in payload.get("message", "").lower() or "查询" in payload.get("message", "")

    def test_decision_kind_rejected_by_argparse(self):
        """decision 不是合法的 --kind 值，argparse 应直接拒绝（exit code 2）。"""
        result = subprocess.run(
            [*OPENMY_CMD, "skill", "context.query", "--kind", "decision", "--json"],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 2, "decision kind 应被 argparse 拒绝"
        assert "invalid choice" in result.stderr

    def test_query_with_term(self):
        """project kind + query 应返回结构化结果。"""
        payload = _run_skill("context.query", "--kind", "project", "--query", "OpenMy")
        assert payload["ok"] is True
        result = payload["data"]["result"]
        assert result["kind"] == "project"
        assert "current_hits" in result


# ──────────────────────────────────────────────────────────────────
# 场景 3：correction.apply 失败时返回清晰信息（不能让 Agent 装成功）
# ──────────────────────────────────────────────────────────────────

class TestCorrectionApply:
    def test_close_loop_returns_specific_hint(self):
        """close-loop 失败时 hint 应包含 open_loops 相关指引。"""
        payload = _run_skill(
            "correction.apply",
            "--op", "close-loop",
            "--arg", "不存在的任务标题",
        )
        assert payload["ok"] is False
        hint = payload.get("hint", "") or payload.get("fix", "")
        assert "open_loops" in hint or "context.query" in hint, (
            f"close-loop 失败的 hint 应包含 open_loops 查询指引，实际: {hint}"
        )

    def test_unknown_op_fails_gracefully(self):
        """不存在的 op 应优雅失败。"""
        payload = _run_skill(
            "correction.apply",
            "--op", "nonexistent-op",
            "--arg", "test",
        )
        assert payload["ok"] is False


# ──────────────────────────────────────────────────────────────────
# 场景 4：profile.set 触发 stt_configured 变化
# ──────────────────────────────────────────────────────────────────

class TestProfileStt:
    def test_set_ready_local_stt_makes_configured_true(self):
        """设置一个可用的转写路线后，stt_configured 应为 True。

        干净环境（CI、新用户 clone）不会安装 faster-whisper / funasr 等本地
        引擎，所以本机不一定有 ready 的本地引擎。这里在隔离项目根里注入一个
        带 key 的云引擎（gemini），保证一定有一条可用的转写路线，再验证
        “设置可用引擎 → stt_configured 变 True” 这条核心契约。优先用 ready 的
        本地引擎（装了本地引擎的机器仍走本地），否则退回任意 ready 引擎。
        """
        with _isolated_env(env_lines=("OPENMY_STT_API_KEY=fake-key-for-test",)) as (env, _data):
            before = _run_skill("health.check", extra_env=env)
            providers = before["data"]["stt_providers"]
            ready_local = next(
                (p["name"] for p in providers if p["type"] == "local" and p["ready"]),
                None,
            )
            ready_provider = ready_local or next(
                (p["name"] for p in providers if p["ready"]),
                None,
            )
            assert ready_provider is not None, (
                f"隔离环境里应至少有一个 ready 的转写引擎，实际: {providers}"
            )
            set_payload = _run_skill("profile.set", "--stt-provider", ready_provider, extra_env=env)
            assert set_payload["ok"] is True
            health = _run_skill("health.check", extra_env=env)
            assert health["data"]["stt_configured"] is True

    def test_restore_stt_provider(self):
        """profile.set 能把 provider 切回指定引擎（在隔离环境里自包含验证）。"""
        with _isolated_env() as (env, _data):
            before = _run_skill("health.check", extra_env=env)
            original = before["data"].get("stt_active") or "gemini"
            restore = _run_skill("profile.set", "--stt-provider", original, extra_env=env)
            assert restore["ok"] is True


# ──────────────────────────────────────────────────────────────────
# 场景 5：基础 skill 烟雾测试
# ──────────────────────────────────────────────────────────────────

class TestBasicSkills:
    def test_status_get(self):
        """status.get 的 total_days 来自数据目录里的日期文件夹。

        原来直接打仓库共享的 data/ 目录，total_days 取决于本机/前序测试残留的
        数据——干净 clone 后 data/ 为空，total_days=0，断言就挂；本机有残留时
        又侥幸通过。这里用隔离数据目录预置一天数据，让断言确定。
        """
        with _isolated_env() as (env, data_dir):
            day_dir = data_dir / "2099-01-15"
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "transcript.md").write_text("测试转写内容", encoding="utf-8")
            payload = _run_skill("status.get", extra_env=env)
            assert payload["ok"] is True
            assert payload["data"]["total_days"] > 0

    def test_profile_get(self):
        payload = _run_skill("profile.get")
        assert payload["ok"] is True
        assert "profile" in payload["data"]

    def test_context_get(self):
        payload = _run_skill("context.get")
        assert payload["ok"] is True

    def test_vocab_init(self):
        payload = _run_skill("vocab.init")
        assert payload["ok"] is True

    def test_unknown_action(self):
        """不存在的 action 应返回 unknown_action 而非崩溃。"""
        payload = _run_skill("nonexistent.action")
        assert payload["ok"] is False
        assert payload.get("error_code") == "unknown_action"


# ──────────────────────────────────────────────────────────────────
# 场景 6：demo partial → agent handoff 信号正确
# ──────────────────────────────────────────────────────────────────

class TestDemoPartialHandoff:
    """验证 quick-start --demo 部分完成时，day.run skill 返回正确的 agent 接管信号。"""

    def test_distill_pending_returns_scenes(self):
        """distill.pending 应返回待蒸馏场景列表（demo 数据日期 2099-12-31）。"""
        payload = _run_skill("distill.pending", "--date", "2099-12-31")
        if not payload["ok"]:
            pytest.skip("Demo data not available on this machine")
        data = payload["data"]
        assert data["status"] in ("pending", "already_done")
        if data["status"] == "pending":
            assert len(data["pending_scenes"]) > 0
            scene = data["pending_scenes"][0]
            assert "scene_id" in scene
            assert "text" in scene

    def test_day_run_partial_gives_distill_next_action(self):
        """day.run 返回 partial 时，next_actions 应指向 distill.pending。"""
        payload = _run_skill("day.run", "--date", "2099-12-31", "--skip-transcribe")
        if not payload["ok"] and payload.get("error_code") == "run_failed":
            pytest.skip("Demo data not available on this machine")
        data = payload.get("data", {})
        run_status = data.get("run_status", {})
        if run_status.get("status") == "partial":
            next_actions = payload.get("next_actions", [])
            has_distill_hint = any("distill.pending" in a for a in next_actions)
            has_extract_hint = any("extract.core.pending" in a for a in next_actions)
            assert has_distill_hint or has_extract_hint, (
                f"partial 结果的 next_actions 应包含 distill.pending 或 extract.core.pending, 实际: {next_actions}"
            )
