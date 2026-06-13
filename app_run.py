"""
日文背词 — 启动器

用法:
  python app_run.py         桌面版（Tkinter）
  python app_run.py web     Web 版（移动端 PWA，通过 HTTP 访问）
"""

import sys, os, subprocess, webbrowser
from pathlib import Path

BASE = Path(__file__).parent

def start_desktop():
    """启动 Tkinter 桌面版"""
    subprocess.run([sys.executable, str(BASE / 'quiz_app.py')])

def start_web():
    """启动 HTTP 服务器 + 打开浏览器"""
    import http.server
    import socketserver

    PORT = 8090
    web_dir = BASE / 'web'
    os.chdir(web_dir)

    handler = http.server.SimpleHTTPRequestHandler

    print(f'╔══════════════════════════════════════════╗')
    print(f'║  日文背词 — Web 版                        ║')
    print(f'║                                          ║')
    print(f'║  本机访问：                                ║')
    print(f'║  http://localhost:{PORT}                   ║')
    print(f'║                                          ║')
    print(f'║  手机访问（同一 WiFi）：                    ║')
    print(f'║  1. 查看本机 IP: ipconfig                 ║')
    print(f'║  2. 在手机浏览器打开 http://IP:{PORT}       ║')
    print(f'║                                          ║')
    print(f'║  建议在 Chrome 中"添加到主屏幕"以安装为应用  ║')
    print(f'║  Ctrl+C 停止服务器                         ║')
    print(f'╚══════════════════════════════════════════╝')

    with socketserver.TCPServer(('0.0.0.0', PORT), handler) as httpd:
        webbrowser.open(f'http://localhost:{PORT}')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\n服务器已停止')
            httpd.server_close()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'web':
        start_web()
    else:
        start_desktop()
