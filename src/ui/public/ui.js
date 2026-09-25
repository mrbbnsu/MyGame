/**
 * F1/WO-008：最小 UI 前端（纯 JS ES Module，零依赖零构建）。
 *
 * 红线：不 spawn 进程、不做二进制解析、不硬编码卡名——
 *   一切数据来自 /api（卡名/效果经 /api/cards 精简卡表按 passcode join）。
 * 热座（K6）：viewer 由服务端强制为当前应答玩家；本文件只渲染与收集操作。
 */

const $ = (id) => document.getElementById(id);
const api = async (path, body) => {
  const opts = body === undefined
    ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' },
             body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!data.ok) throw new Error(data.error ? `${data.error.code}: ${data.error.message}` : '未知错误');
  return data.result;
};

let cards = {};            // passcode -> {name, card_type, flags, race, attribute, level, atk, def, desc}
let cur = null;            // {state, viewer, log}
let selMulti = [];         // SELECT_CARD 多选下标
let placePicks = [];       // SELECT_PLACE 多选下标
let logLen = 0;

const PHASE_CN = {
  DRAW: '抽牌阶段', STANDBY: '准备阶段', MAIN1: '主要阶段 1',
  BATTLE_START: '战斗阶段', BATTLE_STEP: '战斗步骤', DAMAGE: '伤害步骤',
  DAMAGE_CAL: '伤害计算', BATTLE: '战斗阶段', MAIN2: '主要阶段 2', END: '结束阶段',
};
const POS_CN = {
  faceup_attack: '表攻', facedown_attack: '盖卡', faceup_defense: '表守',
  facedown_defense: '盖卡', facedown: '盖卡', faceup: '表侧',
};
const TYPE_CN = { MONSTER: '怪兽', SPELL: '魔法', TRAP: '陷阱' };
const FLAG_CN = {
  NORMAL: '通常', EFFECT: '效果', FUSION: '融合', RITUAL: '仪式',
  SYNCHRO: '同调', XYZ: '超量', LINK: '连接', PENDULUM: '灵摆',
  TUNER: '调整', SPIRIT: '灵魂', TOON: '卡通', UNION: 'union', DUAL: '二重',
  FLIP: '反转', CONTINUOUS: '永续', COUNTER: '反击', EQUIP: '装备',
  FIELD: '场地', QUICKPLAY: '速攻', TOKEN: '衍生物',
};
const KIND_CN = {
  summon: '召唤', spsummon: '特殊召唤', reposition: '表示形式变更',
  mset: '盖放怪兽', sset: '盖放魔法/陷阱', activate: '发动', shuffle: '洗牌',
  to_bp: '进入战斗阶段', to_ep: '结束回合', to_m2: '进入主要阶段 2',
  attack: '攻击', chain: '连锁发动', position: '表示形式',
  place: '放置', accept: '是', decline: '否', option: '选项',
};

const cardName = (code) => (code !== null && cards[String(code)]
  ? cards[String(code)].name : `卡 #${code}`);
const cardImg = (code) => (code !== null ? `/art/${code}.jpg` : '/placeholder.svg');

/* ---------- 卡片 DOM ---------- */

function cardEl(code, pos, face, opts = {}) {
  const div = document.createElement('div');
  const down = face === false;
  div.className = 'card' + (down ? ' facedown' : '') + (opts.cls ? ` ${opts.cls}` : '');
  const visible = code !== null;
  const img = document.createElement('img');
  img.src = visible ? cardImg(code) : '/placeholder.svg';
  img.alt = '';
  img.loading = 'lazy';
  if (visible) {
    img.onerror = () => { img.onerror = null; img.src = '/placeholder.svg'; };
  }
  div.appendChild(img);
  const name = document.createElement('div');
  name.className = 'cname';
  name.textContent = visible ? cardName(code) : (down ? '盖卡' : '？？？');
  div.appendChild(name);
  if (opts.atk !== undefined && !down) {
    const stat = document.createElement('div');
    stat.className = 'cstat';
    const atk = opts.atk ?? '？';
    const def = opts.def ?? '？';
    stat.innerHTML = `<span class="atk-on">ATK ${atk}</span><span>DEF ${def}</span>`;
    div.appendChild(stat);
  }
  if (pos) {
    const badge = document.createElement('span');
    badge.className = 'pos-badge';
    badge.textContent = POS_CN[pos] ?? pos;
    div.appendChild(badge);
  }
  if (opts.hasAttacked) {
    const b = document.createElement('span');
    b.className = 'pos-badge';
    b.style.left = '2px';
    b.style.right = 'auto';
    b.textContent = '已攻击';
    div.appendChild(b);
  }
  if (visible) div.onclick = () => showDetail(code);
  return div;
}

function showDetail(code) {
  const c = cards[String(code)];
  if (!c) return;
  $('overlay-art').src = cardImg(code);
  $('overlay-art').onerror = function () { this.onerror = null; this.src = '/placeholder.svg'; };
  const flags = (c.flags ?? []).map((f) => FLAG_CN[f] ?? f).filter(
    (f) => !['怪兽', '魔法', '陷阱'].includes(f));
  const stat = [];
  if (c.level) stat.push(`★${c.level}`);
  if (c.attribute) stat.push(c.attribute);
  if (c.race) stat.push(`${c.race}族`);
  if (c.atk !== null && c.atk !== undefined) stat.push(`ATK ${c.atk}`);
  if (c.def !== null && c.def !== undefined) stat.push(`DEF ${c.def}`);
  $('overlay-info').innerHTML =
    `<h2>${c.name}</h2>` +
    `<div class="stat">[${TYPE_CN[c.card_type] ?? c.card_type}] ` +
    `${flags.join('/')}${stat.length ? '　' + stat.join(' / ') : ''}</div>` +
    `<div class="desc">${escapeHtml(c.desc)}</div>`;
  $('overlay').classList.remove('hidden');
}

const escapeHtml = (s) => String(s)
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

/* ---------- 布局渲染 ---------- */

function zoneEl(containerId, slots, kind) {
  const box = $(containerId);
  box.innerHTML = '';
  const show = kind === 'm' ? 5 : 5;      // 经典池只用前 5 槽；多余槽不渲染
  for (let i = 0; i < show; i++) {
    const wrap = document.createElement('div');
    wrap.className = 'zone-slot';
    const c = slots[i];
    if (c) {
      wrap.appendChild(cardEl(c.code, c.pos, c.face,
        { atk: c.atk, def: c.def, hasAttacked: c.has_attacked }));
    }
    box.appendChild(wrap);
  }
}

function playerBar(prefix, player, data) {
  $(`${prefix}-name`).textContent = `玩家 ${player + 1}`;
  $(`${prefix}-lp`).textContent = `LP ${data.lp}`;
  $(`${prefix}-counts`).textContent =
    `手牌 ${data.hand.length} · 卡组 ${data.deck_count} · 墓地 ${data.graveyard.length} · 除外 ${data.banished.length} · 额外 ${data.extra_count}`;
}

function renderHand(hand) {
  const box = $('hand');
  box.innerHTML = '';
  for (const h of hand) {
    const el = h.code !== null
      ? cardEl(h.code, null, true, { cls: 'handcard' })
      : Object.assign(document.createElement('div'), { className: 'handcard', textContent: '？？？' });
    if (h.code === null) {
      el.style.display = 'flex';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.color = '#8899aa';
    }
    box.appendChild(el);
  }
}

function choiceLabel(c) {
  const kind = KIND_CN[c.kind] ?? c.kind;
  if (c.kind === 'attack') {
    const n = cardName(c.attacker?.code ?? null);
    return c.direct ? `攻击（${n} · 直接攻击）` : `攻击（${n}）`;
  }
  if (c.card) {
    const n = cardName(c.card.code);
    return c.desc ? `${kind}：${n}` : `${kind} ${n}`;
  }
  if (c.kind === 'position') {
    return { faceup_attack: '表侧攻击表示', facedown_attack: '里侧攻击表示',
             faceup_defense: '表侧守备表示', facedown_defense: '里侧守备表示',
             facedown: '盖放', faceup: '表侧' }[c.pos] ?? c.pos;
  }
  if (c.kind === 'place') {
    const zone = c.zone === 'monster' ? '怪兽区' : '魔法陷阱区';
    return `${zone} 第 ${c.seq + 1} 格${c.owner !== undefined ? '' : ''}`;
  }
  if (c.kind === 'option') return `选项 #${c.desc}`;
  return kind;
}

/* ---------- pending 操作面板（K5：全类型可操作） ---------- */

function renderPending(state, viewer) {
  const p = state.pending;
  const body = $('pending-body');
  body.innerHTML = '';
  selMulti = [];
  placePicks = [];
  if (state.winner !== null || !p) {
    $('pending-title').textContent = state.winner !== null ? '对局结束' : '等待中';
    return;
  }
  const youAre = p.player === viewer;
  $('pending-title').textContent =
    `等待玩家 ${p.player + 1} 操作 —— ${pendingTypeName(p)}`;
  if (p.prompt) body.appendChild(el('div', 'prompt', `提示（效果描述 id）：${p.prompt}`));

  const single = async (i) => act({ choice: i });

  if (p.type === 'IDLE' || p.type === 'SELECT_BATTLE') {
    const wrap = el('div', 'choices');
    p.choices.forEach((c, i) => {
      const b = el('button', 'choice', choiceLabel(c));
      b.onclick = () => single(i);
      wrap.appendChild(b);
    });
    body.appendChild(wrap);
    return;
  }
  if (p.type === 'SELECT_CHAIN' || p.type === 'SELECT_OPTION') {
    const wrap = el('div', 'choices');
    p.choices.forEach((c, i) => {
      const b = el('button', 'choice', choiceLabel(c));
      b.onclick = () => single(i);
      wrap.appendChild(b);
    });
    body.appendChild(wrap);
    addCancel(body, p);
    return;
  }
  if (p.type === 'EFFECT_YESNO' || p.type === 'SELECT_YESNO') {
    const who = p.card ? `「${cardName(p.card.code)}」` : '';
    body.appendChild(el('div', 'prompt', `${who} 是否发动/执行？`));
    const wrap = el('div', 'choices');
    p.choices.forEach((c, i) => {
      const b = el('button', 'choice', choiceLabel(c));
      b.onclick = () => single(i);
      wrap.appendChild(b);
    });
    body.appendChild(wrap);
    return;
  }
  if (p.type === 'SELECT_POSITION') {
    const wrap = el('div', 'choices');
    p.choices.forEach((c, i) => {
      const b = el('button', 'choice', choiceLabel(c));
      b.onclick = () => single(i);
      wrap.appendChild(b);
    });
    body.appendChild(wrap);
    return;
  }
  if (p.type === 'SELECT_CARD') {
    body.appendChild(el('div', 'meta',
      `选择 ${p.min === p.max ? p.min : `${p.min} ~ ${p.max}`} 张（点击卡片切换选中）`));
    const wrap = el('div', 'choices');
    p.choices.forEach((c, i) => {
      const ref = c.card ?? {};
      const b = el('button', 'choice', cardName(ref.code) + zoneTag(ref));
      b.onclick = () => {
        if (selMulti.includes(i)) selMulti = selMulti.filter((x) => x !== i);
        else if (selMulti.length < p.max) selMulti.push(i);
        b.classList.toggle('sel', selMulti.includes(i));
        okBtn.textContent = `确定（已选 ${selMulti.length}/${p.min}~${p.max}）`;
      };
      wrap.appendChild(b);
    });
    body.appendChild(wrap);
    const okBtn = el('button', '', `确定（已选 0/${p.min}~${p.max}）`);
    okBtn.onclick = () => act({ choice: selMulti });
    const actions = el('div', 'actions');
    actions.appendChild(okBtn);
    addCancel(actions, p);
    body.appendChild(actions);
    return;
  }
  if (p.type === 'SELECT_PLACE') {
    body.appendChild(el('div', 'meta',
      `选择 ${p.count} 个位置（点击下方按钮；${p.disfield ? '对手指定你方区域' : '可选位置已剔除禁用格'}）`));
    const wrap = el('div', 'choices');
    p.choices.forEach((c, i) => {
      const b = el('button', 'choice', choiceLabel(c));
      b.onclick = () => {
        if (p.count === 1) return single(i);
        if (!placePicks.includes(i) && placePicks.length < p.count) placePicks.push(i);
        b.classList.toggle('sel', placePicks.includes(i));
        if (placePicks.length === p.count) act({ choice: placePicks });
      };
      wrap.appendChild(b);
    });
    body.appendChild(wrap);
    return;
  }
  if (p.type === 'SELECT_OTHER') {
    body.appendChild(el('div', 'meta',
      `暂不支持的可选类型「${p.msg}」，参数已保留；${p.cancelable ? '可尝试取消跳过。' : '该询问无取消路径——若卡住请重新开局并反馈给 PM。'}`));
    addCancel(body, p);
    return;
  }
  body.appendChild(el('div', 'meta', `未知类型 ${p.type}`));
}

function pendingTypeName(p) {
  const names = {
    IDLE: '主要阶段行动', SELECT_BATTLE: '战斗阶段指令', SELECT_CHAIN: '是否连锁',
    EFFECT_YESNO: '发动确认', SELECT_YESNO: '确认', SELECT_OPTION: '选项',
    SELECT_CARD: '选择卡片', SELECT_PLACE: '选择区域', SELECT_POSITION: '选择表示形式',
    SELECT_OTHER: '其他询问',
  };
  return names[p.type] ?? p.type;
}

function zoneTag(ref) {
  if (ref.loc === undefined) return '';
  const where = { 0x01: '卡组', 0x02: '手牌', 0x04: '怪兽区', 0x08: '魔陷区',
                  0x10: '墓地', 0x20: '除外', 0x40: '额外' }[ref.loc];
  return where ? `（${where}）` : '';
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function addCancel(container, p) {
  if (!p.cancelable) return;
  const b = el('button', 'cancel', '取消');
  b.onclick = () => act({ cancel: true });
  container.appendChild(b);
}

/* ---------- 日志（事件 → 中文行，卡名 join 精简卡表） ---------- */

function renderLog(log) {
  const box = $('log');
  if (logLen === 0) box.innerHTML = '';   // 每次 renderAll 从头重放已累积日志
  for (; logLen < log.length; logLen++) {
    for (const line of eventLines(log[logLen])) {
      const d = el('div', 'new', line);
      box.appendChild(d);
    }
  }
  box.scrollTop = box.scrollHeight;
}

function eventLines(ev) {
  const n = (p) => `玩家 ${p + 1}`;
  const code = (ref) => (ref && ref.code !== null && ref.code !== undefined
    ? cardName(ref.code) : '盖卡');
  switch (ev.type) {
    case 'NEW_TURN': return [`—— ${n(ev.turn_player)} 的回合 ——`];
    case 'NEW_PHASE': return [`${n(ev.turn_player ?? cur?.state?.turn_player ?? 0)}：进入${PHASE_CN[ev.phase_name] ?? ev.phase_name ?? ''}`];
    case 'DRAW': return [`${n(ev.player)} 抽了 ${ev.cards.length} 张卡`];
    case 'SUMMONING': return [`${n(ev.at.con)} 召唤 ${code(ev)}`];
    case 'SPSUMMONING': return [`${n(ev.at.con)} 特殊召唤 ${code(ev)}`];
    case 'SET': {
      const own = ev.at.con === (cur?.viewer ?? 0) && ev.code !== null;
      return [`${n(ev.at.con)} 盖放 ${own ? code(ev) : '一张卡'}`];
    }
    case 'FLIPSUMMONING': return [`${n(ev.at.con)} 反转召唤 ${code(ev)}`];
    case 'ATTACK': {
      const attacker = ev.attacker.code !== null && ev.attacker.code !== undefined
        ? cardName(ev.attacker.code) : `怪兽区第 ${ev.attacker.seq + 1} 格`;
      const target = ev.target && ev.target.loc === 0
        ? '（直接攻击）'
        : `对方怪兽区第 ${(ev.target?.seq ?? 0) + 1} 格`;
      return [`${attacker} 宣言攻击 → ${target}`];
    }
    case 'BATTLE': return [`战斗：${ev.aa} vs ${ev.da}（伤害 ${ev.dd} / ${ev.bd1}）`];
    case 'DAMAGE': return [`${n(ev.player)} 受到 ${ev.amount} 伤害`];
    case 'RECOVER': return [`${n(ev.player)} 回复 ${ev.amount} LP`];
    case 'PAY_LPCOST': return [`${n(ev.player)} 支付 ${ev.amount} LP`];
    case 'LPUPDATE': return [`${n(ev.player)} LP → ${ev.lp}`];
    case 'CHAINING': return [`连锁发动：${code(ev)}`];
    case 'WIN': return [ev.winner === 2
      ? '—— 平局 ——'
      : `—— ${n(ev.winner)} 获胜（${{ 0: '认输', 1: 'LP 归零', 2: '卡组抽尽' }[ev.reason] ?? '理由#' + ev.reason}）——`];
    case 'RETRY': return ['操作被拒绝，请重选'];
    case 'SHUFFLE_DECK': return [`${n(ev.player)} 派了卡组`];
    case 'DECK_TOP': case 'CONFIRM_CARDS': case 'CONFIRM_DECKTOP':
      return [`${n(ev.player ?? 0)} 确认了卡组顶/卡片`];
    default: return [];
  }
}

/* ---------- 主渲染 ---------- */

function renderAll(result) {
  cur = result;
  const { state, viewer } = result;
  logLen = 0;
  $('setup').classList.add('hidden');
  $('arena').classList.remove('hidden');
  $('duel-status').classList.remove('hidden');

  const me = state.players[viewer];
  const opp = state.players[1 - viewer];
  $('me-name').textContent = `玩家 ${viewer + 1}（你）`;
  playerBar('me', viewer, me);
  playerBar('opp', 1 - viewer, opp);
  $('turn-info').textContent =
    `回合 ${state.turn_count} · 玩家 ${state.turn_player + 1} · ${PHASE_CN[state.phase] ?? state.phase ?? ''}`;
  $('lp-info').textContent = `LP ${me.lp} : ${opp.lp}`;

  zoneEl('me-monster', me.monster_zones, 'm');
  zoneEl('me-spell', me.spell_trap_zones, 's');
  zoneEl('opp-monster', opp.monster_zones, 'm');
  zoneEl('opp-spell', opp.spell_trap_zones, 's');
  renderHand(me.hand);

  // 交接横幅（K6）：viewer 跟随应答方；应答方 ≠ 回合玩家时提示
  const handoff = $('handoff');
  if (state.winner !== null) {
    handoff.classList.add('hidden');
  } else if (state.pending && viewer !== state.turn_player) {
    handoff.textContent = `对方回合的询问：请交给 玩家 ${viewer + 1} 操作（当前询问：${pendingTypeName(state.pending)}）`;
    handoff.classList.remove('hidden');
  } else {
    handoff.classList.add('hidden');
  }

  renderPending(state, viewer);
  renderLog(result.log);

  const banner = $('winner-banner');
  if (state.winner !== null) {
    banner.textContent = state.winner === 2
      ? '平局！'
      : `玩家 ${state.winner + 1} 获胜！`;
    banner.classList.remove('hidden');
  } else {
    banner.classList.add('hidden');
  }
}

async function act(body) {
  try {
    // 应答前 viewer = 应答方；应答后 pending 可能转给另一方 —— 此时必须
    // 重新 /api/state 换视角渲染（服务端 viewer 自动跟随 pending.player，K6）
    const answeredAs = cur ? cur.viewer : null;
    const result = await api('/api/respond', body);
    renderAll(result);
    if (result.state.pending && answeredAs !== null &&
        result.state.pending.player !== answeredAs) {
      renderAll(await api('/api/state'));
    }
  } catch (e) {
    toast(String(e.message ?? e));
  }
}

async function refresh() {
  try {
    renderAll(await api('/api/state'));
  } catch { /* 服务重启中，忽略一次 */ }
}

function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 2600);
}

/* ---------- 启动 ---------- */

async function boot() {
  cards = await api('/api/cards');
  // 页面刷新/误关后恢复进行中的对局（服务端视角自动跟随）
  try {
    const live = await api('/api/state');
    if (live.state) renderAll(live);
  } catch { /* 无对局或服务未就绪 */ }
  const decks = await api('/api/decks');
  const sel1 = $('deck-p1');
  const sel2 = $('deck-p2');
  for (const d of decks) {
    for (const sel of [sel1, sel2]) {
      const o = document.createElement('option');
      o.value = d.file;
      o.textContent = `${d.name}（${d.count} 张）`;
      sel.appendChild(o);
    }
  }
  if (decks.length >= 2) sel2.selectedIndex = 1;
  $('btn-start').onclick = async () => {
    try {
      const result = await api('/api/new_duel', {
        player_deck: sel1.value,
        opponent_deck: sel2.value,
      });
      renderAll(result);
    } catch (e) {
      toast(String(e.message ?? e));
    }
  };
  $('btn-restart').onclick = () => {
    $('winner-banner').classList.add('hidden');
    $('arena').classList.add('hidden');
    $('duel-status').classList.add('hidden');
    $('setup').classList.remove('hidden');
  };
  $('overlay-close').onclick = () => $('overlay').classList.add('hidden');
  $('overlay').onclick = (e) => {
    if (e.target === $('overlay')) $('overlay').classList.add('hidden');
  };
}

boot().catch((e) => toast(`初始化失败: ${e.message ?? e}`));
