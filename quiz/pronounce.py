"""
发音支持 — Windows SAPI TTS

使用 Windows 内置的 SAPI.SpVoice 朗读日语文本。
非 Windows 平台静默降级。
"""

import sys
import threading

_HAS_TTS = False
_voice = None

if sys.platform == 'win32':
    try:
        import win32com.client
        _voice = win32com.client.Dispatch('SAPI.SpVoice')
        # 尝试选择日语语音（如果有）
        try:
            for v in _voice.GetVoices():
                if 'japan' in v.GetDescription().lower():
                    _voice.Voice = v
                    break
        except Exception:
            pass
        _HAS_TTS = True
    except Exception:
        _HAS_TTS = False


def speak(text: str):
    """朗读文本（异步，不阻塞 UI）"""
    if not _HAS_TTS or not text:
        return
    # 在后台线程朗读，避免阻塞 Tkinter 主循环
    threading.Thread(target=_speak_sync, args=(text,), daemon=True).start()


def _speak_sync(text: str):
    try:
        _voice.Speak(text)
    except Exception:
        pass


def is_available() -> bool:
    return _HAS_TTS
