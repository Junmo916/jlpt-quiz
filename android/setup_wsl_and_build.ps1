<#
  日文背词 — WSL 安装 + APK 构建 一键脚本
  以管理员身份运行：
   右键 →"以 PowerShell 运行" 或
   powershell -ExecutionPolicy Bypass -File setup_wsl_and_build.ps1
#>

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  日文背词 — Android APK 构建              ║" -ForegroundColor Cyan
Write-Host "║  此脚本将：                               ║" -ForegroundColor Cyan
Write-Host "║  1. 安装 WSL + Ubuntu                     ║" -ForegroundColor Cyan
Write-Host "║  2. 安装 Buildozer + 依赖                  ║" -ForegroundColor Cyan
Write-Host "║  3. 构建 APK                               ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 检查管理员权限 ──
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "❌ 请以管理员身份运行！" -ForegroundColor Red
    Write-Host "   右键 PowerShell → 以管理员身份运行" -ForegroundColor Yellow
    pause
    exit 1
}

# ── 步骤 1: 安装 WSL ──
Write-Host ">>> 步骤 1/4: 安装 WSL + Ubuntu..." -ForegroundColor Green
wsl --install -d Ubuntu
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  WSL 安装可能需要重启。重启后重新运行此脚本。" -ForegroundColor Yellow
    Write-Host "    或者手动运行: wsl --install -d Ubuntu" -ForegroundColor Yellow
    pause
    exit
}

Write-Host "✅ WSL 安装成功！" -ForegroundColor Green
Write-Host "⚠️  首次启动 WSL 时需要创建 Linux 用户名和密码。" -ForegroundColor Yellow
Write-Host "   按任意键启动 WSL 进行首次配置..." -ForegroundColor Yellow
pause

# ── 步骤 2: 首次配置 WSL ──
wsl -d Ubuntu -- bash -c "echo 'WSL 就绪'"
Write-Host "✅ WSL 首次配置完成。" -ForegroundColor Green

# ── 步骤 3: 复制文件并安装依赖 ──
Write-Host ">>> 步骤 2/4: 复制项目文件到 WSL..." -ForegroundColor Green
$wslPath = "/home/$(wsl -d Ubuntu -- bash -c 'whoami')/jlpt-quiz"
wsl -d Ubuntu -- mkdir -p $wslPath
wsl -d Ubuntu -- cp -r "$scriptDir/." "$wslPath/"
wsl -d Ubuntu -- cp -r "$(Resolve-Path "$scriptDir/../quiz/data").Path" "$wslPath/data/"

Write-Host ">>> 步骤 3/4: 安装 Buildozer 依赖..." -ForegroundColor Green
wsl -d Ubuntu -- bash -c "
    cd '$wslPath'
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3-pip python3-dev python3-venv libssl-dev libffi-dev
    sudo apt-get install -y -qq openjdk-17-jdk-headless git zip unzip autoconf libtool
    sudo apt-get install -y -qq pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev
    sudo apt-get install -y -qq cmake ccache
    pip3 install --upgrade pip
    pip3 install buildozer Cython==0.29.37
"

# ── 步骤 4: 构建 APK ──
Write-Host ">>> 步骤 4/4: 开始构建 APK（首次会下载 SDK/NDK，约 2-8 分钟）..." -ForegroundColor Green
Write-Host "    构建过程中请保持网络畅通..." -ForegroundColor Yellow

wsl -d Ubuntu -- bash -c "
    cd '$wslPath'
    export ANDROID_HOME=\$HOME/.buildozer/android/platform/android-sdk
    buildozer android debug 2>&1
"

# ── 完成 ──
$apkFiles = Get-ChildItem "$scriptDir/bin/*.apk" -ErrorAction SilentlyContinue
if ($apkFiles) {
    Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║  ✅ 构建成功！                            ║" -ForegroundColor Green
    Write-Host "║                                          ║" -ForegroundColor Green
    Write-Host "║  APK 位置：                               ║" -ForegroundColor Green
    foreach ($apk in $apkFiles) {
        Write-Host "║  $($apk.FullName)  ║" -ForegroundColor Green
    }
    Write-Host "║                                          ║" -ForegroundColor Green
    Write-Host "║  安装到手机：                             ║" -ForegroundColor Green
    Write-Host "║  1. 将 APK 复制到手机                     ║" -ForegroundColor Green
    Write-Host "║  2. 在手机上点击安装                      ║" -ForegroundColor Green
    Write-Host "║  3. 开启"允许安装未知来源应用"              ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Green
} else {
    Write-Host "⚠️  构建可能未成功，请检查上方日志。" -ForegroundColor Yellow
    Write-Host "   也可手动在 WSL 中运行: cd ~/jlpt-quiz && buildozer android debug" -ForegroundColor Yellow
}

pause
