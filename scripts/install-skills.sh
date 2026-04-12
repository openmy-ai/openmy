#!/usr/bin/env bash
set -euo pipefail

# OpenMy Skill Installer
# Detects installed AI coding tools and symlinks OpenMy skills into them.
# Usage: bash scripts/install-skills.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SKILLS_SRC="$PROJECT_ROOT/skills"

echo "🔍 Detecting installed AI coding tools..."
echo ""

installed=0
skipped=0

link_skills() {
  local platform="$1"
  local target_dir="$2"

  mkdir -p "$target_dir"

  for skill_dir in "$SKILLS_SRC"/openmy*; do
    [ -d "$skill_dir" ] || continue
    local skill_name
    skill_name="$(basename "$skill_dir")"
    local link_path="$target_dir/$skill_name"

    if [ -L "$link_path" ]; then
      echo "  ✅ $skill_name (already linked)"
    elif [ -d "$link_path" ]; then
      echo "  ⚠️  $skill_name (directory exists, not a link — skipped)"
      ((skipped++)) || true
    else
      ln -s "$skill_dir" "$link_path"
      echo "  🔗 $skill_name → linked"
      ((installed++)) || true
    fi
  done
}

# Claude Code
if [ -d "$HOME/.claude" ]; then
  echo "📎 Claude Code detected"
  link_skills "Claude Code" "$HOME/.claude/skills"
  echo ""
else
  echo "⏭  Claude Code — not installed (~/.claude not found)"
fi

# Codex (uses ~/.agents/skills per native skill discovery)
if [ -d "$HOME/.codex" ]; then
  echo "📦 Codex detected"
  # Codex native discovery uses ~/.agents/skills/
  link_skills "Codex" "$HOME/.agents/skills"
  echo ""
else
  echo "⏭  Codex — not installed (~/.codex not found)"
fi

# Gemini CLI / Antigravity
if [ -d "$HOME/.gemini" ]; then
  echo "💎 Gemini CLI / Antigravity detected"
  link_skills "Gemini" "$HOME/.gemini/skills"
  echo ""
else
  echo "⏭  Gemini CLI / Antigravity — not installed (~/.gemini not found)"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $installed -gt 0 ]; then
  echo "✅ Done — linked $installed skill(s)"
elif [ $skipped -gt 0 ]; then
  echo "⚠️  Done — $skipped skill(s) skipped (directories already exist)"
else
  echo "✅ All skills already in place"
fi
echo "💡 Restart your AI tool to pick up the changes"
