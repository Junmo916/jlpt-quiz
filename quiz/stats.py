"""
学习统计追踪 — 按天 / 累计 / 按级别

记录每次答题：
  - 日期
  - 级别
  - 总题数
  - 正确数
  - 错误数

支持按时间范围查询、汇总。
"""

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

STATS_FILE = Path(__file__).parent / '_stats.json'


def _load() -> dict:
    if not STATS_FILE.exists():
        return {'days': {}, 'by_level': {}, 'streak': 0, 'last_active': None}
    try:
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {'days': {}, 'by_level': {}, 'streak': 0, 'last_active': None}


def _save(data: dict):
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_session(
    levels: list[str],
    total: int,
    correct: int,
    incorrect: int,
):
    """记录一轮答题结果"""
    data = _load()
    today = date.today().isoformat()

    # ── 每日汇总 ──
    day = data['days'].get(today, {'total': 0, 'correct': 0, 'incorrect': 0})
    day['total'] += total
    day['correct'] += correct
    day['incorrect'] += incorrect
    data['days'][today] = day

    # ── 按级别 ──
    lv_str = '+'.join(sorted(levels))
    lv_entry = data['by_level'].get(lv_str, {'total': 0, 'correct': 0, 'incorrect': 0})
    lv_entry['total'] += total
    lv_entry['correct'] += correct
    lv_entry['incorrect'] += incorrect
    data['by_level'][lv_str] = lv_entry

    # ── 连续活跃天数 ──
    data['last_active'] = today
    data['streak'] = _recalc_streak(data['days'], today)

    _save(data)


def _recalc_streak(days: dict, today: str) -> int:
    """从今天向前计算连续活跃天数"""
    dt = date.fromisoformat(today)
    streak = 0
    for _ in range(365):
        if days.get(dt.isoformat(), {}).get('total', 0) > 0:
            streak += 1
            dt -= timedelta(days=1)
        else:
            break
    return streak


# ── 查询接口 ──────────────────────────────────


def today_stats() -> dict:
    """今日学习量"""
    data = _load()
    today = date.today().isoformat()
    day = data['days'].get(today, {'total': 0, 'correct': 0, 'incorrect': 0})
    return day


def overall_stats() -> dict:
    """全部历史汇总"""
    data = _load()
    days = data['days']
    total = sum(d['total'] for d in days.values())
    correct = sum(d['correct'] for d in days.values())
    incorrect = sum(d['incorrect'] for d in days.values())
    return {
        'total_sessions': len(days),
        'total_attempts': total,
        'total_correct': correct,
        'total_incorrect': incorrect,
        'accuracy': round(correct / total * 100, 1) if total else 0,
        'streak': data.get('streak', 0),
        'last_active': data.get('last_active', ''),
    }


def recent_days(n: int = 7) -> list[dict]:
    """最近 n 天每日数据"""
    data = _load()
    result = []
    for i in range(n - 1, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        day = data['days'].get(d, {'total': 0, 'correct': 0, 'incorrect': 0})
        result.append({'date': d, **day})
    return result


def get_streak() -> int:
    data = _load()
    return data.get('streak', 0)
