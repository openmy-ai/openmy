"""OpenMy 全局配置 — 模型、思考级别等统一管理"""

# ── 模型配置 ──────────────────────────────────────────────
# 改这一个地方，所有模块（清洗/蒸馏/提取/转写）都会跟着变
GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

# ── 思考级别 ──────────────────────────────────────────────
# "none" / "low" / "medium" / "high"
# 提取需要深度推理，用 high；清洗只是文本处理，用 low
THINKING_LEVEL_EXTRACT = "high"      # 提取 intents/facts
THINKING_LEVEL_CLEAN = "low"         # 清洗转写文本
THINKING_LEVEL_DISTILL = "medium"    # 蒸馏场景摘要
