#!/bin/bash
# ── 日文背词 — APK 构建脚本 ──
# 用法: 在 WSL Ubuntu 中运行
#   cd /path/to/android/
#   chmod +x build_apk.sh
#   ./build_apk.sh

set -e

echo "=== 日文背词 APK 构建 ==="

# 1. 安装系统依赖
echo ""
echo ">>> 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    python3-pip python3-dev python3-venv \
    libssl-dev libffi-dev \
    openjdk-17-jdk-headless \
    git zip unzip autoconf libtool \
    pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake \
    ccache libxcursor-dev libxrandr-dev \
    libxinerama-dev libxi-dev

# 2. 创建虚拟环境
echo ""
echo ">>> 创建 Python 虚拟环境..."
python3 -m venv venv
source venv/bin/activate

# 3. 安装 Buildozer
echo ""
echo ">>> 安装 Buildozer..."
pip install --upgrade pip
pip install buildozer Cython==0.29.37

# 4. 显示 Android SDK 许可（首次需要接受）
echo ""
echo ">>> 设置 Android SDK..."
export ANDROID_HOME="$HOME/.buildozer/android/platform/android-sdk"
export PATH="$ANDROID_HOME/tools/bin:$PATH"

# 5. 构建 APK
echo ""
echo ">>> 开始构建 APK（首次构建会下载 SDK/NDK，约 2-8 分钟）..."
buildozer android debug

echo ""
echo "=== 构建完成！ ==="
echo "APK 位置: $(pwd)/bin/*.apk"
echo ""
echo "将 APK 传输到手机："
echo "  adb install bin/jlptquiz-*-debug.apk"
echo "或通过 USB/蓝牙复制到手机后点击安装"
