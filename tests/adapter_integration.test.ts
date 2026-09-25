/**
 * E1/WO-007 集成测试：spawn 真实 Adapter 服务（Python 子进程）跑协议全链路。
 *
 * 覆盖（工单 §5 验收 2/3/4 + 1 的 npm 半边）：
 *   - spawn 服务 -> new_duel（普通怪 + 效果卡）-> 自动应答完整局 -> winner/reason
 *   - 信息隐藏：viewer 视角下对手手牌/盖卡 code=null
 *   - 确定性：同 seed + 同应答脚本 -> 两局事件流逐字节一致
 * 运行：npm test（node --test）
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AdapterClient, AdapterClientError } from '../src/adapter/client.ts';
import type {
  AdapterEvent,
  DuelState,
  Pending,
} from '../src/adapter/types.ts';

// 与 adapter/selftest.py 相同的卡组口径：普通怪为主 + 效果卡
// （强欲之壶 55144522 / 死者苏生 83764718 / 圣防 44095762）
const VANILLA = [14575467, 47226949, 43096270];
const POT = 55144522, REBORN = 83764718, MIRROR_FORCE = 44095762;
const SEED = [0x20260925, 1, 2, 3];

function makeDeck(): number[] {
  const deck: number[] = [];
  for (let i = 0; i < 9; i++) deck.push(...VANILLA);
  deck.push(POT, POT, POT, POT, REBORN, REBORN, REBORN, REBORN,
            MIRROR_FORCE, MIRROR_FORCE, MIRROR_FORCE);
  return deck.slice(0, 40);
}

function canon(v: unknown): string {
  return JSON.stringify(v);
}

/** 确定性自动应答策略（与 selftest.Policy 同构：纯 pending 驱动） */
class Policy {
  private ssetP1 = true;

  respond(state: DuelState): { choice?: number | number[]; cancel?: boolean } {
    const p = state.pending;
    if (p === null) throw new Error('无 pending 却要求应答');
    const aggressive = p.player === 0;
    if (p.type === 'IDLE') {
      const idx = (kind: string): number =>
        p.choices.findIndex((c) => c.kind === kind);
      if (aggressive) {
        for (const kind of ['activate', 'summon', 'to_bp'] as const) {
          const i = idx(kind);
          if (i >= 0) return { choice: i };
        }
      } else {
        if (this.ssetP1) {
          const ss = idx('sset');
          if (ss >= 0) {
            this.ssetP1 = false;
            return { choice: ss };
          }
        }
        const ms = idx('mset');
        if (ms >= 0) return { choice: ms };
      }
      const ep = idx('to_ep');
      return { choice: ep >= 0 ? ep : p.choices.length - 1 };
    }
    if (p.type === 'SELECT_BATTLE') {
      const idx = (kind: string): number =>
        p.choices.findIndex((c) => c.kind === kind);
      if (aggressive) {
        for (const kind of ['attack', 'to_m2'] as const) {
          const i = idx(kind);
          if (i >= 0) return { choice: i };
        }
      }
      const ep = idx('to_ep');
      return { choice: ep >= 0 ? ep : p.choices.length - 1 };
    }
    if (p.type === 'SELECT_CHAIN') return { cancel: true };
    if (p.type === 'EFFECT_YESNO') return { choice: aggressive ? 0 : 1 };
    if (p.type === 'SELECT_YESNO') return { choice: 1 };
    if (p.type === 'SELECT_CARD') {
      if (p.cancelable && (p.min ?? 0) === 0) return { cancel: true };
      return { choice: Array.from({ length: Math.min(p.min ?? 0, p.choices.length) }, (_, i) => i) };
    }
    if (p.type === 'SELECT_PLACE') return { choice: 0 };
    if (p.type === 'SELECT_POSITION') {
      const i = p.choices.findIndex((c) => c.pos === 'faceup_attack');
      return { choice: i >= 0 ? i : 0 };
    }
    if (p.type === 'SELECT_OPTION') return { choice: 0 };
    throw new Error(`策略未覆盖的 pending 类型: ${p.type}`);
  }
}

/** spawn 一个服务并注册清理 */
function makeClient(t: TestContext): AdapterClient {
  const client = new AdapterClient();
  t.after(() => client.close());
  return client;
}

/** 自动应答打完整局，返回事件全集 */
async function playFullGame(
  client: AdapterClient,
): Promise<{ events: AdapterEvent[]; final: DuelState; steps: number }> {
  const started = await client.newDuel({
    decks: [makeDeck(), makeDeck()],
    opts: { lp: 8000, start_hand: 5, seed: SEED },
  });
  const events: AdapterEvent[] = [...started.events];
  const policy = new Policy();
  let state = started.state;
  let steps = 0;
  while (state.winner === null) {
    assert.ok(steps < 4000, '超过 4000 步未结束');
    const p: Pending | null = state.pending;
    assert.ok(p !== null, '无 winner 但也无 pending —— 驱动停摆');
    const body = policy.respond(state);
    const res = await client.respond({ ...body });
    events.push(...res.events);
    state = res.state;
    steps++;
  }
  return { events, final: state, steps };
}

test('adapter: 服务就绪握手', async (t) => {
  const client = makeClient(t);
  const ready = await client.ensureReady();
  assert.equal(ready.ready, true);
  assert.equal(ready.core_api_version, '11.0');
});

test('adapter: 完整局 —— new_duel(普通怪+效果卡) 自动应答到 winner/reason', async (t) => {
  const client = makeClient(t);
  const { events, final, steps } = await playFullGame(client);
  assert.equal(final.winner, 0, `预期 p0 胜，实际 winner=${final.winner}`);
  assert.equal(final.reason, 1, 'reason=1（LP 归零）');
  assert.equal(final.players[1].lp, 0, '败方 LP 归零');
  assert.ok(final.turn_count >= 3, `回合数 ${final.turn_count} >= 3`);
  assert.ok(events.length > 50, '事件流非空');
  // 全程无 RETRY / 无解码失败
  const bad = events.filter((e) =>
    ['RETRY', 'DECODE_ERROR', 'UNKNOWN'].includes(e.type));
  assert.deepEqual(bad, [], `不应出现异常事件: ${JSON.stringify(bad.slice(0, 3))}`);
  // 效果卡与召唤/战斗都发生过
  assert.ok(events.some((e) => e.type === 'SPSUMMONING' || e.type === 'SUMMONING'));
  assert.ok(events.some((e) => e.type === 'ATTACK'));
  assert.ok(events.some((e) => e.type === 'CHAINING' || e.type === 'DRAW'),
    '应有效果卡发动或抽牌事件');
  assert.ok(steps > 10);
  // 终局后 respond -> 结构化错误
  await assert.rejects(
    client.respond({ choice: 0 }),
    (e: AdapterClientError) => e.code === 'DUEL_OVER');
});

test('adapter: 信息隐藏 —— 对手手牌 code=null、数量保留；盖卡 code=null', async (t) => {
  const client = makeClient(t);
  const started = await client.newDuel({
    decks: [makeDeck(), makeDeck()],
    opts: { lp: 8000, start_hand: 5, seed: SEED },
  });
  assert.equal(started.state.duel_id, 1);

  const st0 = (await client.getState({ viewer: 0 })).state;
  const st1 = (await client.getState({ viewer: 1 })).state;

  // viewer=0：自己手牌可见，p1 手牌全 null 且长度保留（工单验收 3）
  assert.ok(st0.players[0].hand.every((c) => c.code !== null));
  assert.equal(st0.players[1].hand.length, 5);
  assert.ok(st0.players[1].hand.every((c) => c.code === null),
    'p1 手牌对 viewer=0 应全为 null');
  // 镜像方向
  assert.ok(st1.players[0].hand.every((c) => c.code === null));
  assert.ok(st1.players[1].hand.every((c) => c.code !== null));
  // 公开区双方一致
  assert.deepEqual(st0.players[0].graveyard, st1.players[0].graveyard);

  // 驱动到 p1 首回合结束（含盖卡），验证对手视角盖卡隐藏
  const policy = new Policy();
  let state = started.state;
  let drawEvents: AdapterEvent[] = [];
  for (let i = 0; i < 60 && state.winner === null; i++) {
    if (state.turn_count >= 3) break;
    if (state.pending === null) break;
    const body = policy.respond(state);
    const res = await client.respond({ ...body, viewer: 0 });
    drawEvents.push(...res.events);
    state = res.state;
  }
  // 事件流同样不泄漏：p1 抽牌事件对 viewer=0 无 code
  const p1Draws = drawEvents.filter((e) => e.type === 'DRAW' && e.player === 1);
  assert.ok(p1Draws.length > 0, '驱动过程应包含 p1 抽牌事件');
  for (const d of p1Draws) {
    const cards = d.cards as { code: number | null }[];
    assert.ok(cards.every((c) => c.code === null),
      'p1 抽牌事件对 viewer=0 应隐藏 code');
  }
  // p1 的盖卡（策略保证至少 1 张）对 viewer=0 全隐藏
  const facedowns: { code: number | null; face: boolean | null }[] = [];
  for (const zone of ['monster_zones', 'spell_trap_zones'] as const) {
    for (const slot of state.players[1][zone]) {
      if (slot !== null && slot.face === false) facedowns.push(slot);
    }
  }
  assert.ok(facedowns.length > 0, 'p1 首回合应已盖卡');
  assert.ok(facedowns.every((c) => c.code === null),
    `p1 盖卡对 viewer=0 应 code=null: ${JSON.stringify(facedowns)}`);
});

test('adapter: 确定性 —— 同 seed 同应答脚本事件流逐字节一致', async (t) => {
  const a = makeClient(t);
  const b = makeClient(t);
  const gameA = await playFullGame(a);
  const gameB = await playFullGame(b);
  const streamA = canon(gameA.events);
  const streamB = canon(gameB.events);
  assert.equal(streamA.length, streamB.length);
  assert.ok(streamA === streamB,
    `事件流不一致 @ ${firstDiff(streamA, streamB)}`);
  // 终局状态（剔除 duel_id 序号）也应一致
  const strip = (s: DuelState): unknown => {
    const { duel_id, ...rest } = s;
    return rest;
  };
  assert.deepEqual(strip(gameA.final), strip(gameB.final));
});

test('adapter: 非法请求返回结构化错误且服务存活', async (t) => {
  const client = makeClient(t);
  await client.ensureReady();
  await assert.rejects(
    client.newDuel({ decks: [[], makeDeck()] }),
    (e: AdapterClientError) => e.code === 'BAD_REQUEST');
  await assert.rejects(
    client.getState({}), // 未 new_duel
    (e: AdapterClientError) => e.code === 'NO_DUEL');
  // 服务仍然存活可用
  const started = await client.newDuel({
    decks: [makeDeck(), makeDeck()],
    opts: { seed: SEED },
  });
  assert.equal(started.state.winner, null);
});

function firstDiff(a: string, b: string): string {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i] !== b[i]) return `偏移 ${i}: ...${a.slice(Math.max(0, i - 40), i + 40)}...`;
  }
  return `长度不同 ${a.length}/${b.length}`;
}
