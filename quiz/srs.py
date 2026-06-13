"""
SM-2 间隔重复算法 — 学习状态管理与持久化

每个词条（card）记录：
  - level / kanji / furigana          (标识)
  - ease_factor (初始 2.5)            (难度系数)
  - interval (天)                     (当前间隔)
  - repetitions                       (连续答对次数)
  - next_review (ISO 日期)            (下次复习日)
  - last_reviewed (ISO 日期)          (上次复习日)
  - total_correct / total_wrong       (全生命周期统计)
"""

import json
from datetime import date, timedelta
from pathlib import Path

SRS_FILE = Path(__file__).parent / '_srs_data.json'


def card_key(word: dict) -> str:
    """词条唯一标识：level:kanji:furigana"""
    lv = word.get('_level', '')
    kj = word.get('kanji', '') or ''
    fr = word.get('furigana', '') or ''
    return f'{lv}:{kj}:{fr}'


def _load() -> dict:
    if not SRS_FILE.exists():
        return {}
    try:
        with open(SRS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict):
    SRS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SRS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_or_create(word: dict) -> dict:
    """获取词条的 SRS 状态，不存在则初始化"""
    data = _load()
    key = card_key(word)
    if key not in data:
        data[key] = {
            'level': word.get('_level', ''),
            'kanji': word.get('kanji', '') or '',
            'furigana': word.get('furigana', '') or '',
            'ease_factor': 2.5,
            'interval': 0,
            'repetitions': 0,
            'next_review': None,
            'last_reviewed': None,
            'total_correct': 0,
            'total_wrong': 0,
        }
        _save(data)
    return data[key]


def _update_raw(word: dict, updates: dict):
    """底层写入（不重新加载，保证原子性）"""
    data = _load()
    key = card_key(word)
    if key not in data:
        return
    data[key].update(updates)
    _save(data)


# ── SM-2 核心 ──────────────────────────────────

MIN_EF = 1.3


def _next_ef(ef: float, quality: int) -> float:
    """
    quality: 0-5
      5 — 完美
      4 — 正确，略有犹豫
      3 — 正确，但回忆困难
      2 — 错误，但答案看起来眼熟
      1 — 错误，完全不记得
      0 — 完全黑屏
    """
    new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return max(MIN_EF, new_ef)


def grade_from_correct(is_correct: bool) -> int:
    """将答题正确/错误映射为 SM-2 quality"""
    return 4 if is_correct else 1


def review(word: dict, is_correct: bool):
    """
    答题后更新 SRS 状态。
    调用方在答题时调用此函数（无论是否错题复习模式）。
    """
    quality = grade_from_correct(is_correct)
    data = _load()
    key = card_key(word)
    if key not in data:
        get_or_create(word)
        data = _load()  # reload after create

    card = data[key]
    today = date.today().isoformat()
    ef = card.get('ease_factor', 2.5)
    reps = card.get('repetitions', 0)
    interval = card.get('interval', 0)

    if quality >= 3:
        # 回答正确
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ef)
        reps += 1
        card['total_correct'] = card.get('total_correct', 0) + 1
    else:
        # 回答错误 → 重置
        reps = 0
        interval = 1
        ef = _next_ef(ef, quality)
        card['total_wrong'] = card.get('total_wrong', 0) + 1

    ef = _next_ef(ef, quality)
    next_review = (date.today() + timedelta(days=interval)).isoformat()

    card.update({
        'ease_factor': round(ef, 2),
        'interval': interval,
        'repetitions': reps,
        'next_review': next_review,
        'last_reviewed': today,
    })
    _save(data)


def is_due(word: dict) -> bool:
    """判断词条今天是否需要复习"""
    data = _load()
    key = card_key(word)
    card = data.get(key)
    if card is None:
        return True  # 新词 → 视为待学
    next_review = card.get('next_review')
    if next_review is None:
        return True
    return next_review <= date.today().isoformat()


def get_due_count(levels: list[str]) -> int:
    """今天到期的词数（按级别筛选）"""
    data = _load()
    today = date.today().isoformat()
    count = 0
    for key, card in data.items():
        if card.get('level') not in levels:
            continue
        nr = card.get('next_review')
        if nr is None or nr <= today:
            count += 1
    return count


def get_new_count(levels: list[str], pool: dict) -> int:
    """从未学过的词数"""
    data = _load()
    count = 0
    for lv in levels:
        for w in pool.get(lv, []):
            key = card_key({'_level': lv, **w})
            if key not in data:
                count += 1
    return count


def get_learned_count(levels: list[str]) -> int:
    """已掌握词数（repetitions >= 3，视为已掌握）"""
    data = _load()
    count = 0
    for key, card in data.items():
        if card.get('level') not in levels:
            continue
        if card.get('repetitions', 0) >= 3:
            count += 1
    return count


def get_review_stats(levels: list[str]) -> dict:
    """复习概览：到期 / 新词 / 已掌握 / 总卡片数"""
    data = _load()
    today = date.today().isoformat()
    due = new = learned = total = 0
    for key, card in data.items():
        if card.get('level') not in levels:
            continue
        total += 1
        nr = card.get('next_review')
        if nr is None or nr <= today:
            due += 1
        if card.get('repetitions', 0) >= 3:
            learned += 1
    return {'due': due, 'learned': learned, 'total': total}


def reset_word(word: dict):
    """重置单个词的 SRS 状态"""
    data = _load()
    key = card_key(word)
    data.pop(key, None)
    _save(data)
