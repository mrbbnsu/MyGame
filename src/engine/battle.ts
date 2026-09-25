/**
 * 统一战斗解算器（一切战斗伤害/破坏的唯一入口）与统一 LP 变化入口 changeLp。
 * 胜负只有两种：LP≤0 / 抽牌时卡组为空（D14）；归零即写 state.winner + state.endReason。
 */
import { currentAtk, currentDef } from '../core/card.ts';
import type { CardInstance } from '../core/card.ts';
import type { GameState } from '../core/state.ts';
import { opponentOf } from '../core/state.ts';
import type { PlayerIndex } from '../core/zones.ts';
import { moveCard } from './move.ts';

/** 一切 LP 变化的唯一入口（红线 3）。LP≤0 立即写入 winner + endReason。 */
export function changeLp(state: GameState, playerIdx: PlayerIndex, delta: number): void {
  const p = state.players[playerIdx];
  p.lp += delta;
  if (p.lp <= 0 && state.winner === null) {
    state.winner = opponentOf(playerIdx);
    state.endReason = 'LP_ZERO';
  }
}

export interface AttackOpts {
  /** 贯穿（D11）：破坏守备怪时超出 DEF 部分作伤害，默认 false */
  pierce?: boolean;
}

/**
 * 攻击解算：attackerUid（攻击方场上怪兽）攻向 targetUid（对方场上怪兽）或直接攻击（null）。
 * 合法性由 actions.isLegalAction 在 applyAction 前校验；此处只做防御性断言（测试也会直调）。
 */
export function resolveAttack(
  state: GameState,
  attackerUid: number,
  targetUid: number | null,
  opts: AttackOpts = {},
): void {
  if (state.winner !== null) throw new Error('对局已结束，无法战斗');
  const tp = state.turnPlayer;
  const opp: PlayerIndex = opponentOf(tp);
  const attacker = findMonster(state, tp, attackerUid);
  if (attacker.position !== 'FACE_UP_ATTACK') {
    throw new Error('只有正面攻击表示的怪兽才能攻击');
  }
  if (attacker.attackedThisTurn) {
    throw new Error('该怪兽本回合已攻击过');
  }
  attacker.attackedThisTurn = true;

  const opponent = state.players[opp];
  if (targetUid === null) {
    // D7：直接攻击要求对方怪兽区全空（含盖放怪也算占用）
    if (opponent.monsterZones.some((z) => z !== null)) {
      throw new Error('对方场上有怪兽，不能直接攻击');
    }
    changeLp(state, opp, -currentAtk(attacker));
    return;
  }

  const target = findMonster(state, opp, targetUid);
  // D10：盖放怪被攻击先翻成正面防守（Phase 3 只翻不触发效果），再按 DEF 结算
  if (target.position === 'FACE_DOWN_DEFENSE') {
    target.position = 'FACE_UP_DEFENSE';
  }
  const aAtk = currentAtk(attacker);
  if (target.position === 'FACE_UP_ATTACK') {
    // D8：ATKvsATK，高者破坏低者并造成差值伤害；相同则同时破坏、无伤害
    const tAtk = currentAtk(target);
    if (aAtk > tAtk) {
      destroy(state, opp, target);
      changeLp(state, opp, -(aAtk - tAtk));
    } else if (aAtk < tAtk) {
      destroy(state, tp, attacker);
      changeLp(state, tp, -(tAtk - aAtk));
    } else {
      destroy(state, opp, target);
      destroy(state, tp, attacker);
    }
  } else {
    // D9：ATKvsDEF
    const tDef = currentDef(target);
    if (aAtk > tDef) {
      destroy(state, opp, target);
      if (opts.pierce) changeLp(state, opp, -(aAtk - tDef));
    } else if (aAtk < tDef) {
      changeLp(state, tp, -(tDef - aAtk));
    }
    // 相等无事发生
  }
}

/** 战斗破坏：送去持有者墓地（经 moveCard，离场字段随之清空） */
function destroy(state: GameState, owner: PlayerIndex, card: CardInstance): void {
  moveCard(state, card.uid, { player: owner, kind: 'MONSTER' }, { player: owner, kind: 'GRAVEYARD' });
}

function findMonster(state: GameState, player: PlayerIndex, uid: number): CardInstance {
  const m = state.players[player].monsterZones.find((z) => z?.uid === uid);
  if (!m) throw new Error(`玩家 ${player} 场上没有 uid=${uid} 的怪兽`);
  return m;
}
