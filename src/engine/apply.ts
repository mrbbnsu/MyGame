/**
 * applyAction：先校验 isLegalAction（非法即 throw，红线 4），再执行动作。
 * 执行层只编排：一切卡牌移动走 moveCard，一切战斗走 resolveAttack，一切 LP 变化走 changeLp。
 */
import type { CardInstance } from '../core/card.ts';
import type { GameState, PlayerState } from '../core/state.ts';
import { resolveAttack } from './battle.ts';
import { isLegalAction } from './actions.ts';
import type { GameAction } from './actions.ts';
import { moveCard } from './move.ts';
import { startTurnSequence } from './turn.ts';

export function applyAction(state: GameState, action: GameAction): void {
  if (state.winner !== null) throw new Error('对局已结束，无法执行动作');
  if (!isLegalAction(state, action)) {
    throw new Error(`非法动作：${JSON.stringify(action)}`);
  }
  const tp = state.turnPlayer;
  const me = state.players[tp];
  switch (action.type) {
    case 'NORMAL_SUMMON': {
      for (const t of action.tributes) {
        moveCard(state, t, { player: tp, kind: 'MONSTER' }, { player: tp, kind: 'GRAVEYARD' });
      }
      const card = moveCard(state, action.uid, { player: tp, kind: 'HAND' }, { player: tp, kind: 'MONSTER' });
      card.position = action.position;
      card.summonedTurn = state.turnCount;
      me.normalSummonUsed = true;
      break;
    }
    case 'FLIP_SUMMON': {
      // v1-rules §4：反转召唤 = 背面怪兽翻成正面攻击表示
      const m = monsterOf(me, action.uid);
      m.position = 'FACE_UP_ATTACK';
      m.positionChangedThisTurn = true;
      break;
    }
    case 'CHANGE_POSITION': {
      const m = monsterOf(me, action.uid);
      m.position = m.position === 'FACE_UP_ATTACK' ? 'FACE_UP_DEFENSE' : 'FACE_UP_ATTACK';
      m.positionChangedThisTurn = true;
      break;
    }
    case 'ENTER_BATTLE':
      state.phase = 'BATTLE';
      break;
    case 'ATTACK':
      resolveAttack(state, action.attackerUid, action.targetUid);
      break;
    case 'ADVANCE_PHASE':
      if (state.phase === 'MAIN1' || state.phase === 'BATTLE') {
        state.phase = 'MAIN2';
      } else if (state.phase === 'MAIN2') {
        state.phase = 'END';
        // D12：进 END 时手牌超限 → 置 pendingHandLimit，此状态下只准 DISCARD
        if (me.hand.length > state.rules.handLimit) state.pendingHandLimit = true;
      } else if (state.phase === 'END') {
        startTurnSequence(state);
      }
      break;
    case 'DISCARD': {
      moveCard(state, action.uid, { player: tp, kind: 'HAND' }, { player: tp, kind: 'GRAVEYARD' });
      if (me.hand.length <= state.rules.handLimit) {
        state.pendingHandLimit = false;
        startTurnSequence(state); // D12：弃到上限内自动进入下一回合
      }
      break;
    }
  }
}

function monsterOf(p: PlayerState, uid: number): CardInstance {
  const m = p.monsterZones.find((z) => z?.uid === uid);
  if (!m) throw new Error(`场上找不到 uid=${uid} 的怪兽`);
  return m;
}
