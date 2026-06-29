#!/usr/bin/env bash
#
# 把 OpenMyApp 可执行文件打包成可双击运行的 OpenMy.app。
#
# 步骤：
#   1. swift build -c release 编译 release 版可执行文件
#   2. 组装 OpenMy.app/Contents/{MacOS,Info.plist} 标准 bundle 结构
#   3. 复制 release 二进制到 Contents/MacOS/OpenMy
#
# 用法：
#   bash scripts/build-app.sh          # 在 macos/ 目录下运行
#   open build/OpenMy.app              # 启动（需后端 localhost:8420 已运行）
#
set -euo pipefail

# 切到脚本所在目录的上一级（即 SwiftPM 包根 macos/），保证相对路径稳定。
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PKG_DIR"

APP_NAME="OpenMy"
EXECUTABLE="OpenMyApp"
BUILD_DIR="build"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
CONTENTS="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS/MacOS"

echo "==> 1/3 编译 release 版本"
swift build -c release

BIN_PATH="$(swift build -c release --show-bin-path)"
SRC_BIN="$BIN_PATH/$EXECUTABLE"
if [[ ! -f "$SRC_BIN" ]]; then
  echo "错误：找不到编译产物 $SRC_BIN" >&2
  exit 1
fi

echo "==> 2/3 组装 app bundle 结构"
rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR"

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>ai.openmy.app</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <!-- 菜单栏常驻 + 主窗口；不是纯后台 agent，所以不设 LSUIElement。 -->
</dict>
</plist>
PLIST

echo "==> 3/3 复制可执行文件"
cp "$SRC_BIN" "$MACOS_DIR/$APP_NAME"
chmod +x "$MACOS_DIR/$APP_NAME"

echo ""
echo "完成：$APP_BUNDLE"
echo "启动前请确认后端已在 localhost:8420 运行，然后："
echo "  open $APP_BUNDLE"
