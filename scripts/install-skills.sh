#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SKILLS_SRC="$PROJECT_ROOT/skills"
VENV_DIR="$PROJECT_ROOT/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_OPENMY="$VENV_DIR/bin/openmy"
LOCAL_BIN_DIR="$HOME/.local/bin"
OPENMY_SHIM="$LOCAL_BIN_DIR/openmy"

echo "🔍 先检查 Python（解释器）环境..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 没找到 python3（解释器）。先运行：brew install python@3.13"
  exit 1
fi

PYTHON_VERSION="$(
python3 - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PY
)"

python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit(1)
PY
if [ $? -ne 0 ]; then
  echo "❌ Python（解释器）版本太低：$PYTHON_VERSION。先运行：brew install python@3.13"
  exit 1
fi

if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "❌ 这个 Python（解释器）没有 pip（安装器）。先运行：python3 -m ensurepip --upgrade"
  exit 1
fi

echo "✅ Python（解释器）版本可用：$PYTHON_VERSION"
echo "📦 创建虚拟环境（隔离运行环境）..."
python3 -m venv "$VENV_DIR"

echo "📦 安装 OpenMy（项目）本体..."
"$VENV_PYTHON" -m pip install --upgrade pip >/dev/null
"$VENV_PYTHON" -m pip install -e "$PROJECT_ROOT[local]"

if [ ! -f "$PROJECT_ROOT/.env" ] && [ -f "$PROJECT_ROOT/.env.example" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  echo "📝 已创建 .env（环境文件）"
fi

mkdir -p "$LOCAL_BIN_DIR"
cat > "$OPENMY_SHIM" <<EOF
#!/usr/bin/env bash
exec "$VENV_OPENMY" "\$@"
EOF
chmod +x "$OPENMY_SHIM"

echo "🔍 验证 openmy（命令）..."
"$OPENMY_SHIM" --help >/dev/null

echo ""
echo "🔍 检测已安装的智能编程工具..."
echo ""

installed=0
skipped=0

link_skills() {
  local target_dir="$1"

  mkdir -p "$target_dir"

  for skill_dir in "$SKILLS_SRC"/openmy*; do
    [ -d "$skill_dir" ] || continue
    local skill_name
    skill_name="$(basename "$skill_dir")"
    local link_path="$target_dir/$skill_name"

    if [ -L "$link_path" ]; then
      echo "  ✅ ${skill_name}（已链接）"
    elif [ -d "$link_path" ]; then
      echo "  ⚠️  ${skill_name}（已有同名目录，跳过）"
      skipped=$((skipped + 1))
    else
      ln -s "$skill_dir" "$link_path"
      echo "  🔗 ${skill_name}（已链接）"
      installed=$((installed + 1))
    fi
  done
}

if [ -d "$HOME/.claude" ]; then
  echo "📎 检测到 Claude Code（工具）"
  link_skills "$HOME/.claude/skills"
  echo ""
else
  echo "⏭  没检测到 Claude Code（工具）"
fi

if [ -d "$HOME/.codex" ]; then
  echo "📦 检测到 Codex（工具）"
  link_skills "$HOME/.agents/skills"
  echo ""
else
  echo "⏭  没检测到 Codex（工具）"
fi

if [ -d "$HOME/.gemini" ]; then
  echo "💎 检测到 Gemini CLI（命令行工具）"
  link_skills "$HOME/.gemini/skills"
  echo ""
else
  echo "⏭  没检测到 Gemini CLI（命令行工具）"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 安装完成，运行 openmy quick-start（快速开始）开始"
echo "   - 虚拟环境：$VENV_DIR"
echo "   - 命令入口：$OPENMY_SHIM"
echo "   - 新链接技能数：$installed"
echo "   - 跳过数量：$skipped"
