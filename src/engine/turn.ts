/**
 * 回合/阶段机（一切阶段转换的唯一入口）。
 * startTurnSequence 内自动走 DRAW→STANDBY→MAIN1（D1，Phase 3 无准备阶段效果，瞬时经过）。
 */
import type { GameState } from '../core/state.ts';
import { opponentOf } from '../core/state.ts';
import type { PlayerIndex } from '../core/zones.ts';
import { moveCard } from './move.ts';

/** 抽 1 张（卡组顶 = deck 数组末尾）。抽牌时卡组为空 → 判该玩家负（D14）。 */
export function drawOne(state: GameState, player: PlayerIndex): void {
  const p = state.players[player];
  if (p.deck.length === 0) {
    if (state.winner === null) {
      state.winner = opponentOf(player);
      state.endReason = 'DECK_OUT';
    }
    return;
  }
  const top = p.deck[p.deck.length - 1]!;
  moveCard(state, top.uid, { player, kind: 'DECK' }, { player, kind: 'HAND' });
}

/**
 * 结束当前回合，进入对方玩家的回合并停在 MAIN1：
 * 换手 → 清每回合规限标记 → 抽牌（先攻第一回合不抽，D2）。
 */
export function startTurnSequence(state: GameState): void {
  state.turnCount += 1;
  state.turnPlayer = opponentOf(state.turnPlayer);
  state.pendingHandLimit = false;

  const p = state.players[state.turnPlayer];
  p.normalSummonUsed = false;
  p.specialSummonsThisTurn = 0;
  for (const pl of state.players) {
    for (const m of pl.monsterZones) {
      if (m) {
        m.attackedThisTurn = false;
        m.positionChangedThisTurn = false;
      }
    }
  }

  state.phase = 'DRAW';
  if (!(state.turnCount === 1 && !state.rules.firstTurnDraw)) {
    drawOne(state, state.turnPlayer);
  }
  state.phase = 'STANDBY';
  state.phase = 'MAIN1';
}
