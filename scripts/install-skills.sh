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

# ─── Step 1: Find a usable Python ≥ 3.10 ───

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      local ver
      ver=$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
      local major minor
      major=$(echo "$ver" | cut -d. -f1)
      minor=$(echo "$ver" | cut -d. -f2)
      if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
        echo "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

echo "🔍 先检查 Python（解释器）环境..."

# If .venv already exists and has a good Python, reuse it
if [ -f "$VENV_PYTHON" ]; then
  VENV_VER=$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
  VENV_MAJOR=$(echo "$VENV_VER" | cut -d. -f1)
  VENV_MINOR=$(echo "$VENV_VER" | cut -d. -f2)
  if [ "$VENV_MAJOR" -ge 3 ] && [ "$VENV_MINOR" -ge 10 ]; then
    echo "✅ 已有虚拟环境，Python $VENV_VER"
    NEED_VENV=false
  else
    echo "⚠️  虚拟环境的 Python 太旧（$VENV_VER），需要重建"
    NEED_VENV=true
  fi
else
  NEED_VENV=true
fi

if [ "$NEED_VENV" = true ]; then
  PYTHON_CMD=$(find_python) || {
    echo "❌ 没找到 Python 3.10+。先运行：brew install python@3.13"
    exit 1
  }
  PY_VER=$("$PYTHON_CMD" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  echo "✅ 找到可用的 Python：$PYTHON_CMD ($PY_VER)"

  echo "📦 创建虚拟环境（隔离运行环境）..."
  "$PYTHON_CMD" -m venv "$VENV_DIR"
fi

# ─── Step 2: Install OpenMy ───

if ! "$VENV_PYTHON" -c "import openmy" 2>/dev/null; then
  echo "📦 安装 OpenMy（项目）本体..."
  "$VENV_PYTHON" -m pip install --upgrade pip >/dev/null
  "$VENV_PYTHON" -m pip install -e "$PROJECT_ROOT[local]"
else
  echo "✅ OpenMy 已安装"
fi

if [ ! -f "$PROJECT_ROOT/.env" ] && [ -f "$PROJECT_ROOT/.env.example" ]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
  echo "📝 已创建 .env（环境文件）"
fi

# ─── Step 3: Create PATH shim ───

mkdir -p "$LOCAL_BIN_DIR"
cat > "$OPENMY_SHIM" <<EOF
#!/usr/bin/env bash
exec "$VENV_OPENMY" "\$@"
EOF
chmod +x "$OPENMY_SHIM"

echo "🔍 验证 openmy（命令）..."
"$OPENMY_SHIM" --help >/dev/null

# ─── Step 4: Link skills to all detected agent platforms ───

echo ""
echo "🔍 检测已安装的智能编程工具..."
echo ""

installed=0
skipped=0
fixed=0

link_skills() {
  local target_dir="$1"

  mkdir -p "$target_dir"

  for skill_dir in "$SKILLS_SRC"/openmy*; do
    [ -d "$skill_dir" ] || continue
    local skill_name
    skill_name="$(basename "$skill_dir")"
    local link_path="$target_dir/$skill_name"

    if [ -L "$link_path" ]; then
      # Check if the symlink is valid and points to the right place
      if [ ! -e "$link_path" ]; then
        # Broken symlink — fix it
        rm "$link_path"
        ln -s "$skill_dir" "$link_path"
        echo "  🔧 ${skill_name}（修复断链）"
        fixed=$((fixed + 1))
      elif [ "$(readlink "$link_path")" != "$skill_dir" ]; then
        # Points to wrong location — update it
        rm "$link_path"
        ln -s "$skill_dir" "$link_path"
        echo "  🔧 ${skill_name}（更新路径）"
        fixed=$((fixed + 1))
      else
        echo "  ✅ ${skill_name}（已链接）"
      fi
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
  echo "📎 检测到 Claude Code"
  link_skills "$HOME/.claude/skills"
  echo ""
else
  echo "⏭  没检测到 Claude Code"
fi

if [ -d "$HOME/.codex" ]; then
  echo "📦 检测到 Codex"
  link_skills "$HOME/.agents/skills"
  echo ""
else
  echo "⏭  没检测到 Codex"
fi

if [ -d "$HOME/.gemini" ]; then
  echo "💎 检测到 Gemini CLI / Antigravity（反重力）"
  link_skills "$HOME/.gemini/skills"
  echo ""
else
  echo "⏭  没检测到 Gemini CLI / Antigravity"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 安装完成"
echo "   - 虚拟环境：$VENV_DIR"
echo "   - 命令入口：$OPENMY_SHIM"
echo "   - 新链接技能数：$installed"
echo "   - 修复链接数：$fixed"
echo "   - 跳过数量：$skipped"
echo ""
echo "👉 下一步：openmy quick-start --demo"
