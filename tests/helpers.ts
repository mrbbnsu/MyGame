/**
 * 引擎测试公共工具：合成卡、部署怪兽、推进回合、检索动作。
 * 白盒辅助只走公共 API（createDuel / moveCard / legalActions / apply），不直接改区域数组。
 * 本文件不是测试，node --test 不会执行它。
 */
import assert from 'node:assert/strict';
import type { CardDef, CardInstance, FacePosition } from '../src/core/card.ts';
import type { GameAction } from '../src/engine/actions.ts';
import type { Duel } from '../src/engine/index.ts';
import { moveCard } from '../src/engine/move.ts';

let nextId = 900001;

/** 合成测试卡（工单 §6：id 任意、数值自定） */
export function mk(name: string, level: number, atk: number, def: number): CardDef {
  return { id: nextId++, name, cardType: 'MONSTER', attribute: '地', race: '战士', level, atk, def, text: '' };
}

/** 把若干种卡循环填成 total 张的卡组 */
export function deckWith(cards: CardDef[], total: number): CardDef[] {
  const out: CardDef[] = [];
  for (let i = 0; out.length < total; i++) out.push(cards[i % cards.length]!);
  return out;
}

/** 在手牌或卡组里找到指定卡的实例（起手只抽走 5 张，必有剩余） */
export function getCard(duel: Duel, player: 0 | 1, defId: number): CardInstance {
  const p = duel.state.players[player];
  const c = p.hand.find((x) => x.def.id === defId) ?? p.deck.find((x) => x.def.id === defId);
  if (!c) throw new Error(`测试 setup：玩家 ${player} 的手牌/卡组里找不到 id=${defId}`);
  return c;
}

/** 把指定卡部署上场（白盒 setup，等价一次召唤但不受次数/回合限制） */
export function deploy(duel: Duel, player: 0 | 1, defId: number, position: FacePosition): CardInstance {
  const p = duel.state.players[player];
  const c = getCard(duel, player, defId);
  const from = p.hand.includes(c)
    ? ({ player, kind: 'HAND' } as const)
    : ({ player, kind: 'DECK' } as const);
  const placed = moveCard(duel.state, c.uid, from, { player, kind: 'MONSTER' });
  placed.position = position;
  return placed;
}

/** 把指定卡抽到手牌（已在手牌则原样返回） */
export function pullToHand(duel: Duel, player: 0 | 1, defId: number): CardInstance {
  const c = getCard(duel, player, defId);
  const p = duel.state.players[player];
  if (p.hand.includes(c)) return c;
  return moveCard(duel.state, c.uid, { player, kind: 'DECK' }, { player, kind: 'HAND' });
}

/** 强制从卡组再抽一张指定卡到手牌（手牌数 +1，用于构造超限场景） */
export function pullExtraToHand(duel: Duel, player: 0 | 1, defId: number): CardInstance {
  const c = duel.state.players[player].deck.find((x) => x.def.id === defId);
  if (!c) throw new Error(`测试 setup：玩家 ${player} 的卡组里找不到 id=${defId}`);
  return moveCard(duel.state, c.uid, { player, kind: 'DECK' }, { player, kind: 'HAND' });
}

/**
 * 只用 ADVANCE_PHASE / DISCARD 一路推进，停到指定玩家的下一个 MAIN1。
 * 至少执行一个动作（已经在其 MAIN1 也会先推进走完）。
 */
export function passToMain1(duel: Duel, player: 0 | 1): void {
  for (let i = 0; i < 300; i++) {
    if (duel.over) throw new Error('passToMain1：对局提前结束');
    const acts = duel.legalActions();
    const act = acts.find((a) => a.type === 'ADVANCE_PHASE') ?? acts.find((a) => a.type === 'DISCARD');
    if (!act) throw new Error(`passToMain1 卡住：${JSON.stringify(acts)}`);
    duel.apply(act);
    if (duel.state.turnPlayer === player && duel.state.phase === 'MAIN1') return;
  }
  throw new Error('passToMain1：步数超限');
}

export type SummonAction = Extract<GameAction, { type: 'NORMAL_SUMMON' }>;
export type AttackAction = Extract<GameAction, { type: 'ATTACK' }>;

export function summonActionsOf(duel: Duel, uid: number): SummonAction[] {
  return duel.legalActions().filter(
    (a): a is SummonAction => a.type === 'NORMAL_SUMMON' && a.uid === uid,
  );
}

export function attackActionsOf(duel: Duel): AttackAction[] {
  return duel.legalActions().filter((a): a is AttackAction => a.type === 'ATTACK');
}

export function assertApplyThrows(duel: Duel, action: GameAction, msg: string): void {
  assert.throws(() => duel.apply(action), Error, msg);
}
