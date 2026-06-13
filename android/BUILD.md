# 日文背词 — Android APK 构建指南

## 方法一：GitHub Actions（推荐，零本地配置）

不需要安装任何工具，APK 在云端自动构建。

1. 创建 GitHub 仓库并推送代码
2. 在 GitHub 仓库页面点击 **Actions** → **Build Android APK** → **Run workflow**
3. 等 15-30 分钟构建完成 → 下载 `jlptquiz-apk` 构件中的 `.apk` 文件

或者，推送代码后每次推送到 `main` 分支都会自动构建。

## 方法二：WSL

Windows 上推荐用 WSL 构建。一键脚本会安装所有依赖。

```powershell
# 1. 安装 WSL（管理员 PowerShell）
wsl --install -d Ubuntu
# 重启后完成设置

# 2. 在 WSL 中运行构建
cd /mnt/d/opencode/projects/jlpt-quiz/android
chmod +x build_apk.sh
./build_apk.sh
```

等待首次构建下载 SDK/NDK（约 2-5 分钟），APK 会生成在 `android/bin/` 目录。

## 方法二：Docker

如果安装了 Docker Desktop，也可以直接用 Docker 构建：

```powershell
# 在 PowerShell 中运行
cd D:\opencode\projects\jlpt-quiz\android
# 使用 WSL 中的 bash 或 Git Bash
bash build_docker.sh
```

## 方法三：Google Colab（无需本地安装）

1. 新建 Colab Notebook
2. 运行以下命令：

```python
!pip install buildozer
!git clone https://github.com/your-repo/jlpt-quiz.git
%cd jlpt-quiz/android
!buildozer android debug
```

然后下载生成的 APK。

## 安装到手机

构建成功后，APK 文件在 `android/bin/` 目录：

```
bin/jlptquiz-1.1.0-arm64-v8a_armeabi-v7a-debug.apk
```

安装方式：
- **USB 连接**：`adb install bin/jlptquiz-*-debug.apk`
- **复制到手机**：通过 USB/蓝牙/云盘复制到手机，点击安装
- **开启"允许安装未知来源应用"**（设置 → 安全 → 未知来源）

## 目录结构

```
android/
├── main.py              # KivyMD 应用主代码
├── jlptquiz.kv          # Kivy 布局文件
├── buildozer.spec       # APK 构建配置
├── build_apk.sh         # WSL 一键构建脚本
├── build_docker.sh      # Docker 构建脚本
├── BUILD.md             # 本文件
├── data/                # 词汇数据（JSON）
│   ├── N5.json
│   ├── N4.json
│   ├── N3.json
│   ├── N2.json
│   ├── N1.json
│   └── meta.json
└── bin/                 # 构建产物（APK）
```

## 调试

如果构建失败或运行出错：

1. **查看构建日志**：`buildozer android debug 2>&1 | tee build.log`
2. **查看运行时日志**：
   ```bash
   adb logcat -s python:V
   ```
3. **常见问题**：
   - NDK/SDK 下载失败 → 检查网络/代理
   - KivyMD 兼容性 → 检查 `buildozer.spec` 中的版本号
   - 权限问题 → 确保 `data/` 目录中有 JSON 文件
