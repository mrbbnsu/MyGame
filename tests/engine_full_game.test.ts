/**
 * 完整对局测试（工单 WO-001 §6 验收核心）：
 * 读真实卡库 data/cards_clean.json，组两套 20 张通常怪兽卡组，
 * 用贪心策略驱动至终局，断言不抛错、步数 < 2000、winner 非空。
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createDuel } from '../src/engine/index.ts';
import type { Duel } from '../src/engine/index.ts';
import type { CardDef } from '../src/core/card.ts';
import type { GameState } from '../src/core/state.ts';
import type { GameAction } from '../src/engine/actions.ts';

interface RawCard {
  id: number;
  name: string;
  card_type: string;
  flags: string[];
  level: number | null;
  atk: number | null;
  def: number | null;
}

/** 筛 flags 含 NORMAL、atk/def 为数字、level≤4、atk≥1000 的通常怪兽 */
function loadDecks(): [CardDef[], CardDef[]] {
  const raw = JSON.parse(
    readFileSync(new URL('../data/cards_clean.json', import.meta.url), 'utf8'),
  ) as RawCard[];
  const pool = raw.filter(
    (c) =>
      c.card_type === 'MONSTER'
      && Array.isArray(c.flags)
      && c.flags.includes('NORMAL')
      && typeof c.atk === 'number'
      && typeof c.def === 'number'
      && typeof c.level === 'number'
      && c.level <= 4
      && c.atk >= 1000,
  );
  assert.ok(pool.length >= 40, `可用通常怪兽不足：${pool.length}`);
  const sorted = [...pool].sort((a, b) => (b.atk ?? 0) - (a.atk ?? 0));
  const toDef = (c: RawCard): CardDef => ({
    id: c.id,
    name: c.name,
    cardType: 'MONSTER',
    level: c.level,
    atk: c.atk,
    def: c.def,
  });
  // 按 ATK 排序切两半，两套不同强度的卡组（保证对局有胜负）
  return [sorted.slice(0, 20).map(toDef), sorted.slice(20, 40).map(toDef)];
}

function monsterAt(state: GameState, player: 0 | 1, uid: number) {
  return state.players[player].monsterZones.find((z) => z?.uid === uid) ?? null;
}

/** 贪心策略：优先 ATTACK → 最高 ATK 召唤 → ENTER_BATTLE → ADVANCE_PHASE → DISCARD */
function pickGreedy(duel: Duel): GameAction {
  const state = duel.state;
  const acts = duel.legalActions();

  const attacks = acts.filter((a): a is Extract<GameAction, { type: 'ATTACK' }> => a.type === 'ATTACK');
  if (attacks.length > 0) {
    const opp = state.turnPlayer === 0 ? 1 : 0;
    let best = attacks[0]!;
    let bestScore = -Infinity;
    for (const a of attacks) {
      let s: number;
      if (a.targetUid === null) {
        s = 1_000_000; // 直接攻击最优
      } else {
        const attacker = monsterAt(state, state.turnPlayer, a.attackerUid)!;
        const target = monsterAt(state, opp, a.targetUid)!;
        const aAtk = attacker.def.atk ?? 0;
        if (target.position === 'FACE_UP_ATTACK') {
          const tAtk = target.def.atk ?? 0;
          s = aAtk > tAtk ? 4000 + tAtk : aAtk === tAtk ? 10 : -4000;
        } else if (target.position === 'FACE_UP_DEFENSE') {
          const tDef = target.def.def ?? 0;
          s = aAtk > tDef ? 3000 + tDef : aAtk === tDef ? 10 : -2000;
        } else {
          s = 20; // 盖放信息不明，保守可打
        }
      }
      if (s > bestScore) {
        bestScore = s;
        best = a;
      }
    }
    return best;
  }

  const summons = acts.filter((a): a is Extract<GameAction, { type: 'NORMAL_SUMMON' }> => a.type === 'NORMAL_SUMMON');
  if (summons.length > 0) {
    let best = summons[0]!;
    let bestScore = -Infinity;
    for (const a of summons) {
      const card = state.players[state.turnPlayer].hand.find((c) => c.uid === a.uid)!;
      const s =
        (card.def.atk ?? 0) * 100
        + (a.tributes.length === 0 ? 10 : 0)
        + (a.position === 'FACE_UP_ATTACK' ? 2 : a.position === 'FACE_UP_DEFENSE' ? 1 : 0);
      if (s > bestScore) {
        bestScore = s;
        best = a;
      }
    }
    return best;
  }

  const enter = acts.find((a) => a.type === 'ENTER_BATTLE');
  if (enter) return enter;
  const advance = acts.find((a) => a.type === 'ADVANCE_PHASE');
  if (advance) return advance;
  const discard = acts.find((a) => a.type === 'DISCARD');
  if (discard) return discard;
  throw new Error(`贪心驱动无动作可选：${JSON.stringify(acts)}`);
}

test('test_full_game_with_real_db_data', () => {
  const [deck0, deck1] = loadDecks();
  const duel = createDuel({ deckDefs: [deck0, deck1] });
  let steps = 0;
  while (!duel.over) {
    duel.apply(pickGreedy(duel)); // 非法动作会 throw → 测试失败
    steps++;
    assert.ok(steps < 2000, `步数超限：${steps}`);
  }
  assert.ok(duel.state.winner !== null, '必须分出胜负');
  assert.ok(duel.state.endReason !== null);
  assert.deepEqual(duel.legalActions(), []);
  assert.ok(steps < 2000, `步数 ${steps} < 2000`);
});
