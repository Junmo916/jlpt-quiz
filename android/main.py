"""
日文背词 — JLPT 10k 填空练习（KivyMD Android 版）
=====================================================
依赖: kivy, kivymd
打包: buildozer
"""

import json, os, random, sys, math
from datetime import date, timedelta
from pathlib import Path

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.core.window import Window
from kivy.animation import Animation

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDRaisedButton, MDFlatButton, MDIconButton
from kivymd.uix.textfield import MDTextField
from kivymd.uix.label import MDLabel
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.dialog import MDDialog
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.list import OneLineListItem, TwoLineListItem, ThreeLineListItem
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.checkbox import MDCheckbox
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.relativelayout import MDRelativeLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.properties import StringProperty, NumericProperty, BooleanProperty
from kivy.uix.behaviors import FocusBehavior

# ── 配置 ──────────────────────────────────────
DATA_DIR = Path(__file__).parent / 'data'
LEVELS = ['N5', 'N4', 'N3', 'N2', 'N1']
LEVEL_LABELS = {
    'N5': 'N5（入门）', 'N4': 'N4（基础）',
    'N3': 'N3（中级）', 'N2': 'N2（中上级）', 'N1': 'N1（上级）',
}
MIN_EF = 1.3

# ── 数据加载 ──────────────────────────────────

WORD_POOL = {}

def load_word_data():
    for lv in LEVELS:
        path = DATA_DIR / f'{lv}.json'
        with open(str(path), 'r', encoding='utf-8') as f:
            data = json.load(f)
        WORD_POOL[lv] = data['words']

# ── 工具函数 ──────────────────────────────────

def card_key(word):
    lv = word.get('_level', '')
    kj = word.get('kanji', '') or ''
    fr = word.get('furigana', '') or ''
    return f'{lv}:{kj}:{fr}'

def normalize(s):
    s = (s or '').strip().replace(' ', '').replace('\u3000', '')
    result = []
    for ch in s:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(ch)
    return ''.join(result).lower()

def match_furigana(user, correct):
    if not (user or '').strip():
        return False
    a, b = normalize(user), normalize(correct)
    if a == b:
        return True
    if b.startswith(a) and len(a) >= 2:
        return True
    if a.startswith(b) and len(b) >= 2:
        return True
    return False

def match_meaning(user, correct):
    if not (user or '').strip() or not correct:
        return False
    a, b = normalize(user), normalize(correct)
    if a == b:
        return True
    if len(a) >= 2 and b.find(a) != -1:
        return True
    if len(b) >= 2 and a.find(b) != -1:
        return True
    return False

def match_kanji(user, correct):
    if not (user or '').strip():
        return False
    return normalize(user) == normalize(correct)

def build_question(word, qtype):
    kanji = word.get('kanji', '')
    furi = word.get('furigana', '')
    sc = word.get('def_sc', '')
    if qtype == 'jp2cn':
        return {'type': 'jp2cn', 'label': '日译中', 'answer': sc,
                'check': lambda u, k: match_meaning(u, sc)}
    else:
        return {'type': 'cn2jp', 'label': '中译日',
                'answer': f'{kanji}（{furi}）',
                'check': lambda u, k: match_kanji(k, kanji) and match_furigana(u, furi)}

# ── 存储路径（Android vs 桌面） ────────────────

def get_data_dir():
    app = MDApp.get_running_app()
    if platform == 'android':
        return app.user_data_dir
    return str(Path(__file__).parent)

SRS_FILE = None
STATS_FILE = None
WRONG_FILE = None
PROGRESS_FILE = None

def init_storage():
    global SRS_FILE, STATS_FILE, WRONG_FILE, PROGRESS_FILE
    d = get_data_dir()
    SRS_FILE = os.path.join(d, '_srs.json')
    STATS_FILE = os.path.join(d, '_stats.json')
    WRONG_FILE = os.path.join(d, '_wrong.json')
    PROGRESS_FILE = os.path.join(d, '_progress.json')

def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default

def _write_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

# ── SRS ──────────────────────────────────────

def srs_get_or_create(word):
    data = _read_json(SRS_FILE, {})
    key = card_key(word)
    if key not in data:
        data[key] = {
            'level': word.get('_level', ''), 'kanji': word.get('kanji', '') or '',
            'furigana': word.get('furigana', '') or '',
            'ease_factor': 2.5, 'interval': 0, 'repetitions': 0,
            'next_review': None, 'last_reviewed': None,
            'total_correct': 0, 'total_wrong': 0,
        }
        _write_json(SRS_FILE, data)
    return data[key]

def srs_review(word, is_correct):
    quality = 4 if is_correct else 1
    data = _read_json(SRS_FILE, {})
    key = card_key(word)
    if key not in data:
        srs_get_or_create(word)
        data = _read_json(SRS_FILE, {})
    card = data[key]
    today = date.today().isoformat()
    ef = card.get('ease_factor', 2.5)
    reps = card.get('repetitions', 0)
    interval = card.get('interval', 0)

    if quality >= 3:
        if reps == 0: interval = 1
        elif reps == 1: interval = 6
        else: interval = round(interval * ef)
        reps += 1
        card['total_correct'] = card.get('total_correct', 0) + 1
    else:
        reps = 0; interval = 1
        ef = max(MIN_EF, ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
        card['total_wrong'] = card.get('total_wrong', 0) + 1

    ef = max(MIN_EF, ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    next_review = (date.today() + timedelta(days=interval)).isoformat()
    card.update({
        'ease_factor': round(ef, 2), 'interval': interval,
        'repetitions': reps, 'next_review': next_review, 'last_reviewed': today,
    })
    _write_json(SRS_FILE, data)

def srs_is_due(word):
    data = _read_json(SRS_FILE, {})
    card = data.get(card_key(word))
    if not card: return True
    nr = card.get('next_review')
    if not nr: return True
    return nr <= date.today().isoformat()

def srs_stats(levels):
    data = _read_json(SRS_FILE, {})
    today = date.today().isoformat()
    due = learned = total = 0
    for c in data.values():
        if c.get('level') not in levels: continue
        total += 1
        if c.get('repetitions', 0) >= 3: learned += 1
        nr = c.get('next_review')
        if not nr or nr <= today: due += 1
    return {'due': due, 'learned': learned, 'total': total}

def srs_learned_count(levels):
    data = _read_json(SRS_FILE, {})
    return sum(1 for c in data.values()
               if c.get('level') in levels and c.get('repetitions', 0) >= 3)

def srs_new_count(levels):
    data = _read_json(SRS_FILE, {})
    count = 0
    for lv in levels:
        for w in WORD_POOL.get(lv, []):
            key = card_key({'_level': lv, **w})
            if key not in data: count += 1
    return count

# ── Wrong Bank ──────────────────────────────

def wb_all():
    return _read_json(WRONG_FILE, {})

def wb_total():
    bank = wb_all()
    return sum(len(v) for v in bank.values())

def wb_add(level, word):
    bank = wb_all()
    if level not in bank: bank[level] = []
    key = f"{word.get('kanji','')}|{word.get('furigana','')}"
    found = next((e for e in bank[level] if f"{e.get('kanji','')}|{e.get('furigana','')}" == key), None)
    if found:
        found['wrong_count'] = found.get('wrong_count', 0) + 1
    else:
        entry = dict(word); entry.pop('_level', None); entry['wrong_count'] = 1
        bank[level].append(entry)
    _write_json(WRONG_FILE, bank)

def wb_remove(level, word):
    bank = wb_all()
    if level not in bank: return
    key = f"{word.get('kanji','')}|{word.get('furigana','')}"
    bank[level] = [e for e in bank[level] if f"{e.get('kanji','')}|{e.get('furigana','')}" != key]
    if not bank[level]: del bank[level]
    _write_json(WRONG_FILE, bank)

def wb_clear():
    _write_json(WRONG_FILE, {})

# ── Stats ────────────────────────────────────

def stats_record(levels, total, correct, incorrect):
    data = _read_json(STATS_FILE, {'days': {}, 'by_level': {}, 'streak': 0, 'last_active': None})
    today = date.today().isoformat()
    day = data['days'].get(today, {'total': 0, 'correct': 0, 'incorrect': 0})
    day['total'] += total; day['correct'] += correct; day['incorrect'] += incorrect
    data['days'][today] = day
    lk = '+'.join(sorted(levels))
    lv = data['by_level'].get(lk, {'total': 0, 'correct': 0, 'incorrect': 0})
    lv['total'] += total; lv['correct'] += correct; lv['incorrect'] += incorrect
    data['by_level'][lk] = lv
    data['last_active'] = today
    # recalc streak
    dt = date.today()
    s = 0
    for _ in range(365):
        if data['days'].get(dt.isoformat(), {}).get('total', 0) > 0:
            s += 1; dt -= timedelta(days=1)
        else: break
    data['streak'] = s
    _write_json(STATS_FILE, data)

def stats_overall():
    data = _read_json(STATS_FILE, {'days': {}, 'by_level': {}, 'streak': 0, 'last_active': None})
    total = correct = incorrect = 0
    for d in data['days'].values():
        total += d['total']; correct += d['correct']; incorrect += d['incorrect']
    return {
        'sessions': len(data['days']), 'total': total,
        'correct': correct, 'incorrect': incorrect,
        'accuracy': round(correct / total * 100, 1) if total else 0,
        'streak': data.get('streak', 0),
    }

# ── Progress ────────────────────────────────

def progress_save(levels, pool):
    _write_json(PROGRESS_FILE, {'levels': levels, 'remaining': pool})
def progress_load():
    return _read_json(PROGRESS_FILE, None)
def progress_clear():
    try: os.remove(PROGRESS_FILE)
    except FileNotFoundError: pass

# ═══════════════════════════════════════════════
#  KivyMD Screens
# ═══════════════════════════════════════════════

class SetupScreen(MDScreen):
    def on_enter(self):
        app = MDApp.get_running_app()
        self.ids.level_box.clear_widgets()
        for lv in LEVELS:
            box = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(48),
                              padding=[dp(16), 0, dp(16), 0], spacing=dp(8))
            cb = MDCheckbox(size_hint=(None, None), size=(dp(48), dp(48)),
                            active=lv in app.selected_levels)
            cb.bind(active=lambda inst, val, l=lv: self._toggle_level(l, val))
            lbl = MDLabel(text=f'{LEVEL_LABELS[lv]}（{len(WORD_POOL.get(lv, []))} 词）',
                          font_size=sp(15), theme_text_color='Secondary')
            box.add_widget(cb); box.add_widget(lbl)
            self.ids.level_box.add_widget(box)
        self._update_info()

    def _toggle_level(self, lv, active):
        app = MDApp.get_running_app()
        if active:
            if lv not in app.selected_levels: app.selected_levels.append(lv)
        else:
            app.selected_levels = [l for l in app.selected_levels if l != lv]
        self._update_info()

    def _update_info(self):
        app = MDApp.get_running_app()
        sel = app.selected_levels
        total = sum(len(WORD_POOL.get(lv, [])) for lv in sel)
        if sel:
            ss = srs_stats(sel)
            info = (f'已选 {len(sel)} 个级别，共 {total} 词\n'
                    f'待复习 {ss["due"]}  已掌握 {ss["learned"]}  新词 {srs_new_count(sel)}')
            o = stats_overall()
            self.ids.level_info.text = info
            self.ids.streak_info.text = f'累计正确率 {o["accuracy"]}% · 连续 {o["streak"]} 天'
            self.ids.streak_info.opacity = 1
            self.ids.btn_start.disabled = False
        else:
            self.ids.level_info.text = '请至少选择一个级别'
            self.ids.streak_info.opacity = 0
            self.ids.btn_start.disabled = True

    def start_quiz(self):
        app = MDApp.get_running_app()
        if not app.selected_levels: return
        qc = int(self.ids.quiz_count.text) if self.ids.quiz_count.text else 10
        pool = []
        for lv in app.selected_levels:
            for w in WORD_POOL.get(lv, []):
                wc = dict(w); wc['_level'] = lv; pool.append(wc)
        if len(pool) < qc:
            app.show_dialog(f'所选级别共 {len(pool)} 词，不足 {qc} 题')
            return
        progress_clear()
        app.wrong_bank_mode = False
        app.current_pool = pool
        app.quiz_count = qc
        app.draw_quiz()
        app.switch_screen('quiz')


class QuizScreen(MDScreen):
    def on_enter(self):
        self._render()

    def _render(self):
        app = MDApp.get_running_app()
        idx = app.current_idx
        if idx >= len(app.quiz_words):
            return
        word = app.quiz_words[idx]
        q = app.quiz_questions[idx]
        app.answered = False

        # Header
        self.ids.q_counter.text = f'第 {idx+1} / {app.quiz_count} 题'
        self.ids.q_type.text = f'[{q["label"]}]'
        self.ids.q_score.text = f'✓ {app.correct_count}  ✗ {app.incorrect_count}'
        self.ids.q_remaining.text = f'剩余 {app.current_pool.__len__()} 词'
        self.ids.progress_bar.value = idx / app.quiz_count * 100

        # Reset dynamic areas
        self.ids.word_area.opacity = 0
        self.ids.def_area.opacity = 0
        self.ids.pos_label.opacity = 0
        self.ids.input_area.opacity = 0
        self.ids.feedback_area.opacity = 0
        self.ids.btn_submit.opacity = 0
        self.ids.btn_next.opacity = 0
        self.ids.btn_pronounce.opacity = 0
        self.ids.input2_group.opacity = 0
        self.ids.ans_input1.text = ''
        self.ids.ans_input2.text = ''
        self.ids.ans_input1.disabled = False
        self.ids.ans_input2.disabled = False

        if q['type'] == 'jp2cn':
            self.ids.word_area.opacity = 1
            self.ids.q_furigana.text = word.get('furigana', '')
            self.ids.q_kanji.text = word.get('kanji', '') or '（无汉字）'
            pos = ' · '.join(filter(None, [word.get('pos', ''), word.get('pitch', '')]))
            if pos:
                self.ids.pos_label.text = pos
                self.ids.pos_label.opacity = 1
            self.ids.prompt1.text = '请输入中文释义：'
            self.ids.btn_pronounce.opacity = 1
        else:
            self.ids.def_area.opacity = 1
            self.ids.q_def.text = word.get('def_sc', '')
            self.ids.prompt1.text = '请输入日语汉字：'
            self.ids.prompt2.text = '请输入读音（振假名）：'
            self.ids.input2_group.opacity = 1

        self.ids.input_area.opacity = 1
        self.ids.btn_submit.opacity = 1
        Clock.schedule_once(lambda dt: self.ids.ans_input1.focus, 0.3)

    def submit(self):
        app = MDApp.get_running_app()
        if app.answered: return
        q = app.quiz_questions[app.current_idx]
        user1 = self.ids.ans_input1.text
        user2 = self.ids.ans_input2.text
        correct = q['check'](user1, user2)
        app.answered = True
        word = app.quiz_words[app.current_idx]

        srs_review(word, correct)

        if correct:
            app.correct_count += 1
            if app.wrong_bank_mode and word.get('_level'):
                wb_remove(word['_level'], word)
        else:
            app.incorrect_count += 1
            if word.get('_level'):
                wb_add(word['_level'], word)

        app.score_log[app.current_idx] = correct
        self.ids.q_score.text = f'✓ {app.correct_count}  ✗ {app.incorrect_count}'
        self.ids.ans_input1.disabled = True
        self.ids.ans_input2.disabled = True
        self.ids.btn_submit.opacity = 0

        # Feedback
        card = srs_get_or_create(word)
        self.ids.fb_icon.text = '✅' if correct else '❌'
        self.ids.fb_answer.text = f'正确答案：{q["answer"]}'
        self.ids.fb_srs.text = (f'SRS 难度 {card["ease_factor"]}  '
                                f'连续答对 {card["repetitions"]} 次  '
                                f'下次复习 {card["next_review"] or "—"}')
        plus = (word.get('plus', '') or '').strip()
        self.ids.fb_plus.text = f'📌 {plus}' if plus else ''
        self.ids.fb_plus.opacity = 1 if plus else 0

        # Sentences
        self.ids.sent_box.clear_widgets()
        for s in (word.get('sentences', []) or [])[:4]:
            txt = (s.get('furigana', '') or s.get('kanji', '') or '').replace('<b>','').replace('</b>','')
            d = s.get('def_sc', '')
            lbl = MDLabel(text=f'{txt}\n→ {d}' if d else txt,
                         font_size=sp(14), theme_text_color='Secondary',
                         size_hint_y=None, height=dp(40))
            self.ids.sent_box.add_widget(lbl)

        self.ids.feedback_area.opacity = 1

        if app.current_idx + 1 < app.quiz_count:
            Clock.schedule_once(lambda dt: self._show_next(), 0.2)
        else:
            Clock.schedule_once(lambda dt: app.show_result(), 0.6)

    def _show_next(self):
        self.ids.btn_next.opacity = 1

    def next(self):
        MDApp.get_running_app().current_idx += 1
        self._render()


class ResultScreen(MDScreen):
    def on_enter(self):
        app = MDApp.get_running_app()
        total = len(app.quiz_words)
        pct = round(app.correct_count / total * 100) if total else 0

        if not app.wrong_bank_mode:
            stats_record(app.selected_levels, total, app.correct_count, app.incorrect_count)

        self.ids.result_title.text = '错题复习结果' if app.wrong_bank_mode else '练习结果'
        self.ids.result_pct.text = f'{pct}%'

        o = stats_overall()
        learned = srs_learned_count(app.selected_levels)
        self.ids.result_detail.text = (
            f'{total} 题 · 正确 {app.correct_count} · 错误 {app.incorrect_count}\n'
            f'剩余 {len(app.current_pool)} 词 · 累计正确率 {o["accuracy"]}% · '
            f'连续 {o["streak"]} 天 · 已掌握 {learned} 词')

        self.ids.result_list.clear_widgets()
        for i, word in enumerate(app.quiz_words):
            ok = app.score_log[i]
            q = app.quiz_questions[i]
            icon = '✅' if ok is True else '❌' if ok is False else '⏭️'
            row = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40),
                              padding=[dp(8), 0, dp(8), 0], spacing=dp(4))
            defs = word.get('def_sc', '')
            row.add_widget(MDLabel(text=f'{icon}', font_size=sp(14), size_hint_x=.08))
            row.add_widget(MDLabel(text=f'[{q["label"]}]', font_size=sp(11),
                          theme_text_color='Primary', size_hint_x=.15))
            row.add_widget(MDLabel(text=word.get('kanji', '') or '', font_size=sp(14),
                          bold=True, size_hint_x=.2))
            row.add_widget(MDLabel(text=word.get('furigana', '') or '', font_size=sp(12),
                          theme_text_color='Primary', size_hint_x=.25))
            row.add_widget(MDLabel(text=defs, font_size=sp(12),
                          theme_text_color='Secondary', size_hint_x=.32))
            self.ids.result_list.add_widget(row)


class WrongBankScreen(MDScreen):
    def on_enter(self):
        self._show_overview()

    def _show_overview(self):
        app = MDApp.get_running_app()
        bank = wb_all()
        total = wb_total()
        container = self.ids.wb_container
        container.clear_widgets()

        if not total:
            container.add_widget(MDLabel(text='暂无错题 🎉', halign='center',
                                        font_size=sp(16), theme_text_color='Secondary'))
            self.ids.wb_actions.opacity = 0
            return

        self.ids.wb_actions.opacity = 1
        lbl = MDLabel(text='选择要复习的级别（可多选）：', font_size=sp(14),
                      theme_text_color='Secondary', size_hint_y=None, height=dp(30))
        container.add_widget(lbl)

        app.wb_checks = {}
        for lv in LEVELS:
            items = bank.get(lv, [])
            if not items: continue
            box = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(44),
                              padding=[dp(8), 0, dp(8), 0])
            cb = MDCheckbox(size_hint=(None, None), size=(dp(44), dp(44)), active=True)
            app.wb_checks[lv] = cb
            lbl = MDLabel(text=f'{LEVEL_LABELS[lv]}（{len(items)} 个错词）',
                         font_size=sp(15), theme_text_color='Secondary')
            view_btn = MDFlatButton(text='查看→', on_release=lambda x, l=lv: self._show_detail(l))
            box.add_widget(cb); box.add_widget(lbl); box.add_widget(view_btn)
            container.add_widget(box)

        container.add_widget(MDLabel(text=f'共 {total} 个错词', font_size=sp(14),
                                    theme_text_color='Primary', halign='center'))

    def _show_detail(self, level):
        bank = wb_all()
        container = self.ids.wb_container
        container.clear_widgets()
        self.ids.wb_actions.opacity = 0

        back_btn = MDFlatButton(text='← 返回', on_release=lambda x: self._show_overview())
        container.add_widget(back_btn)
        container.add_widget(MDLabel(text=LEVEL_LABELS[level], font_size=sp(18), bold=True))

        items = sorted(bank.get(level, []), key=lambda x: x.get('wrong_count', 0), reverse=True)
        for item in items:
            wc = item.get('wrong_count', 1)
            row = MDBoxLayout(orientation='horizontal', size_hint_y=None, height=dp(36))
            row.add_widget(MDLabel(text=f'×{wc}', font_size=sp(14), bold=True,
                                  theme_text_color='Error', size_hint_x=.1))
            row.add_widget(MDLabel(text=item.get('kanji', '（无汉字）'), font_size=sp(14),
                                  bold=True, size_hint_x=.25))
            row.add_widget(MDLabel(text=item.get('furigana', ''), font_size=sp(12),
                                  theme_text_color='Primary', size_hint_x=.3))
            row.add_widget(MDLabel(text=item.get('def_sc', ''), font_size=sp(12),
                                  theme_text_color='Secondary'))
            container.add_widget(row)

        review_btn = MDRaisedButton(text='复习此级别',
                                    on_release=lambda x: self._start_review([level]))
        container.add_widget(review_btn)

    def review_selected(self):
        app = MDApp.get_running_app()
        if not hasattr(app, 'wb_checks'): return
        levels = [lv for lv, cb in app.wb_checks.items() if cb.active]
        if not levels:
            MDApp.get_running_app().show_dialog('请至少勾选一个级别')
            return
        self._start_review(levels)

    def _start_review(self, levels):
        app = MDApp.get_running_app()
        bank = wb_all()
        pool = []
        for lv in levels:
            for entry in bank.get(lv, []):
                w = dict(entry); w['_level'] = lv; w.pop('wrong_count', None)
                pool.append(w)
        if not pool:
            app.show_dialog('错题本为空，无需复习！')
            return
        app.wrong_bank_mode = True
        app.current_pool = pool
        app.draw_quiz()
        app.switch_screen('quiz')

    def clear_confirm(self):
        MDApp.get_running_app().show_dialog('确定要清空所有错题记录吗？', on_ok=self._do_clear)

    def _do_clear(self, *args):
        wb_clear()
        self._show_overview()


# ═══════════════════════════════════════════════
#  App
# ═══════════════════════════════════════════════

class JlptQuizApp(MDApp):
    selected_levels = []
    quiz_words = []
    quiz_questions = []
    current_idx = 0
    quiz_count = 10
    correct_count = 0
    incorrect_count = 0
    score_log = []
    current_pool = []
    wrong_bank_mode = False
    answered = False

    def build(self):
        self.theme_cls.primary_palette = 'Brown'
        self.theme_cls.theme_style = 'Light'
        self.title = '日文背词 — JLPT 10k'

        screen_manager = MDScreenManager()
        screen_manager.add_widget(SetupScreen(name='setup'))
        screen_manager.add_widget(QuizScreen(name='quiz'))
        screen_manager.add_widget(ResultScreen(name='result'))
        screen_manager.add_widget(WrongBankScreen(name='wrong'))
        self.sm = screen_manager

        return screen_manager

    def on_start(self):
        load_word_data()
        init_storage()
        self.check_progress()
        self.switch_screen('setup')

    def switch_screen(self, name):
        self.sm.current = name
        if hasattr(self.sm.current_screen, 'on_enter'):
            self.sm.current_screen.on_enter()

    def check_progress(self):
        prog = progress_load()
        if prog and prog.get('remaining'):
            Clock.schedule_once(lambda dt: self._show_progress_dialog(prog), 0.5)

    def _show_progress_dialog(self, prog):
        remaining = prog.get('remaining', [])
        levels = prog.get('levels', [])
        if not remaining: return
        label = '、'.join(LEVEL_LABELS.get(lv, lv) for lv in levels)
        self.dialog = MDDialog(
            title='检测到上次进度',
            text=f'级别：{label}\n剩余 {len(remaining)} 词未学',
            buttons=[
                MDFlatButton(text='重新开始', on_release=lambda x: self._clear_progress()),
                MDRaisedButton(text='继续学习', on_release=lambda x: self._resume_progress(levels, remaining)),
            ],
        )
        self.dialog.open()

    def _resume_progress(self, levels, remaining, *args):
        self.selected_levels = list(levels)
        self.wrong_bank_mode = False
        self.current_pool = remaining
        self.draw_quiz()
        self.switch_screen('quiz')
        if hasattr(self, 'dialog'): self.dialog.dismiss()

    def _clear_progress(self, *args):
        progress_clear()
        if hasattr(self, 'dialog'): self.dialog.dismiss()
        self.switch_screen('setup')

    def draw_quiz(self):
        pool = self.current_pool
        if not pool:
            self.show_dialog('当前词库已全部学完！')
            self.go_home()
            return
        qc = self.quiz_count

        random.shuffle(pool)
        pool.sort(key=lambda w: 0 if srs_is_due(w) else 1)

        take = min(qc, len(pool))
        self.quiz_words = pool[:take]
        self.current_pool = pool[take:]

        half_jp = take // 2
        half_cn = take - half_jp
        types = ['jp2cn'] * half_jp + ['cn2jp'] * half_cn
        random.shuffle(types)

        self.quiz_questions = [build_question(w, t) for w, t in zip(self.quiz_words, types)]
        self.score_log = [None] * take
        self.current_idx = 0
        self.correct_count = 0
        self.incorrect_count = 0
        self.answered = False

    def show_result(self):
        self.switch_screen('result')

    def next_round(self):
        for i, word in enumerate(self.quiz_words):
            if self.score_log[i] is False:
                self.current_pool.append(word)
        if not self.wrong_bank_mode:
            progress_save(self.selected_levels, self.current_pool)
        self.draw_quiz()
        self.switch_screen('quiz')

    def go_home(self):
        if self.wrong_bank_mode:
            self.wrong_bank_mode = False
            self.switch_screen('wrong')
        else:
            if self.current_pool:
                progress_save(self.selected_levels, self.current_pool)
            else:
                progress_clear()
            self.switch_screen('setup')

    def play_sound(self):
        """朗读当前单词（Android TTS）"""
        if not hasattr(self, 'quiz_words') or not self.quiz_words:
            return
        word = self.quiz_words[self.current_idx]
        text = word.get('furigana', '') or word.get('kanji', '') or ''
        if not text:
            return
        try:
            from plyer import tts
            tts.speak(text)
        except Exception:
            pass  # 非 Android 或 plyer 不可用时静默降级

    def show_dialog(self, text, on_ok=None):
        buttons = [MDFlatButton(text='确定', on_release=lambda x: self._close_dialog())]
        if on_ok:
            buttons.insert(0, MDFlatButton(text='取消'))
            buttons.append(MDRaisedButton(text='确定', on_release=lambda x: on_ok()))
        self.dialog = MDDialog(text=text, buttons=buttons)
        self.dialog.open()

    def _close_dialog(self, *args):
        if hasattr(self, 'dialog'): self.dialog.dismiss()


if __name__ == '__main__':
    JlptQuizApp().run()
