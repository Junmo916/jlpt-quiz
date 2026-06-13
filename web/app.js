/* =====================================================
   日文背词 — JLPT 10k 填空练习（移动端 PWA）
   ===================================================== */

// ── 常量 ──────────────────────────────────
const LEVELS = ['N5', 'N4', 'N3', 'N2', 'N1'];
const LEVEL_LABELS = {
  N5: 'N5（入门）', N4: 'N4（基础）',
  N3: 'N3（中级）', N2: 'N2（中上级）', N1: 'N1（上级）',
};
const MIN_EF = 1.3;
const SRS_KEY = 'jlpt_srs';
const STATS_KEY = 'jlpt_stats';
const WRONG_KEY = 'jlpt_wrong';
const PROGRESS_KEY = 'jlpt_progress';

// ── 工具函数 ──────────────────────────────

function cardKey(word) {
  const lv = word._level || '';
  const kj = word.kanji || '';
  const fr = word.furigana || '';
  return `${lv}:${kj}:${fr}`;
}

function normalize(s) {
  s = (s || '').trim().replace(/ /g, '').replace(/\u3000/g, '');
  let result = '';
  for (const ch of s) {
    const code = ch.charCodeAt(0);
    if (0xFF01 <= code && code <= 0xFF5E) {
      result += String.fromCharCode(code - 0xFEE0);
    } else {
      result += ch;
    }
  }
  return result.toLowerCase();
}

function matchFurigana(user, correct) {
  if (!(user || '').trim()) return false;
  const a = normalize(user), b = normalize(correct);
  if (a === b) return true;
  if (b.startsWith(a) && a.length >= 2) return true;
  if (a.startsWith(b) && b.length >= 2) return true;
  return false;
}

function matchMeaning(user, correct) {
  if (!(user || '').trim() || !correct) return false;
  const a = normalize(user), b = normalize(correct);
  if (a === b) return true;
  if (a.length >= 2 && b.includes(a)) return true;
  if (b.length >= 2 && a.includes(b)) return true;
  return false;
}

function matchKanji(user, correct) {
  if (!(user || '').trim()) return false;
  return normalize(user) === normalize(correct);
}

// ── Storage helpers ───────────────────────

function storageGet(key, def) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : def;
  } catch { return def; }
}
function storageSet(key, val) {
  localStorage.setItem(key, JSON.stringify(val));
}

// ── SRS ───────────────────────────────────

function srsLoad() { return storageGet(SRS_KEY, {}); }
function srsSave(data) { storageSet(SRS_KEY, data); }

function srsGetOrCreate(word) {
  const data = srsLoad();
  const key = cardKey(word);
  if (!data[key]) {
    data[key] = {
      level: word._level || '',
      kanji: word.kanji || '',
      furigana: word.furigana || '',
      ease_factor: 2.5,
      interval: 0,
      repetitions: 0,
      next_review: null,
      last_reviewed: null,
      total_correct: 0,
      total_wrong: 0,
    };
    srsSave(data);
  }
  return data[key];
}

function srsReview(word, isCorrect) {
  const quality = isCorrect ? 4 : 1;
  const data = srsLoad();
  const key = cardKey(word);
  if (!data[key]) {
    srsGetOrCreate(word);
    return srsReview(word, isCorrect); // retry
  }
  const card = data[key];
  const today = new Date().toISOString().slice(0, 10);
  let ef = card.ease_factor || 2.5;
  let reps = card.repetitions || 0;
  let interval = card.interval || 0;

  if (quality >= 3) {
    if (reps === 0) interval = 1;
    else if (reps === 1) interval = 6;
    else interval = Math.round(interval * ef);
    reps++;
    card.total_correct = (card.total_correct || 0) + 1;
  } else {
    reps = 0;
    interval = 1;
    ef = nextEF(ef, quality);
    card.total_wrong = (card.total_wrong || 0) + 1;
  }
  ef = nextEF(ef, quality);

  const next = new Date();
  next.setDate(next.getDate() + interval);
  card.ease_factor = Math.round(ef * 100) / 100;
  card.interval = interval;
  card.repetitions = reps;
  card.next_review = next.toISOString().slice(0, 10);
  card.last_reviewed = today;
  srsSave(data);
}

function nextEF(ef, quality) {
  return Math.max(MIN_EF, ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)));
}

function srsIsDue(word) {
  const data = srsLoad();
  const key = cardKey(word);
  const card = data[key];
  if (!card) return true;
  const nr = card.next_review;
  if (!nr) return true;
  return nr <= new Date().toISOString().slice(0, 10);
}

function srsGetReviewStats(levels) {
  const data = srsLoad();
  const today = new Date().toISOString().slice(0, 10);
  let due = 0, learned = 0, total = 0;
  for (const key in data) {
    const card = data[key];
    if (!levels.includes(card.level)) continue;
    total++;
    if (card.repetitions >= 3) learned++;
    const nr = card.next_review;
    if (!nr || nr <= today) due++;
  }
  return { due, learned, total };
}

function srsGetLearnedCount(levels) {
  const data = srsLoad();
  let count = 0;
  for (const key in data) {
    const card = data[key];
    if (!levels.includes(card.level)) continue;
    if (card.repetitions >= 3) count++;
  }
  return count;
}

function srsGetNewCount(levels, pool) {
  const data = srsLoad();
  let count = 0;
  for (const lv of levels) {
    for (const w of (pool[lv] || [])) {
      const key = cardKey({ _level: lv, ...w });
      if (!data[key]) count++;
    }
  }
  return count;
}

// ── Wrong Bank ────────────────────────────

function wbLoad() { return storageGet(WRONG_KEY, {}); }
function wbSave(data) { storageSet(WRONG_KEY, data); }
function wbTotalCount() {
  const bank = wbLoad();
  return Object.values(bank).reduce((s, arr) => s + arr.length, 0);
}

function wbAdd(level, word) {
  const bank = wbLoad();
  if (!bank[level]) bank[level] = [];
  const key = `${word.kanji || ''}|${word.furigana || ''}`;
  const found = bank[level].find(e => `${e.kanji || ''}|${e.furigana || ''}` === key);
  if (found) {
    found.wrong_count = (found.wrong_count || 0) + 1;
  } else {
    const entry = { ...word, wrong_count: 1 };
    delete entry._level;
    bank[level].push(entry);
  }
  wbSave(bank);
}

function wbRemove(level, word) {
  const bank = wbLoad();
  if (!bank[level]) return;
  const key = `${word.kanji || ''}|${word.furigana || ''}`;
  bank[level] = bank[level].filter(e => `${e.kanji || ''}|${e.furigana || ''}` !== key);
  if (!bank[level].length) delete bank[level];
  wbSave(bank);
}

// ── Stats ─────────────────────────────────

function statsLoad() { return storageGet(STATS_KEY, { days: {}, by_level: {}, streak: 0, last_active: null }); }
function statsSave(data) { storageSet(STATS_KEY, data); }

function statsRecordSession(levels, total, correct, incorrect) {
  const data = statsLoad();
  const today = new Date().toISOString().slice(0, 10);
  const day = data.days[today] || { total: 0, correct: 0, incorrect: 0 };
  day.total += total;
  day.correct += correct;
  day.incorrect += incorrect;
  data.days[today] = day;

  const key = [...levels].sort().join('+');
  const lv = data.by_level[key] || { total: 0, correct: 0, incorrect: 0 };
  lv.total += total;
  lv.correct += correct;
  lv.incorrect += incorrect;
  data.by_level[key] = lv;

  data.last_active = today;
  data.streak = recalcStreak(data.days, today);
  statsSave(data);
}

function recalcStreak(days, today) {
  let dt = new Date(today);
  let streak = 0;
  for (let i = 0; i < 365; i++) {
    const key = dt.toISOString().slice(0, 10);
    if ((days[key] || {}).total > 0) {
      streak++;
      dt.setDate(dt.getDate() - 1);
    } else break;
  }
  return streak;
}

function statsOverall() {
  const data = statsLoad();
  const days = data.days || {};
  let total = 0, correct = 0, incorrect = 0;
  for (const key in days) {
    total += days[key].total;
    correct += days[key].correct;
    incorrect += days[key].incorrect;
  }
  return {
    total_sessions: Object.keys(days).length,
    total_attempts: total,
    total_correct: correct,
    total_incorrect: incorrect,
    accuracy: total ? Math.round(correct / total * 1000) / 10 : 0,
    streak: data.streak || 0,
    last_active: data.last_active || '',
  };
}

function statsToday() {
  const data = statsLoad();
  const key = new Date().toISOString().slice(0, 10);
  return data.days[key] || { total: 0, correct: 0, incorrect: 0 };
}

// ── Progress ──────────────────────────────

function progressSave(levels, remaining) {
  storageSet(PROGRESS_KEY, { levels, remaining });
}
function progressLoad() {
  return storageGet(PROGRESS_KEY, null);
}
function progressClear() {
  localStorage.removeItem(PROGRESS_KEY);
}

// ── 应用状态 ──────────────────────────────

const App = {
  wordPool: {},      // { N5: [...], N4: [...], ... }
  selectedLevels: [],
  quizWords: [],
  quizQuestions: [],
  currentIdx: 0,
  quizCount: 10,
  correctCount: 0,
  incorrectCount: 0,
  scoreLog: [],
  currentPool: [],
  wrongBankMode: false,
  answered: false,
  currentScreen: 'setup',

  // DOM 引用缓存
  els: {},
};

// ── Data Loading ──────────────────────────

async function loadWordData() {
  App.wordPool = {};
  for (const lv of LEVELS) {
    const resp = await fetch(`../quiz/data/${lv}.json`);
    const data = await resp.json();
    App.wordPool[lv] = data.words;
  }
}

// ── Screen Navigation ─────────────────────

function showScreen(name) {
  document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
  const target = document.getElementById(`screen-${name}`);
  if (target) target.classList.add('active');
  App.currentScreen = name;
}

// ── HTML 模板 ─────────────────────────────

function buildQuestion(word, type) {
  const kanji = word.kanji || '';
  const furi = word.furigana || '';
  const sc = word.def_sc || '';
  if (type === 'jp2cn') {
    return { type, label: '日译中', answer: sc, check: (u, k) => matchMeaning(u, sc) };
  } else {
    return { type, label: '中译日', answer: `${kanji}（${furi}）`, check: (u, k) => matchKanji(k, kanji) && matchFurigana(u, furi) };
  }
}

// ═══════════════════════════════════════════
//  Screen: SETUP
// ═══════════════════════════════════════════

function renderSetup() {
  const sel = document.getElementById('level-select');
  sel.innerHTML = '';
  for (const lv of LEVELS) {
    const label = document.createElement('label');
    label.className = 'level-item';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.value = lv;
    cb.checked = App.selectedLevels.includes(lv);
    cb.addEventListener('change', () => {
      if (cb.checked) {
        if (!App.selectedLevels.includes(lv)) App.selectedLevels.push(lv);
      } else {
        App.selectedLevels = App.selectedLevels.filter(l => l !== lv);
      }
      updateLevelInfo();
    });
    label.appendChild(cb);
    const span = document.createElement('span');
    span.textContent = `${LEVEL_LABELS[lv]}（${(App.wordPool[lv] || []).length} 词）`;
    label.appendChild(span);
    sel.appendChild(label);
  }

  document.getElementById('quiz-count').value = App.quizCount;
  updateLevelInfo();
}

function updateLevelInfo() {
  const levels = App.selectedLevels;
  const total = levels.reduce((s, lv) => s + (App.wordPool[lv] || []).length, 0);
  const info = document.getElementById('level-info');
  const srsInfo = document.getElementById('srs-summary');

  if (levels.length) {
    const ss = srsGetReviewStats(levels);
    info.textContent = `已选 ${levels.length} 个级别，共 ${total} 词 | 待复习 ${ss.due} 已掌握 ${ss.learned}`;
    srsInfo.textContent = `总学习卡片 ${ss.total} 今日到期 ${ss.due} 新词待学 ${srsGetNewCount(levels, App.wordPool)}`;

    const o = statsOverall();
    const t = statsToday();
    document.getElementById('streak-display').textContent =
      `今日 ${t.total} 题  累计正确率 ${o.accuracy}%  连续 ${o.streak} 天`;
    document.getElementById('streak-display').style.display = 'block';

    document.getElementById('btn-start').disabled = false;
  } else {
    info.textContent = '请至少选择一个级别';
    srsInfo.textContent = '';
    document.getElementById('streak-display').style.display = 'none';
    document.getElementById('btn-start').disabled = true;
  }
}

function startQuiz() {
  const levels = App.selectedLevels;
  if (!levels.length) return;
  const qc = parseInt(document.getElementById('quiz-count').value) || 10;
  App.quizCount = qc;

  let pool = [];
  for (const lv of levels) {
    for (const w of (App.wordPool[lv] || [])) {
      pool.push({ ...w, _level: lv });
    }
  }
  if (pool.length < qc) {
    alert(`所选级别共 ${pool.length} 词，不足 ${qc} 题`);
    return;
  }
  progressClear();
  App.wrongBankMode = false;
  App.currentPool = pool;
  drawQuiz();
}

// ═══════════════════════════════════════════
//  Screen: QUIZ
// ═══════════════════════════════════════════

function drawQuiz() {
  const pool = App.currentPool;
  if (!pool.length) {
    alert('当前词库已全部学完！');
    goHome();
    return;
  }
  const qc = App.quizCount;

  // Shuffle + SRS priority
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }
  pool.sort((a, b) => srsIsDue(a) ? -1 : 1);

  const take = Math.min(qc, pool.length);
  App.quizWords = pool.slice(0, take);
  App.currentPool = pool.slice(take);

  const halfJp = Math.floor(take / 2);
  const halfCn = take - halfJp;
  const types = [...Array(halfJp).fill('jp2cn'), ...Array(halfCn).fill('cn2jp')];
  for (let i = types.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [types[i], types[j]] = [types[j], types[i]];
  }

  App.quizQuestions = App.quizWords.map((w, i) => buildQuestion(w, types[i]));
  App.scoreLog = Array(take).fill(null);
  App.currentIdx = 0;
  App.correctCount = 0;
  App.incorrectCount = 0;
  App.answered = false;

  renderQuestion();
  showScreen('quiz');
}

function renderQuestion() {
  const idx = App.currentIdx;
  const word = App.quizWords[idx];
  const q = App.quizQuestions[idx];
  App.answered = false;

  document.getElementById('progress-bar').style.width = `${(idx / App.quizCount) * 100}%`;
  document.getElementById('q-counter').textContent = `第 ${idx+1} / ${App.quizCount} 题`;
  document.getElementById('q-type').textContent = `[${q.label}]`;
  document.getElementById('q-score').textContent = `✓ ${App.correctCount}  ✗ ${App.incorrectCount}`;
  document.getElementById('q-remaining').textContent = `剩余 ${App.currentPool.length} 词`;

  const wordArea = document.getElementById('word-area');
  const defArea = document.getElementById('def-area');
  const posArea = document.getElementById('pos-area');
  const inputArea = document.getElementById('input-area');
  const prompt1 = document.getElementById('prompt1');
  const prompt2 = document.getElementById('prompt2');
  const input2Group = document.getElementById('input2-group');
  const feedback = document.getElementById('feedback');
  const submitBtn = document.getElementById('btn-submit');
  const nextBtn = document.getElementById('btn-next');

  wordArea.style.display = 'none';
  defArea.style.display = 'none';
  posArea.style.display = 'none';
  inputArea.style.display = 'none';
  input2Group.style.display = 'none';
  feedback.style.display = 'none';
  submitBtn.style.display = 'none';
  nextBtn.style.display = 'none';
  document.getElementById('pronounce-btn').style.display = 'none';

  document.getElementById('ans-input1').value = '';
  document.getElementById('ans-input2').value = '';
  document.getElementById('ans-input1').disabled = false;
  document.getElementById('ans-input2').disabled = false;

  if (q.type === 'jp2cn') {
    wordArea.style.display = 'block';
    document.getElementById('q-furigana').textContent = word.furigana || '';
    document.getElementById('q-kanji').textContent = word.kanji || '（无汉字）';
    const pos = [word.pos, word.pitch].filter(Boolean).join(' · ');
    if (pos) { posArea.textContent = pos; posArea.style.display = 'block'; }
    prompt1.textContent = '请输入中文释义：';
    prompt2.textContent = '';
    document.getElementById('pronounce-btn').style.display = 'inline-block';
  } else {
    defArea.style.display = 'block';
    document.getElementById('q-def').textContent = word.def_sc || '';
    prompt1.textContent = '请输入日语汉字：';
    prompt2.textContent = '请输入读音（振假名）：';
    input2Group.style.display = 'block';
  }

  inputArea.style.display = 'block';
  submitBtn.style.display = 'block';
  document.getElementById('ans-input1').focus();
}

function submitAnswer() {
  if (App.answered) return;
  const idx = App.currentIdx;
  const q = App.quizQuestions[idx];
  const user1 = document.getElementById('ans-input1').value;
  const user2 = document.getElementById('ans-input2').value;
  const correct = q.check(user1, user2);
  App.answered = true;

  const word = App.quizWords[idx];
  srsReview(word, correct);

  if (correct) {
    App.correctCount++;
    if (App.wrongBankMode) {
      const lv = word._level || '';
      if (lv) wbRemove(lv, word);
    }
  } else {
    App.incorrectCount++;
    const lv = word._level || '';
    if (lv) wbAdd(lv, word);
  }

  App.scoreLog[idx] = correct;
  document.getElementById('q-score').textContent = `✓ ${App.correctCount}  ✗ ${App.incorrectCount}`;
  document.getElementById('ans-input1').disabled = true;
  document.getElementById('ans-input2').disabled = true;
  document.getElementById('btn-submit').style.display = 'none';

  // Feedback
  const icon = correct ? '✅' : '❌';
  const feedback = document.getElementById('feedback');
  document.getElementById('fb-icon').textContent = icon;
  document.getElementById('fb-answer').textContent = `正确答案：${q.answer}`;

  // SRS status
  const card = srsGetOrCreate(word);
  document.getElementById('fb-srs').textContent =
    `SRS 难度 ${card.ease_factor}  连续答对 ${card.repetitions} 次  下次复习 ${card.next_review || '—'}`;

  // VocabPlus
  const plus = (word.plus || '').trim();
  document.getElementById('fb-plus').textContent = plus ? `📌 ${plus}` : '';
  document.getElementById('fb-plus').style.display = plus ? 'block' : 'none';

  // Sentences
  const sents = word.sentences || [];
  const sentContainer = document.getElementById('fb-sentences');
  sentContainer.innerHTML = '';
  if (sents.length) {
    const title = document.createElement('div');
    title.className = 'sent-title';
    title.textContent = '例句：';
    sentContainer.appendChild(title);
    for (const s of sents.slice(0, 4)) {
      const txt = (s.furigana || s.kanji || '').replace(/<b>/g, '').replace(/<\/b>/g, '');
      const d = s.def_sc || '';
      const p = document.createElement('p');
      p.className = 'sent-item';
      p.innerHTML = `${txt}${d ? `<br><span class="sent-def">→ ${d}</span>` : ''}`;
      sentContainer.appendChild(p);
    }
  }

  feedback.style.display = 'block';

  if (idx + 1 < App.quizCount) {
    setTimeout(() => {
      document.getElementById('btn-next').style.display = 'block';
    }, 200);
  } else {
    setTimeout(showResult, 600);
  }
}

function nextQuestion() {
  App.currentIdx++;
  renderQuestion();
}

// ═══════════════════════════════════════════
//  Screen: RESULT
// ═══════════════════════════════════════════

function showResult() {
  showScreen('result');
  const total = App.quizWords.length;
  const pct = total ? Math.round(App.correctCount / total * 100) : 0;

  if (!App.wrongBankMode) {
    statsRecordSession(App.selectedLevels, total, App.correctCount, App.incorrectCount);
  }

  document.getElementById('result-title').textContent = App.wrongBankMode ? '错题复习结果' : '练习结果';
  document.getElementById('result-pct').textContent = `${pct}%`;

  const o = statsOverall();
  const learned = srsGetLearnedCount(App.selectedLevels);
  document.getElementById('result-detail').textContent =
    `${total} 题 · 正确 ${App.correctCount} · 错误 ${App.incorrectCount} · 剩余 ${App.currentPool.length} 词` +
    ` · 累计正确率 ${o.accuracy}% · 连续 ${o.streak} 天 · 已掌握 ${learned} 词`;

  const list = document.getElementById('result-list');
  list.innerHTML = '';
  for (let i = 0; i < App.quizWords.length; i++) {
    const word = App.quizWords[i];
    const ok = App.scoreLog[i];
    const q = App.quizQuestions[i];
    const icon = ok === true ? '✅' : ok === false ? '❌' : '⏭️';
    const row = document.createElement('div');
    row.className = 'result-row';
    row.innerHTML = `
      <span class="r-icon">${icon}</span>
      <span class="r-type">[${q.label}]</span>
      <span class="r-kanji">${word.kanji || ''}</span>
      <span class="r-furi">${word.furigana || ''}</span>
      <span class="r-def">${word.def_sc || ''}</span>
    `;
    list.appendChild(row);
  }
}

function nextRound() {
  for (let i = 0; i < App.quizWords.length; i++) {
    if (App.scoreLog[i] === false) {
      App.currentPool.push(App.quizWords[i]);
    }
  }
  if (!App.wrongBankMode) {
    progressSave(App.selectedLevels, App.currentPool);
  }
  drawQuiz();
}

function goHome() {
  if (App.wrongBankMode) {
    App.wrongBankMode = false;
    showWrongBank();
  } else {
    if (App.currentPool.length) {
      progressSave(App.selectedLevels, App.currentPool);
    } else {
      progressClear();
    }
    showScreen('setup');
    renderSetup();
  }
}

// ═══════════════════════════════════════════
//  Screen: WRONG BANK
// ═══════════════════════════════════════════

function showWrongBank(level) {
  showScreen('wrong');
  const bank = wbLoad();
  const total = wbTotalCount();
  const container = document.getElementById('wb-content');
  container.innerHTML = '';

  if (!total) {
    container.innerHTML = '<p class="empty-state">暂无错题 🎉</p>';
    document.getElementById('wb-level-select').style.display = 'none';
    document.getElementById('wb-btns').style.display = 'none';
    return;
  }

  document.getElementById('wb-level-select').style.display = 'block';
  document.getElementById('wb-btns').style.display = 'flex';

  if (level) {
    // Detail view
    document.getElementById('wb-level-select').style.display = 'none';
    document.getElementById('wb-btns').style.display = 'none';

    const back = document.createElement('button');
    back.className = 'btn btn-sm';
    back.textContent = '← 返回';
    back.addEventListener('click', () => showWrongBank());
    container.appendChild(back);

    const title = document.createElement('h3');
    title.textContent = LEVEL_LABELS[level];
    container.appendChild(title);

    const items = (bank[level] || []).sort((a, b) => (b.wrong_count || 0) - (a.wrong_count || 0));
    for (const item of items) {
      const row = document.createElement('div');
      row.className = 'result-row';
      row.innerHTML = `
        <span class="r-icon" style="color:var(--wrong)">×${item.wrong_count || 1}</span>
        <span class="r-kanji">${item.kanji || '（无汉字）'}</span>
        <span class="r-furi">${item.furigana || ''}</span>
        <span class="r-def">${item.def_sc || ''}</span>
      `;
      container.appendChild(row);
    }

    const reviewBtn = document.createElement('button');
    reviewBtn.className = 'btn btn-primary';
    reviewBtn.textContent = '复习此级别';
    reviewBtn.addEventListener('click', () => startWrongReview([level]));
    container.appendChild(reviewBtn);
  } else {
    // Directory view
    const sel = document.getElementById('wb-level-select');
    sel.innerHTML = '<p style="margin-bottom:8px;font-size:14px;color:var(--text-sec)">选择要复习的级别（可多选）：</p>';
    const selected = {};

    for (const lv of LEVELS) {
      const items = bank[lv] || [];
      if (!items.length) continue;
      const label = document.createElement('label');
      label.className = 'level-item';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = true;
      selected[lv] = cb;
      label.appendChild(cb);
      const span = document.createElement('span');
      span.textContent = `${LEVEL_LABELS[lv]}（${items.length} 个错词）`;
      label.appendChild(span);
      const viewBtn = document.createElement('button');
      viewBtn.className = 'btn btn-sm';
      viewBtn.textContent = '查看 →';
      viewBtn.addEventListener('click', (e) => { e.stopPropagation(); showWrongBank(lv); });
      label.appendChild(viewBtn);
      sel.appendChild(label);
    }

    sel.style.display = 'block';
    container.innerHTML = `<p>共 ${total} 个错词</p>`;

    window._wbSelected = selected;
    document.getElementById('btn-wb-review').onclick = () => {
      const levels = Object.keys(selected).filter(lv => selected[lv].checked);
      if (!levels.length) { alert('请至少勾选一个级别'); return; }
      startWrongReview(levels);
    };
    document.getElementById('btn-wb-clear').onclick = confirmClearWrong;
  }
}

function startWrongReview(levels) {
  const bank = wbLoad();
  let pool = [];
  for (const lv of levels) {
    for (const entry of (bank[lv] || [])) {
      const w = { ...entry, _level: lv };
      delete w.wrong_count;
      pool.push(w);
    }
  }
  if (!pool.length) { alert('错题本为空，无需复习！'); return; }
  App.wrongBankMode = true;
  App.currentPool = pool;
  drawQuiz();
}

function confirmClearWrong() {
  const container = document.getElementById('wb-content');
  container.innerHTML = `
    <div class="confirm-dialog">
      <p style="font-size:16px;font-weight:bold;margin-bottom:16px">确定要清空所有错题记录吗？</p>
      <div style="display:flex;gap:12px;justify-content:center">
        <button class="btn btn-danger" onclick="doClearWrong()">确认清空</button>
        <button class="btn" onclick="showWrongBank()">取消</button>
      </div>
    </div>
  `;
}

function doClearWrong() {
  wbSave({});
  showWrongBank();
}

// ═══════════════════════════════════════════
// 进度恢复
// ═══════════════════════════════════════════

function checkProgress() {
  const prog = progressLoad();
  if (prog && prog.remaining && prog.remaining.length) {
    const snack = document.getElementById('progress-snack');
    snack.textContent = `检测到上次进度：${prog.remaining.length} 词未学`;
    snack.style.display = 'flex';
    document.getElementById('btn-resume').onclick = () => {
      App.selectedLevels = prog.levels || [];
      for (const lv of LEVELS) {
        const cb = document.querySelector(`#level-select input[value="${lv}"]`);
        if (cb) cb.checked = App.selectedLevels.includes(lv);
      }
      App.wrongBankMode = false;
      App.currentPool = prog.remaining;
      drawQuiz();
      snack.style.display = 'none';
    };
    document.getElementById('btn-resume-clear').onclick = () => {
      progressClear();
      snack.style.display = 'none';
    };
  }
}

// ═══════════════════════════════════════════
//  底部导航更新
// ═══════════════════════════════════════════

function updateNav(active) {
  const items = {
    'nav-setup': () => { App.wrongBankMode = false; showScreen('setup'); renderSetup(); },
    'nav-wrong': () => { App.wrongBankMode = false; showWrongBank(); },
  };
  for (const [id, fn] of Object.entries(items)) {
    const el = document.getElementById(id);
    el.classList.toggle('active', id === active);
  }
  // Update wrong bank count
  const total = wbTotalCount();
  document.getElementById('nav-wrong').textContent = total ? `错题本(${total})` : '错题本';
}

// ═══════════════════════════════════════════
//  应用入口
// ═══════════════════════════════════════════

async function initApp() {
  // Show loading
  document.getElementById('app-loading').style.display = 'flex';

  await loadWordData();

  document.getElementById('app-loading').style.display = 'none';
  document.getElementById('app-root').style.display = 'flex';

  renderSetup();
  checkProgress();
  updateNav('nav-setup');

  // Event bindings
  document.getElementById('btn-start').addEventListener('click', startQuiz);
  document.getElementById('btn-submit').addEventListener('click', submitAnswer);
  document.getElementById('btn-next').addEventListener('click', nextQuestion);
  document.getElementById('btn-next-round').addEventListener('click', nextRound);
  document.getElementById('btn-go-home').addEventListener('click', goHome);
  document.getElementById('btn-go-home2').addEventListener('click', goHome);
  document.getElementById('ans-input1').addEventListener('keydown', e => {
    if (e.key === 'Enter') submitAnswer();
  });
  document.getElementById('ans-input2').addEventListener('keydown', e => {
    if (e.key === 'Enter') submitAnswer();
  });
  document.getElementById('pronounce-btn').addEventListener('click', () => {
    const word = App.quizWords[App.currentIdx];
    const text = word.furigana || word.kanji || '';
    if ('speechSynthesis' in window) {
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = 'ja-JP';
      speechSynthesis.speak(utter);
    }
  });

  // Navigation
  document.getElementById('nav-setup').addEventListener('click', () => {
    App.wrongBankMode = false;
    showScreen('setup');
    renderSetup();
    updateNav('nav-setup');
  });
  document.getElementById('nav-wrong').addEventListener('click', () => {
    App.wrongBankMode = false;
    showWrongBank();
    updateNav('nav-wrong');
  });

  // Keyboard shortcut from result screen
  document.addEventListener('keydown', e => {
    if (e.key === 'Enter' && App.currentScreen === 'result') {
      nextRound();
    }
  });

  // Quiz count change handler
  document.getElementById('quiz-count').addEventListener('change', () => {
    App.quizCount = parseInt(document.getElementById('quiz-count').value) || 10;
  });
}

// Start when DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
