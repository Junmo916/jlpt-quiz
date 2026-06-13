[app]

# ── 应用信息 ──
title = 日文背词
package.name = jlptquiz
package.domain = org.jlptquiz
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf,json,txt
source.include_patterns = data/*.json

# ── 版本 ──
version = 1.0.0
version.regex = __version__ = ['"](.*)['"]
version.filename = %(source.dir)s/main.py

# ── 依赖 ──
requirements = python3,kivy==2.3.0,kivymd==2.0.1,plyer

# ── 权限 ──
android.permissions = INTERNET

# ── Android 配置 ──
android.api = 34
android.minapi = 21
android.sdk = 34
android.ndk = 25.1.8937393
android.accept_sdk_license = True
android.gradle_dependencies = 
android.java_source = 17
android.java_target = 17
android.archs = arm64-v8a
android.manifest_placeholders =

# ── UI ──
android.wakelock = False
android.fullscreen = 0
android.window_size = 1080x1920
android.allow_backup = True
android.recents = 
android.selector_image = 

# ── 图标 (使用内置占位图) ──
# 替换为自定义图标：presplash.png, icon.png
icon = 
presplash = 

# ── 通知 ──
android.notch = True
android.override_attribution = False
android.enable_deprecated = False

# ── 日志 ──
android.logcat_filters = *:S python:V

# ── 调试（首次构建开 debug，方便排错） ──
android.release_mode = False
android.debug_mode = True
android.archs_debug = arm64-v8a

[buildozer]
log_level = 2
warn_on_root = 1

# ── 输出目录（APK 生成位置） ──
export_dir = ./bin
