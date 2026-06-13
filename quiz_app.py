"""
日文背词 — JLPT 10k 填空练习
用法: python quiz_app.py
"""

import json, os, random, sys
from pathlib import Path
from tkinter import Tk, Frame, Label, Button, Checkbutton, BooleanVar, StringVar, Spinbox
from tkinter import ttk, messagebox
from quiz import srs, stats as qstats, pronounce

# ── 数据路径 ──────────────────────────────────
DATA_DIR = Path(__file__).parent / 'quiz' / 'data'
LEVELS = ['N5', 'N4', 'N3', 'N2', 'N1']
LEVEL_LABELS = {
    'N5': 'N5（入门）', 'N4': 'N4（基础）',
    'N3': 'N3（中级）', 'N2': 'N2（中上级）', 'N1': 'N1（上级）',
}
QUIZ_COUNT = 10

# ── 进度保存 ──────────────────────────────────
PROGRESS_FILE = Path(__file__).parent / 'quiz' / '_progress.json'

def save_progress(levels, pool):
    """保存当前进度（剩余词库）"""
    data = {'levels': levels, 'remaining': pool}
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_progress():
    """读取进度，无进度时返回 None"""
    if not PROGRESS_FILE.exists():
        return None
    with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def clear_progress():
    """清除进度文件"""
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

# ── 错题库 ────────────────────────────────────
WRONG_BANK_FILE = Path(__file__).parent / 'quiz' / '_wrong_bank.json'

def load_wrong_bank():
    if not WRONG_BANK_FILE.exists():
        return {}
    with open(WRONG_BANK_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_wrong_bank(data):
    with open(WRONG_BANK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_wrong_word(level, word):
    """将答错的词加入错题库/增加错误次数"""
    bank = load_wrong_bank()
    if level not in bank:
        bank[level] = []
    # 用 kanji|furigana 作为唯一标识
    key = (word.get('kanji', '') or '', word.get('furigana', '') or '')
    for entry in bank[level]:
        ek = (entry.get('kanji', '') or '', entry.get('furigana', '') or '')
        if ek == key:
            entry['wrong_count'] = entry.get('wrong_count', 0) + 1
            save_wrong_bank(bank)
            return
    # 新错词
    entry = dict(word)
    entry.pop('_level', None)
    entry['wrong_count'] = 1
    bank[level].append(entry)
    save_wrong_bank(bank)

def remove_wrong_word(level, word):
    """答对后从错题库移除"""
    bank = load_wrong_bank()
    if level not in bank:
        return
    key = (word.get('kanji', '') or '', word.get('furigana', '') or '')
    bank[level] = [e for e in bank[level]
                   if (e.get('kanji', '') or '', e.get('furigana', '') or '') != key]
    if not bank[level]:
        del bank[level]
    save_wrong_bank(bank)

def get_total_wrong_count():
    return sum(len(items) for items in load_wrong_bank().values())

# ── 题型 ──────────────────────────────────────
TYPE_JP2CN = 'jp2cn'
TYPE_CN2JP = 'cn2jp'


# ── 数据加载 ──────────────────────────────────
def load_all_words():
    pool = {}
    for lv in LEVELS:
        path = DATA_DIR / f'{lv}.json'
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pool[lv] = data['words']
    return pool


WORD_POOL = load_all_words()


# ── 答案匹配 ──────────────────────────────────
def normalize(s: str) -> str:
    s = s.strip().replace(' ', '').replace('　', '')
    result = []
    for ch in s:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        else:
            result.append(ch)
    return ''.join(result).lower()


def match_furigana(user_input: str, correct: str) -> bool:
    if not user_input.strip():
        return False
    a, b = normalize(user_input), normalize(correct)
    if a == b:
        return True
    if b.startswith(a) and len(a) >= 2:
        return True
    if a.startswith(b) and len(b) >= 2:
        return True
    return False


def match_meaning(user_input: str, correct: str) -> bool:
    """释义匹配：仅用简体中文"""
    if not user_input.strip() or not correct:
        return False
    a, b = normalize(user_input), normalize(correct)
    if a == b:
        return True
    if len(a) >= 2 and b.find(a) != -1:
        return True
    if len(b) >= 2 and a.find(b) != -1:
        return True
    return False


def match_kanji(user_input: str, correct: str) -> bool:
    if not user_input.strip():
        return False
    return normalize(user_input) == normalize(correct)


def build_question(word: dict, qtype: str) -> dict:
    """构建一道题目，释义只用简体中文"""
    kanji = word.get('kanji', '')
    furi  = word.get('furigana', '')
    sc    = word.get('def_sc', '')

    if qtype == TYPE_JP2CN:
        return {
            'type': TYPE_JP2CN,
            'label': '日译中',
            'answer': sc,
            'check': lambda u, _k: match_meaning(u, sc),
        }
    else:
        return {
            'type': TYPE_CN2JP,
            'label': '中译日',
            'answer': f'{kanji}（{furi}）',
            'check': lambda u, k: match_kanji(k, kanji) and match_furigana(u, furi),
        }


# ── 主应用 ────────────────────────────────────
class QuizApp:
    def __init__(self):
        self.root = Tk()
        self.root.title('日文背词 — JLPT 10k')
        self.root.geometry('600x680')
        self.root.minsize(540, 600)

        # 字体模度比例：10 → 11 → 13 → 15 → 20（×1.273）
        if sys.platform == 'win32':
            self.f_kanji     = ('楷体', 20, 'bold')
            self.f_furi      = ('楷体', 13)
            self.f_body      = ('楷体', 11)
            self.f_input     = ('楷体', 15)
            self.f_prompt    = ('楷体', 10)
            self.f_answer    = ('楷体', 15)
            self.f_sentence  = ('楷体', 13)
        else:
            self.f_kanji     = ('Noto Serif CJK SC', 20, 'bold')
            self.f_furi      = ('Noto Serif CJK SC', 13)
            self.f_body      = ('Georgia', 11)
            self.f_input     = ('Noto Serif CJK SC', 15)
            self.f_prompt    = ('Georgia', 10)
            self.f_answer    = ('Georgia', 15)
            self.f_sentence  = ('Georgia', 13)

        # 状态
        self.selected_levels = {lv: BooleanVar(value=False) for lv in LEVELS}
        self.quiz_words = []
        self.quiz_questions = []
        self.current_idx = 0
        self.quiz_count = QUIZ_COUNT
        self.quiz_count_var = StringVar(value=str(QUIZ_COUNT))
        self.correct_count = 0
        self.incorrect_count = 0
        self.score_log = []
        self.current_pool = []      # session 级词库（正确剔除，错误回池）
        self.wrong_bank_mode = False  # 是否错题复习模式
        self.answered = False

        self._colors()
        self.container = Frame(self.root, bg=self.bg)
        self.container.pack(fill='both', expand=True)

        self._build_setup()
        self._build_quiz()
        self._build_result()
        self._build_progress_page()
        self._build_wrong_bank()

        self._show_screen('setup')
        self._update_level_info()
        self._build_nav(self.nav_setup, 'setup')

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ── 配色（暖色复古）────────────────────
    def _colors(self):
        self.bg        = '#f2ebe1'   # 米黄纸纹底
        self.card_bg   = '#faf6ef'   # 卡片暖白
        self.primary   = '#b87a4a'   # 暖褐
        self.correct_c = '#5a8a5a'   # 哑绿
        self.wrong_c   = '#b85c4a'   # 砖红
        self.text      = '#4a3728'   # 深褐
        self.text_sec  = '#8b7355'   # 中褐
        self.border    = '#d4c5a9'   # 暖米边框

    # ═══════════════════════════════════════
    #  界面 1：级别选择
    # ═══════════════════════════════════════
    def _build_setup(self):
        self.frame_setup = Frame(self.container, bg=self.bg)
        Label(self.frame_setup, text='日文背词', font=('楷体', 22, 'bold'),
              bg=self.bg, fg=self.text).pack(pady=(32, 2))
        Label(self.frame_setup, text='JLPT 10k · 填空练习', font=self.f_body,
               bg=self.bg, fg=self.text_sec).pack(pady=(0, 10))

        # ── SRS 复习概览 ──
        self.srs_summary = Label(self.frame_setup, text='', font=('楷体', 9),
                                 bg=self.bg, fg=self.primary)
        self.srs_summary.pack(pady=(0, 10))

        card = Frame(self.frame_setup, bg=self.card_bg,
                     highlightbackground=self.border, highlightthickness=1)
        card.pack(padx=32, fill='x')

        Label(card, text='选择背诵级别：', font=self.f_body,
              bg=self.card_bg, fg=self.text).pack(anchor='w', padx=20, pady=(16, 6))

        for lv in LEVELS:
            row = Frame(card, bg=self.card_bg)
            row.pack(fill='x', padx=20, pady=2)
            Checkbutton(row, text=LEVEL_LABELS[lv],
                        variable=self.selected_levels[lv],
                        font=self.f_body, bg=self.card_bg, fg=self.text,
                        selectcolor=self.card_bg, activebackground=self.card_bg,
                        command=self._update_level_info).pack(side='left')
            Label(row, text=f'（{len(WORD_POOL[lv])} 词）',
                  font=('楷体', 10), bg=self.card_bg,
                  fg=self.text_sec).pack(side='right')

        self.lbl_level_info = Label(card, text='', font=('楷体', 10),
                                    bg=self.card_bg, fg=self.text_sec)
        self.lbl_level_info.pack(anchor='w', padx=20, pady=(4, 2))

        # ── 每轮题数 ──
        row_count = Frame(card, bg=self.card_bg)
        row_count.pack(fill='x', padx=20, pady=(2, 6))
        Label(row_count, text='每轮题数：', font=self.f_body,
              bg=self.card_bg, fg=self.text).pack(side='left')
        Spinbox(row_count, from_=5, to=30, increment=5,
                textvariable=self.quiz_count_var,
                font=self.f_body, width=6, justify='center',
                bg=self.card_bg).pack(side='left', padx=(4, 0))

        self.btn_start = Button(card, text='开始答题', font=('楷体', 12, 'bold'),
                                bg=self.primary, fg='white', relief='flat',
                                padx=24, pady=8, border=0,
                                command=self._start_quiz)
        self.btn_start.pack(pady=(4, 10))
        self.btn_start.config(state='disabled')

        # ── 底部导航 ──
        self.nav_setup = Frame(self.frame_setup, bg=self.bg)
        self.nav_setup.pack(pady=(0, 18))
        self._build_nav(self.nav_setup, 'setup')

    def _build_nav(self, parent, active):
        """底部导航栏（setup / progress / wrong）"""
        for w in parent.winfo_children():
            w.destroy()
        # 选择题库
        btn1 = Button(parent, text='📖 选择题库', font=self.f_body,
                      bg=self.primary if active == 'setup' else self.card_bg,
                      fg='white' if active == 'setup' else self.primary,
                      relief='flat', border=0, padx=20, pady=6,
                      command=self._refresh_setup_view)
        btn1.pack(side='left', padx=4)
        # 继续学习（有存档时显示）
        prog = load_progress()
        if prog and prog.get('remaining'):
            rem = prog['remaining']
            lbl = f'📝 继续({len(rem)})'
            bg = self.primary if active == 'progress' else self.card_bg
            fg = 'white' if active == 'progress' else self.primary
            Button(parent, text=lbl, font=self.f_body,
                   bg=bg, fg=fg, relief='flat', border=0, padx=20, pady=6,
                   command=self._refresh_progress_view).pack(side='left', padx=4)
        # 错题本
        total = get_total_wrong_count()
        label2 = f'❌ 错题本({total})' if total else '❌ 错题本'
        btn2 = Button(parent, text=label2, font=self.f_body,
                      bg=self.primary if active == 'wrong' else self.card_bg,
                      fg='white' if active == 'wrong' else self.primary,
                      relief='flat', border=0, padx=20, pady=6,
                      command=self._show_wrong_bank)
        btn2.pack(side='left', padx=4)

    def _refresh_setup_view(self):
        """切换到选择题库页"""
        self.wrong_bank_mode = False
        self._show_screen('setup')
        self._update_level_info()
        self._build_nav(self.nav_setup, 'setup')

    def _refresh_progress_view(self):
        """刷新并显示继续学习页"""
        self.wrong_bank_mode = False
        prog = load_progress()
        if prog and prog.get('remaining'):
            levels = prog.get('levels', [])
            remaining = prog.get('remaining', [])
            label = '、'.join(LEVEL_LABELS.get(lv, lv) for lv in levels)
            self.lbl_prog_info.config(text=f'级别：{label}  ·  剩余 {len(remaining)} 词')
            self._show_screen('progress')
        else:
            self._show_screen('setup')
            self._update_level_info()
            self._build_nav(self.nav_setup, 'setup')

    def _update_level_info(self):
        selected = [lv for lv in LEVELS if self.selected_levels[lv].get()]
        total = sum(len(WORD_POOL[lv]) for lv in selected)
        if selected:
            ss = srs.get_review_stats(selected)
            due = ss['due']
            learned = ss['learned']
            self.lbl_level_info.config(
                text=f'已选 {len(selected)} 个级别，共 {total} 词   |   待复习 {due}  已掌握 {learned}'
            )
            self.srs_summary.config(
                text=f'总学习卡片 {ss["total"]}  今日到期 {due}  新词待学 {srs.get_new_count(selected, WORD_POOL)}'
            )
        else:
            self.lbl_level_info.config(text='请至少选择一个级别')
            self.srs_summary.config(text='')
        self.btn_start.config(state='normal' if selected else 'disabled')

    # ── 主页刷新 ──────────────────────────
    def _refresh_setup(self):
        self._update_level_info()

    def _resume_from_progress(self):
        """从进度继续学习"""
        prog = load_progress()
        if not prog:
            return
        self.wrong_bank_mode = False
        levels = prog.get('levels', [])
        remaining = prog.get('remaining', [])
        if not remaining:
            clear_progress()
            self._show_screen('setup')
            self._update_level_info()
            return
        for lv in LEVELS:
            self.selected_levels[lv].set(lv in levels)
        self._update_level_info()
        self.current_pool = remaining
        self._draw_quiz()

    def _clear_and_refresh(self):
        """清除进度并跳转到选择题库主页"""
        self.wrong_bank_mode = False
        clear_progress()
        self._show_screen('setup')
        self._update_level_info()
        self._build_nav(self.nav_setup, 'setup')

    # ═══════════════════════════════════════
    #  界面 1b：继续进度主页
    # ═══════════════════════════════════════
    def _build_progress_page(self):
        self.frame_progress = Frame(self.container, bg=self.bg)
        Label(self.frame_progress, text='日文背词', font=('楷体', 22, 'bold'),
              bg=self.bg, fg=self.text).pack(pady=(32, 2))
        Label(self.frame_progress, text='JLPT 10k · 填空练习', font=self.f_body,
              bg=self.bg, fg=self.text_sec).pack(pady=(0, 20))

        card = Frame(self.frame_progress, bg=self.card_bg,
                     highlightbackground=self.primary, highlightthickness=1)
        card.pack(padx=32, pady=20, fill='x')

        Label(card, text='📖 检测到上次进度', font=('楷体', 14, 'bold'),
              bg=self.card_bg, fg=self.primary).pack(pady=(18, 6))

        self.lbl_prog_info = Label(card, text='', font=self.f_body,
                                   bg=self.card_bg, fg=self.text_sec)
        self.lbl_prog_info.pack()

        btn_row = Frame(card, bg=self.card_bg)
        btn_row.pack(pady=(14, 18))
        Button(btn_row, text='继续学习', font=('楷体', 12, 'bold'),
               bg=self.primary, fg='white', relief='flat',
               padx=24, pady=8, border=0,
               command=self._resume_from_progress).pack(side='left', padx=6)
        Button(btn_row, text='重新开始', font=('楷体', 12),
               bg=self.card_bg, fg=self.primary,
               relief='solid', border=1,
               padx=24, pady=8,
                command=self._clear_and_refresh).pack(side='left', padx=6)

    # ═══════════════════════════════════════
    #  界面 1c：错题本
    # ═══════════════════════════════════════
    def _build_wrong_bank(self):
        self.frame_wrong_bank = Frame(self.container, bg=self.bg)
        Label(self.frame_wrong_bank, text='❌ 错题本', font=('楷体', 20, 'bold'),
              bg=self.bg, fg=self.text).pack(pady=(28, 2))
        Label(self.frame_wrong_bank, text='曾经答错的词，复习巩固', font=self.f_body,
              bg=self.bg, fg=self.text_sec).pack(pady=(0, 16))

        card = Frame(self.frame_wrong_bank, bg=self.card_bg,
                     highlightbackground=self.border, highlightthickness=1)
        card.pack(padx=32, fill='x')

        self.wb_inner = Frame(card, bg=self.card_bg)
        self.wb_inner.pack(fill='x', padx=20, pady=16)

        self.wb_btn_frame = Frame(self.frame_wrong_bank, bg=self.bg)
        self.wb_btn_frame.pack(pady=(14, 6))
        self.btn_wb_review = Button(self.wb_btn_frame, text='复习选中级别', font=('楷体', 12, 'bold'),
                                    bg=self.primary, fg='white', relief='flat',
                                    padx=24, pady=8, border=0,
                                    command=self._start_selected_review)
        self.btn_wb_review.pack(side='left', padx=4)
        Button(self.wb_btn_frame, text='清空错题本', font=self.f_body,
               bg=self.card_bg, fg=self.wrong_c,
               relief='solid', border=1,
               padx=20, pady=8,
               command=self._clear_wrong_bank).pack(side='left', padx=4)

        # 底部导航
        self.nav_wrong = Frame(self.frame_wrong_bank, bg=self.bg)
        self.nav_wrong.pack(side='bottom', pady=18)
        self._build_nav(self.nav_wrong, 'wrong')

    def _show_wrong_bank(self, level=None):
        """刷新并显示错题本页面
        level=None → 目录视图（按级别列出）
        level=lv   → 详情视图（该级别错词按错误次数降序）"""
        self.wrong_bank_mode = False
        for w in self.wb_inner.winfo_children():
            w.destroy()
        bank = load_wrong_bank()
        total = get_total_wrong_count()

        if not total:
            Label(self.wb_inner, text='暂无错题 🎉', font=self.f_body,
                  bg=self.card_bg, fg=self.text_sec).pack(pady=10)
            self.btn_wb_review.config(state='disabled')
            self._build_nav(self.nav_wrong, 'wrong')
            self._show_screen('wrong_bank')
            return

        self.btn_wb_review.config(state='normal')

        if level is None:
            # ── 目录视图 ──
            self.wb_btn_frame.pack(pady=(14, 6))
            Label(self.wb_inner, text='选择要复习的级别（可多选）：', font=('楷体', 11, 'bold'),
                  bg=self.card_bg, fg=self.text_sec).pack(anchor='w', pady=(0, 6))
            self.wb_level_vars = {}
            for lv in LEVELS:
                items = bank.get(lv, [])
                if not items:
                    continue
                row = Frame(self.wb_inner, bg=self.card_bg)
                row.pack(fill='x', pady=2)
                var = BooleanVar(value=True)
                self.wb_level_vars[lv] = var
                Checkbutton(row, variable=var, text='', bg=self.card_bg,
                            selectcolor=self.card_bg, activebackground=self.card_bg,
                            font=self.f_body).pack(side='left')
                Label(row, text=LEVEL_LABELS[lv], font=('楷体', 11, 'bold'),
                      bg=self.card_bg, fg=self.text, width=14, anchor='w').pack(side='left')
                Label(row, text=f'{len(items)} 个错词', font=self.f_body,
                      bg=self.card_bg, fg=self.text_sec).pack(side='left', padx=(0, 4))
                Button(row, text='查看 →', font=('楷体', 9),
                       bg=self.card_bg, fg=self.primary, relief='flat', border=0,
                       command=lambda l=lv: self._show_wrong_bank(l)).pack(side='right')
            Label(self.wb_inner, text=f'共 {total} 个错词', font=self.f_body,
                  bg=self.card_bg, fg=self.primary).pack(pady=(6, 0))
        else:
            # ── 详情视图 ──
            self.wb_btn_frame.pack_forget()
            hdr = Frame(self.wb_inner, bg=self.card_bg)
            hdr.pack(fill='x')
            Button(hdr, text='← 返回', font=self.f_body,
                   bg=self.card_bg, fg=self.primary, relief='flat', border=0,
                   command=lambda: self._show_wrong_bank()).pack(side='left')
            Label(hdr, text=LEVEL_LABELS[level], font=('楷体', 12, 'bold'),
                  bg=self.card_bg, fg=self.text).pack(side='left', padx=(10, 0))

            items = sorted(bank.get(level, []),
                           key=lambda x: x.get('wrong_count', 0), reverse=True)
            for item in items:
                wc = item.get('wrong_count', 0)
                kanji = item.get('kanji', '') or '（无汉字）'
                furi = item.get('furigana', '')
                defs = item.get('def_sc', '')
                row = Frame(self.wb_inner, bg=self.card_bg)
                row.pack(fill='x', pady=2)
                Label(row, text=f'×{wc}', font=('楷体', 11, 'bold'),
                      bg=self.card_bg, fg=self.wrong_c, width=4, anchor='w').pack(side='left')
                Label(row, text=kanji, font=('楷体', 11, 'bold'),
                      bg=self.card_bg, fg=self.text, width=12, anchor='w').pack(side='left')
                Label(row, text=furi, font=('楷体', 10),
                      bg=self.card_bg, fg=self.primary, width=16, anchor='w').pack(side='left')
                Label(row, text=defs, font=('楷体', 10),
                      bg=self.card_bg, fg=self.text_sec, anchor='w').pack(side='left', padx=(4, 0))

            Button(self.wb_inner, text='复习此级别', font=self.f_body,
                   bg=self.primary, fg='white', relief='flat',
                   padx=20, pady=6, border=0,
                   command=lambda l=level: self._start_wrong_review(l)).pack(pady=(10, 2))

        self._build_nav(self.nav_wrong, 'wrong')
        self._show_screen('wrong_bank')

    def _start_wrong_review(self, level=None):
        """进入错题复习模式，可选指定级别或级别列表"""
        bank = load_wrong_bank()
        pool = []
        if isinstance(level, list):
            review_levels = level
        elif level:
            review_levels = [level]
        else:
            review_levels = LEVELS
        for lv in review_levels:
            for entry in bank.get(lv, []):
                wc = dict(entry)
                wc['_level'] = lv
                wc.pop('wrong_count', None)
                pool.append(wc)
        if not pool:
            messagebox.showinfo('无错题', '错题本为空，无需复习！')
            return
        self.wrong_bank_mode = True
        self.current_pool = pool
        self._draw_quiz()

    def _start_selected_review(self):
        """复习勾选中的级别"""
        levels = [lv for lv, var in self.wb_level_vars.items() if var.get()]
        if not levels:
            messagebox.showinfo('未选择', '请至少勾选一个级别')
            return
        self._start_wrong_review(levels)

    def _clear_wrong_bank(self):
        """在页面内嵌入清空确认"""
        for w in self.wb_inner.winfo_children():
            w.destroy()
        self.wb_btn_frame.pack_forget()

        confirm = Frame(self.wb_inner, bg=self.card_bg)
        confirm.pack(fill='x', pady=20)
        Label(confirm, text='确定要清空所有错题记录吗？', font=('楷体', 13, 'bold'),
              bg=self.card_bg, fg=self.text).pack(pady=(0, 14))
        row = Frame(confirm, bg=self.card_bg)
        row.pack()
        Button(row, text='确认清空', font=('楷体', 12, 'bold'),
               bg=self.wrong_c, fg='white', relief='flat',
               padx=24, pady=8, border=0,
               command=self._do_clear).pack(side='left', padx=6)
        Button(row, text='取消', font=self.f_body,
               bg=self.card_bg, fg=self.text, relief='solid', border=1,
               padx=24, pady=8,
               command=lambda: self._show_wrong_bank()).pack(side='left', padx=6)

    def _do_clear(self):
        """实际执行清空"""
        save_wrong_bank({})
        self._show_wrong_bank()

    # ═══════════════════════════════════════
    #  界面 2：答题（填空）
    # ═══════════════════════════════════════
    def _build_quiz(self):
        self.frame_quiz = Frame(self.container, bg=self.bg)

        # 进度条
        self.progress = ttk.Progressbar(self.frame_quiz, value=0, maximum=QUIZ_COUNT)
        self.progress.pack(fill='x', padx=32, pady=(20, 4))

        # 顶部信息
        hdr = Frame(self.frame_quiz, bg=self.bg)
        hdr.pack(fill='x', padx=36, pady=(4, 0))
        self.lbl_counter = Label(hdr, text='', font=self.f_body,
                                 bg=self.bg, fg=self.text_sec)
        self.lbl_counter.pack(side='left')
        self.lbl_qtype = Label(hdr, text='', font=('楷体', 10, 'bold'),
                               bg=self.bg, fg=self.primary)
        self.lbl_qtype.pack(side='left', padx=(10, 0))
        self.lbl_score = Label(hdr, text='', font=self.f_body,
                               bg=self.bg, fg=self.text_sec)
        self.lbl_score.pack(side='right')
        self.lbl_remaining = Label(hdr, text='', font=self.f_body,
                                   bg=self.bg, fg=self.primary)
        self.lbl_remaining.pack(side='right', padx=(0, 8))

        # 卡片
        card = Frame(self.frame_quiz, bg=self.card_bg,
                     highlightbackground=self.border, highlightthickness=1)
        card.pack(padx=32, pady=10, fill='both', expand=True)

        # ── 单词展示区（日译中用） ──
        self.word_frame = Frame(card, bg=self.card_bg)
        self.word_frame.pack(pady=(20, 2))

        self.lbl_furigana_top = Label(self.word_frame, text='', font=self.f_furi,
                                      bg=self.card_bg, fg=self.primary)
        self.lbl_furigana_top.grid(row=0, column=0)
        self.lbl_furigana_top.grid_remove()

        self.lbl_kanji = Label(self.word_frame, text='', font=self.f_kanji,
                               bg=self.card_bg, fg=self.text)
        self.lbl_kanji.grid(row=1, column=0)

        # ── 释义展示区（中译日用） ──
        self.def_frame = Frame(card, bg=self.card_bg)
        self.lbl_def_show = Label(self.def_frame, text='', font=self.f_kanji,
                                  bg=self.card_bg, fg=self.text, wraplength=480)
        self.lbl_def_show.pack(pady=(20, 4))
        self.def_frame.pack_forget()

        # 词性
        self.lbl_pos = Label(card, text='', font=('楷体', 10),
                             bg=self.card_bg, fg=self.text_sec)
        self.lbl_pos.pack(pady=(0, 6))

        # ── 发音按钮 ──
        self.btn_pronounce = Button(self.word_frame, text='🔊', font=('楷体', 11),
                                    bg=self.card_bg, fg=self.primary,
                                    relief='flat', border=0, padx=6, pady=2,
                                    command=self._play_pronunciation)
        self.btn_pronounce.grid(row=1, column=1, padx=(8, 0))

        # ── 输入区域 ──
        self.input_area = Frame(card, bg=self.card_bg)

        self.lbl_prompt1 = Label(self.input_area, text='', font=self.f_prompt,
                                 bg=self.card_bg, fg=self.text)
        self.lbl_prompt1.pack(anchor='w', pady=(0, 1))

        self.entry_var1 = StringVar()
        self.entry_input1 = ttk.Entry(self.input_area, textvariable=self.entry_var1,
                                      font=self.f_input, justify='center')
        self.entry_input1.pack(fill='x', pady=(0, 6))
        self.entry_input1.bind('<Return>', lambda e: self._submit_answer())

        self.lbl_prompt2 = Label(self.input_area, text='', font=self.f_prompt,
                                 bg=self.card_bg, fg=self.text)
        self.entry_var2 = StringVar()
        self.entry_input2 = ttk.Entry(self.input_area, textvariable=self.entry_var2,
                                      font=self.f_input, justify='center')

        # 提交
        self.btn_submit = Button(card, text='提交', font=self.f_body,
                                 bg=self.primary, fg='white', relief='flat',
                                 padx=24, pady=6, border=0,
                                 command=self._submit_answer)

        # ── 反馈区域 ──
        self.frame_feedback = Frame(card, bg=self.card_bg)

        self.lbl_result_icon = Label(self.frame_feedback, text='',
                                     font=('楷体', 20), bg=self.card_bg)
        self.lbl_result_icon.pack(pady=(2, 0))

        self.lbl_result_answer = Label(self.frame_feedback, text='',
                                       font=self.f_answer, bg=self.card_bg,
                                       fg=self.text, wraplength=480)
        self.lbl_result_answer.pack(pady=(0, 2))

        self.lbl_srs_status = Label(self.frame_feedback, text='', font=('楷体', 9),
                                    bg=self.card_bg, fg=self.text_sec)
        self.lbl_srs_status.pack(pady=(0, 2))

        self.lbl_plus = Label(self.frame_feedback, text='', font=('楷体', 10),
                              bg=self.card_bg, fg='#8e8e93', wraplength=480,
                              justify='left')
        self.lbl_plus.pack(pady=(0, 1))

        self.lbl_sent_title = Label(self.frame_feedback, text='例句：',
                                    font=('楷体', 11, 'bold'),
                                    bg=self.card_bg, fg=self.text, anchor='w')
        self.lbl_sent_title.pack(fill='x', pady=(2, 0))

        self.sent_frames = []
        for i in range(4):
            sf = Frame(self.frame_feedback, bg=self.card_bg)
            lbl_s = Label(sf, text='', font=self.f_sentence,
                          bg=self.card_bg, fg=self.text, wraplength=480,
                          justify='left', anchor='w')
            lbl_s.pack(fill='x')
            lbl_d = Label(sf, text='', font=self.f_sentence,
                          bg=self.card_bg, fg=self.text, wraplength=480,
                          justify='left', anchor='w')
            lbl_d.pack(fill='x')
            sf.pack_forget()
            self.sent_frames.append({'frame': sf, 'lbl_s': lbl_s, 'lbl_d': lbl_d})

        self.frame_feedback.pack_forget()

        # 下一题
        self.btn_next = Button(card, text='下一题 →', font=self.f_body,
                               bg=self.card_bg, fg=self.primary,
                               activebackground='#e8f2ff', relief='solid',
                               border=1, padx=28, pady=6,
                               command=self._next_question)
        self.btn_next.pack_forget()

    # ── 开始答题 ──────────────────────────
    def _start_quiz(self):
        selected = [lv for lv in LEVELS if self.selected_levels[lv].get()]
        qc = int(self.quiz_count_var.get())
        pool = []
        for lv in selected:
            for w in WORD_POOL[lv]:
                wc = dict(w)
                wc['_level'] = lv
                pool.append(wc)

        if len(pool) < qc:
            messagebox.showwarning('词数不足', f'所选级别共 {len(pool)} 词，不足 {qc} 题。')
            return

        clear_progress()
        self.wrong_bank_mode = False
        self.current_pool = pool
        self._draw_quiz()

    def _draw_quiz(self):
        """从 current_pool 抽取一组题目，SRS 优先取到期词"""
        if not self.current_pool:
            messagebox.showinfo('学习完成', '当前词库已全部学完！')
            self._go_home()
            return

        qc = int(self.quiz_count_var.get())
        random.shuffle(self.current_pool)
        # SRS 到期词排在前面
        self.current_pool.sort(key=lambda w: 0 if srs.is_due(w) else 1)

        take = min(qc, len(self.current_pool))
        self.quiz_words = self.current_pool[:take]
        self.current_pool = self.current_pool[take:]

        # 保持 1:1 题型比例
        half_jp = take // 2
        half_cn = take - half_jp
        types = [TYPE_JP2CN] * half_jp + [TYPE_CN2JP] * half_cn
        random.shuffle(types)

        self.quiz_questions = [build_question(w, t) for w, t in zip(self.quiz_words, types)]
        self.score_log = [None] * take
        self.current_idx = 0
        self.quiz_count = take
        self.correct_count = 0
        self.incorrect_count = 0
        self.answered = False

        self.progress.config(maximum=take)

        self._show_screen('quiz')
        self._render_question()

    # ── 渲染题目 ──────────────────────────
    def _play_pronunciation(self):
        word = self.quiz_words[self.current_idx]
        text = word.get('furigana', '') or word.get('kanji', '') or ''
        pronounce.speak(text)

    def _render_question(self):
        idx = self.current_idx
        word = self.quiz_words[idx]
        q = self.quiz_questions[idx]
        self.answered = False

        self.progress['value'] = idx
        self.lbl_counter.config(text=f'第 {idx+1} / {self.quiz_count} 题')
        self.lbl_qtype.config(text=f'[{q["label"]}]')
        self.lbl_score.config(text=f'✓ {self.correct_count}   ✗ {self.incorrect_count}')
        self.lbl_remaining.config(text=f'词库剩余 {len(self.current_pool)} 词')

        # 先收拢所有动态元素
        self.def_frame.pack_forget()
        self.word_frame.pack_forget()
        self.lbl_pos.pack_forget()
        self.lbl_furigana_top.grid_remove()
        self.btn_pronounce.grid_remove()
        self.input_area.pack_forget()
        self.lbl_prompt2.pack_forget()
        self.entry_input2.pack_forget()
        self.frame_feedback.pack_forget()
        self.lbl_plus.pack_forget()
        self.lbl_sent_title.pack_forget()
        self.lbl_srs_status.pack_forget()
        for sf in self.sent_frames:
            sf['frame'].pack_forget()
        self.btn_submit.pack_forget()
        self.btn_next.pack_forget()

        if q['type'] == TYPE_JP2CN:
            # ── 日译中：显示汉字+注音 ──
            self.word_frame.pack(pady=(16, 0))
            furi = word.get('furigana', '')
            if furi:
                self.lbl_furigana_top.config(text=furi)
                self.lbl_furigana_top.grid()
            self.lbl_kanji.config(text=word['kanji'] or '（无汉字）')
            pos = ' · '.join(filter(None, [word.get('pos', ''), word.get('pitch', '')]))
            self.lbl_pos.config(text=pos)
            self.lbl_pos.pack(pady=(0, 4))
            self.lbl_prompt1.config(text='请输入中文释义：')
        else:
            # ── 中译日：显示释义 ──
            self.def_frame.pack(pady=(14, 4))
            self.lbl_def_show.config(text=word.get('def_sc', ''))
            self.lbl_prompt1.config(text='请输入日语汉字：')
            self.lbl_prompt2.pack(anchor='w', pady=(2, 1))
            self.lbl_prompt2.config(text='请输入读音（振假名）：')
            self.entry_input2.pack(fill='x', pady=(0, 4))
            self.entry_var2.set('')

        # 发音按钮
        if pronounce.is_available():
            self.btn_pronounce.grid(row=1, column=1, padx=(8, 0))

        # 输入区（紧接题目下方，entry_input1 初始化时已 pack，别再重复调用）
        self.input_area.pack(pady=(4, 4), fill='x', padx=24)
        self.entry_var1.set('')
        self.entry_input1.config(state='normal')
        self.entry_input2.config(state='normal')
        self.entry_input1.focus_set()

        self.btn_submit.pack(pady=(2, 10))

    # ── 提交答案 ──────────────────────────
    def _submit_answer(self):
        if self.answered:
            return
        q = self.quiz_questions[self.current_idx]
        user1 = self.entry_var1.get()
        user2 = self.entry_var2.get()
        correct = q['check'](user1, user2)
        self.answered = True

        word = self.quiz_words[self.current_idx]

        # SRS 记录（错题复习模式也记录，但不影响间隔重复）
        srs.review(word, correct)

        if correct:
            self.correct_count += 1
            icon, color = '✅', self.correct_c
            # 错题复习模式下答对 → 从错题库移除
            if getattr(self, 'wrong_bank_mode', False):
                lv = word.get('_level', '')
                if lv:
                    remove_wrong_word(lv, word)
        else:
            self.incorrect_count += 1
            icon, color = '❌', self.wrong_c
            # 记录错题（错题复习模式下也增加次数）
            lv = word.get('_level', '')
            if lv:
                add_wrong_word(lv, word)

        self.score_log[self.current_idx] = correct
        self.lbl_score.config(text=f'✓ {self.correct_count}   ✗ {self.incorrect_count}')

        # 禁用输入
        self.entry_input1.config(state='disabled')
        self.entry_input2.config(state='disabled')
        self.btn_submit.pack_forget()

        # 反馈：答案
        self.lbl_result_icon.config(text=icon, fg=color)
        self.lbl_result_answer.config(text=f'正确答案：{q["answer"]}')

        # 反馈：SRS 状态
        card = srs.get_or_create(word)
        ef = card.get('ease_factor', 2.5)
        reps = card.get('repetitions', 0)
        nr = card.get('next_review', '—')
        self.lbl_srs_status.config(
            text=f'SRS 难度 {ef}  连续答对 {reps} 次  下次复习 {nr}'
        )
        self.lbl_srs_status.pack(pady=(0, 2))

        # 反馈：VocabPlus
        plus = word.get('plus', '').strip()
        if plus:
            self.lbl_plus.config(text=f'📌 {plus}')
            self.lbl_plus.pack(pady=(0, 1))
        else:
            self.lbl_plus.pack_forget()

        # 反馈：例句
        sents = word.get('sentences', [])
        if sents:
            self.lbl_sent_title.pack(fill='x', pady=(2, 0))
            for i, sf in enumerate(self.sent_frames):
                if i < len(sents):
                    s = sents[i]
                    txt = s.get('furigana', '') or s.get('kanji', '')
                    txt = txt.replace('<b>', '').replace('</b>', '')
                    sf['lbl_s'].config(text=txt)
                    d = s.get('def_sc', '')
                    sf['lbl_d'].config(text=f'→ {d}' if d else '')
                    sf['frame'].pack(fill='x', pady=1)
                else:
                    sf['frame'].pack_forget()
        else:
            self.lbl_sent_title.pack_forget()
            for sf in self.sent_frames:
                sf['frame'].pack_forget()

        self.frame_feedback.pack(fill='x', padx=20, pady=(2, 6))

        if self.current_idx + 1 < self.quiz_count:
            self.root.after(200, lambda: self.btn_next.pack(pady=(0, 16)))
        else:
            self.root.after(600, self._show_result)

    # ── 下一题 ──────────────────────────
    def _next_question(self):
        self.current_idx += 1
        self._render_question()

    # ═══════════════════════════════════════
    #  界面 3：结果
    # ═══════════════════════════════════════
    def _build_result(self):
        self.frame_result = Frame(self.container, bg=self.bg)

        self.lbl_result_title = Label(self.frame_result, text='练习结果',
                                      font=('楷体', 20, 'bold'),
                                      bg=self.bg, fg=self.text)
        self.lbl_result_title.pack(pady=(28, 2))

        self.lbl_result_pct = Label(self.frame_result, text='', font=('楷体', 48, 'bold'),
                                    bg=self.bg, fg=self.primary)
        self.lbl_result_pct.pack(pady=(12, 0))

        self.lbl_result_detail = Label(self.frame_result, text='', font=self.f_body,
                                       bg=self.bg, fg=self.text_sec)
        self.lbl_result_detail.pack(pady=(2, 12))

        canvas_frame = Frame(self.frame_result, bg=self.bg)
        canvas_frame.pack(fill='both', expand=True, padx=32)

        canvas_outline = Frame(canvas_frame, bg=self.card_bg,
                               highlightbackground=self.border, highlightthickness=1)
        canvas_outline.pack(fill='both', expand=True)

        self.list_container = Frame(canvas_outline, bg=self.card_bg)
        self.list_container.pack(fill='both', expand=True, padx=14, pady=6)

        btn_frame = Frame(self.frame_result, bg=self.bg)
        btn_frame.pack(pady=(12, 24))

        self.btn_restart = Button(btn_frame, text='再来一组', font=self.f_body,
                                  bg=self.primary, fg='white', relief='flat',
                                  padx=20, pady=8, border=0,
                                  command=self._next_round)
        self.btn_restart.pack(side='left', padx=6)

        self.btn_back = Button(btn_frame, text='返回主页', font=self.f_body,
                               bg=self.card_bg, fg=self.primary,
                               relief='solid', border=1,
                               padx=20, pady=8,
                               command=self._go_home)
        self.btn_back.pack(side='left', padx=6)

    def _show_result(self):
        self._show_screen('result')
        total = len(self.quiz_words)
        pct = round(self.correct_count / total * 100) if total else 0
        if self.wrong_bank_mode:
            self.lbl_result_title.config(text='错题复习结果')
        else:
            self.lbl_result_title.config(text='练习结果')
            # 记录统计（仅在普通模式下，错题复习不稀释统计）
            selected = [lv for lv in LEVELS if self.selected_levels[lv].get()]
            qstats.record_session(selected, total, self.correct_count, self.incorrect_count)

        # 累计统计
        o = qstats.overall_stats()
        streak = o.get('streak', 0)
        total_learned = srs.get_learned_count([lv for lv in LEVELS if self.selected_levels[lv].get()])

        self.lbl_result_pct.config(text=f'{pct}%')
        self.lbl_result_detail.config(
            text=f'{total} 题  ·  正确 {self.correct_count}  ·  错误 {self.incorrect_count}'
            f'  ·  词库剩余 {len(self.current_pool)} 词'
            f'  ·  累计正确率 {o["accuracy"]}%'
            f'  ·  连续 {streak} 天'
            f'  ·  已掌握 {total_learned} 词'
        )

        for w in self.list_container.winfo_children():
            w.destroy()

        for i, word in enumerate(self.quiz_words):
            ok = self.score_log[i]
            q = self.quiz_questions[i]
            icon = '✅' if ok is True else '❌' if ok is False else '⏭️'
            defs = word.get('def_sc', '')

            row = Frame(self.list_container, bg=self.card_bg)
            row.pack(fill='x', pady=1)

            Label(row, text=icon, font=('楷体', 11),
                  bg=self.card_bg).pack(side='left', padx=(0, 6))
            Label(row, text=f'[{q["label"]}]', font=('楷体', 9),
                  bg=self.card_bg, fg=self.primary,
                  width=7, anchor='w').pack(side='left')
            Label(row, text=word.get('kanji', ''), font=('楷体', 11, 'bold'),
                  bg=self.card_bg, fg=self.text,
                  width=12, anchor='w').pack(side='left')
            Label(row, text=word.get('furigana', ''), font=('楷体', 10),
                  bg=self.card_bg, fg=self.primary,
                  width=16, anchor='w').pack(side='left')
            Label(row, text=defs, font=('楷体', 10),
                  bg=self.card_bg, fg=self.text_sec,
                  anchor='w').pack(side='left', padx=(4, 0))

    def _next_round(self):
        """错题回池，再从剩余词库抽一组"""
        for i, word in enumerate(self.quiz_words):
            if self.score_log[i] is False:
                self.current_pool.append(word)
        if not self.wrong_bank_mode:
            selected = [lv for lv in LEVELS if self.selected_levels[lv].get()]
            save_progress(selected, self.current_pool)
        self._draw_quiz()

    def _go_home(self):
        """返回主页（选择题库页），有剩余词则存档"""
        if getattr(self, 'wrong_bank_mode', False):
            self.wrong_bank_mode = False
            self._show_wrong_bank()
        else:
            if self.current_pool:
                selected = [lv for lv in LEVELS if self.selected_levels[lv].get()]
                save_progress(selected, self.current_pool)
            else:
                clear_progress()
            self._show_screen('setup')
            self._update_level_info()
            self._build_nav(self.nav_setup, 'setup')

    # ── 界面切换 ──────────────────────────
    def _show_screen(self, name):
        for f in (self.frame_setup, self.frame_progress, self.frame_wrong_bank,
                  self.frame_quiz, self.frame_result):
            f.pack_forget()
        getattr(self, f'frame_{name}').pack(fill='both', expand=True)

    def _on_close(self):
        """窗口关闭时保存进度"""
        if not self.wrong_bank_mode:
            selected = [lv for lv in LEVELS if self.selected_levels[lv].get()]
            if selected and self.current_pool:
                save_progress(selected, self.current_pool)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = QuizApp()
    app.run()
