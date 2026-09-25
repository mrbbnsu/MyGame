/**
 * F1/WO-008：UI 服务 /api/* 端点测试（node:test，spawn 真 Adapter 子进程）。
 * UI 渲染本身走 PM 人工验收（工单 §3.2），这里验证服务端协议与转发正确性。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import type { ChildProcess } from 'node:child_process';
import { startServer, type UiServer } from '../src/ui/server.ts';
import type { AdapterEvent, DuelState } from '../src/adapter/types.ts';

const BASE = 'http://127.0.0.1';

interface ApiResult {
  state: DuelState | null;
  viewer: 0 | 1 | null;
  log: AdapterEvent[];
}

async function get(srv: UiServer, path: string): Promise<{ status: number;
  body: any }> {
  const res = await fetch(`${BASE}:${srv.port}${path}`);
  return { status: res.status, body: await res.json() };
}

async function post(srv: UiServer, path: string, body: unknown): Promise<{ status: number;
  body: any }> {
  const res = await fetch(`${BASE}:${srv.port}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return { status: res.status, body: await res.json() };
}

/** 服务端共享一个实例（adapter 进程 spawn 一次，测试更快） */
const srv = await startServer({ port: 0 });

test('ui/api: 健康检查（adapter 进程拉起）', async () => {
  const { status, body } = await get(srv, '/api/health');
  assert.equal(status, 200);
  assert.equal(body.ok, true);
  assert.equal(body.adapter_ready, true);
  assert.equal(body.core_api_version, '11.0');
  assert.ok(body.card_count > 14000);
});

test('ui/api: 静态文件', async () => {
  const html = await fetch(`${BASE}:${srv.port}/`);
  assert.match(await html.text(), /id="arena"/);
  const js = await fetch(`${BASE}:${srv.port}/ui.js`);
  assert.equal(js.status, 200);
  const css = await fetch(`${BASE}:${srv.port}/ui.css`);
  assert.equal(css.status, 200);
});

test('ui/api: /api/cards 精简卡表（id join + 中文字段）', async () => {
  const { body } = await get(srv, '/api/cards');
  assert.equal(body.ok, true);
  const cards = body.result;
  const reborn = cards['83764718'];
  assert.ok(reborn, '死者苏生应在精简卡表');
  assert.equal(reborn.name, '死者苏生');
  assert.equal(reborn.card_type, 'SPELL');
  assert.ok(typeof reborn.desc === 'string' && reborn.desc.length > 5);
  const dragon = cards['89631139'];
  assert.equal(dragon.name, '青眼白龙');
  assert.equal(dragon.atk, 3000);
  assert.equal(dragon.def, 2500);
  assert.deepEqual(dragon.flags, ['NORMAL']);
  assert.equal(dragon.race, '龙');
  assert.equal(dragon.level, 8);
});

test('ui/api: /api/decks 两套预设各 40 张', async () => {
  const { body } = await get(srv, '/api/decks');
  assert.equal(body.ok, true);
  const decks = body.result;
  assert.ok(decks.length >= 2);
  for (const d of decks) assert.equal(d.count, 40, `${d.file} 应为 40 张`);
});

test('ui/api: new_duel -> 初始状态（热座 viewer 跟随 + 信息隐藏）', async () => {
  const { body } = await post(srv, '/api/new_duel', {
    player_deck: 'classic-dragon.json',
    opponent_deck: 'classic-warrior.json',
  });
  assert.equal(body.ok, true, JSON.stringify(body).slice(0, 300));
  const { state, viewer, log } = body.result as ApiResult;
  assert.equal(viewer, 0);
  assert.equal(state.players[0].lp, 8000);
  assert.equal(state.players[1].lp, 8000);
  assert.equal(state.players[0].hand.length, 5);
  assert.equal(state.players[1].hand.length, 5);
  // 服务端强制 viewer=turn_player：自己手牌可见、对手手牌隐藏
  assert.ok(state.players[0].hand.every((c) => c.code !== null));
  assert.ok(state.players[1].hand.every((c) => c.code === null));
  assert.ok(state.pending !== null);
  assert.ok(log.length > 0);
});

test('ui/api: 非法 respond -> 结构化错误且服务存活', async () => {
  const bad = await post(srv, '/api/respond', { choice: 9999 });
  assert.equal(bad.body.ok, false);
  assert.equal(bad.body.error.code, 'CHOICE_INVALID');
  const st = await get(srv, '/api/state');
  assert.equal(st.body.ok, true);
});

test('ui/api: 合法 respond（结束回合）-> 状态推进', async () => {
  const { body } = await get(srv, '/api/state');
  const pending = (body.result.state as DuelState).pending!;
  const ep = pending.choices.findIndex((c) => c.kind === 'to_ep');
  assert.ok(ep >= 0, '初始 IDLE 应可结束回合');
  const res = await post(srv, '/api/respond', { choice: ep });
  assert.equal(res.body.ok, true, JSON.stringify(res.body).slice(0, 300));
  const { state, log } = res.body.result as ApiResult;
  assert.ok(state.turn_count >= 1);
  assert.ok(log.length > 0);
});

test('ui/api: /api 全链路自动完整局到胜负', async () => {
  await post(srv, '/api/new_duel', {
    player_deck: 'classic-dragon.json',
    opponent_deck: 'classic-warrior.json',
  });
  const seen = new Set<string>();
  let state: DuelState | null = (await get(srv, '/api/state')).body.result.state;
  let steps = 0;
  while (state && state.winner === null) {
    assert.ok(steps++ < 4000, '超过 4000 步未结束');
    const p = state.pending;
    assert.ok(p, '无 winner 也无 pending —— 停摆');
    seen.add(p.type);
    const choice = pickChoice(p);
    const res = await post(srv, '/api/respond', choice);
    assert.equal(res.body.ok, true,
      `respond 失败: ${JSON.stringify(res.body).slice(0, 200)}`);
    state = (res.body.result as ApiResult).state;
  }
  assert.ok(state!.winner !== null, '应打完整局');
  assert.ok(seen.has('IDLE'), `应出现 IDLE（实际 ${[...seen]}）`);
  assert.ok(seen.has('SELECT_BATTLE'), `应出现 SELECT_BATTLE（实际 ${[...seen]}）`);
  assert.ok(seen.has('SELECT_CARD'), `应出现 SELECT_CARD（苏生/增援等目标选择，实际 ${[...seen]}）`);
  // 终局视角隐藏（K3/K6）：非视角方（对手）的盖卡不得带 code
  const vp = state!.pending ? state!.pending.player : state!.turn_player;
  const oppSide = state!.players[1 - vp];
  for (const zone of ['monster_zones', 'spell_trap_zones'] as const) {
    for (const slot of oppSide[zone]) {
      if (slot !== null && slot.face === false) {
        assert.equal(slot.code, null, '对手盖卡在终局状态里也不得泄漏 code');
      }
    }
  }
});

test('ui/api: 未知 API -> 结构化 NOT_FOUND', async () => {
  const res = await get(srv, '/api/nothing');
  assert.equal(res.body.ok, false);
  assert.equal(res.body.error.code, 'NOT_FOUND');
});

test('ui/api: 服务关闭 -> adapter 子进程被回收', async (t) => {
  const proc = (srv.adapter as unknown as { proc: ChildProcess | null }).proc;
  assert.ok(proc, 'adapter 子进程应存在');
  const exited = new Promise<number | null>((res) => {
    if (proc.exitCode !== null) return res(proc.exitCode);
    proc.once('exit', (code) => res(code));
  });
  await srv.close();
  const code = await exited;
  assert.equal(code, 0, 'stdin EOF 后 python 应干净退出（exit 0）');
});

/** 与 selftest/集成测试同构的确定性应答策略（p0 进取 / p1 消极） */
function pickChoice(p: NonNullable<DuelState['pending']>):
  { choice?: number | number[]; cancel?: boolean } {
  const idx = (kind: string): number =>
    p.choices.findIndex((c) => c.kind === kind);
  const aggressive = p.player === 0;
  if (p.type === 'IDLE') {
    if (aggressive) {
      for (const kind of ['activate', 'summon', 'to_bp'] as const) {
        const i = idx(kind);
        if (i >= 0) return { choice: i };
      }
    } else {
      const ss = idx('sset');
      if (ss >= 0) return { choice: ss };
      const ms = idx('mset');
      if (ms >= 0) return { choice: ms };
    }
    const ep = idx('to_ep');
    return { choice: ep >= 0 ? ep : p.choices.length - 1 };
  }
  if (p.type === 'SELECT_BATTLE') {
    if (aggressive) {
      for (const kind of ['attack', 'to_m2'] as const) {
        const i = idx(kind);
        if (i >= 0) return { choice: i };
      }
    }
    const ep = idx('to_ep');
    return { choice: ep >= 0 ? ep : p.choices.length - 1 };
  }
  if (p.type === 'SELECT_CHAIN') {
    // 可取消一律不连锁；强制连锁（forced，不可取消）只能选链上效果
    return p.cancelable ? { cancel: true } : { choice: 0 };
  }
  if (p.type === 'EFFECT_YESNO') return { choice: aggressive ? 0 : 1 };
  if (p.type === 'SELECT_YESNO') return { choice: 1 };
  if (p.type === 'SELECT_CARD') {
    if (p.cancelable && (p.min ?? 0) === 0) return { cancel: true };
    return { choice: Array.from({ length: Math.min(p.min ?? 0, p.choices.length) },
                                 (_, i) => i) };
  }
  if (p.type === 'SELECT_PLACE') return { choice: 0 };
  if (p.type === 'SELECT_POSITION') {
    const i = p.choices.findIndex((c) => c.pos === 'faceup_attack');
    return { choice: i >= 0 ? i : 0 };
  }
  if (p.type === 'SELECT_OPTION') return { choice: 0 };
  if (p.cancelable) return { cancel: true };
  throw new Error(`策略未覆盖: ${p.type}`);
}
