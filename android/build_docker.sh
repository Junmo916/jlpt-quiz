#!/bin/bash
# ── 日文背词 — Docker APK 构建（替代 WSL） ──
# 需要先安装 Docker Desktop for Windows
# 在 PowerShell 中运行: docker run ...

set -e

IMAGE="kivy/buildozer:latest"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== 使用 Docker 构建 APK ==="
echo "首次运行会自动下载 buildozer 镜像（约 1GB）"
echo ""

docker run --rm -it \
    -v "$DIR":/home/user/app \
    -v "$DIR/.buildozer":/home/user/.buildozer \
    "$IMAGE" \
    bash -c "cd /home/user/app && buildozer android debug"

echo ""
echo "=== 构建完成！ ==="
echo "APK 位置: $DIR/bin/*.apk"
