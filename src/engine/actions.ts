/**
 * GameAction 数据类型 + isLegalAction + legalActions。
 * 动作是纯数据（能 JSON.stringify 比较）；AI/输入层只允许从 legalActions() 列表里选（红线 4）。
 */
import { isFaceUp, tributeCount } from '../core/card.ts';
import type { CardInstance, FacePosition } from '../core/card.ts';
import type { GameState } from '../core/state.ts';
import { opponentOf } from '../core/state.ts';

export type GameAction =
  | { type: 'NORMAL_SUMMON'; uid: number; position: 'FACE_UP_ATTACK'|'FACE_UP_DEFENSE'|'FACE_DOWN_DEFENSE'; tributes: number[] }
  | { type: 'FLIP_SUMMON'; uid: number }
  | { type: 'CHANGE_POSITION'; uid: number }
  | { type: 'ATTACK'; attackerUid: number; targetUid: number | null }  // null = 直接攻击
  | { type: 'ENTER_BATTLE' }
  | { type: 'ADVANCE_PHASE' }   // MAIN1→MAIN2 / BATTLE→MAIN2 / MAIN2→END→下回合
  | { type: 'DISCARD'; uid: number };  // 仅结束阶段手牌超限时出现

/** 通常召唤三种落场（D3）：正面攻击 / 正面防守（v1 特有）/ 背面防守（盖放） */
export const SUMMON_POSITIONS: readonly FacePosition[] = [
  'FACE_UP_ATTACK',
  'FACE_UP_DEFENSE',
  'FACE_DOWN_DEFENSE',
];

/** 当前全部合法动作；对局结束返回 []（D14） */
export function legalActions(state: GameState): GameAction[] {
  if (state.winner !== null) return [];
  const me = state.players[state.turnPlayer];
  // D12：结束阶段手牌超限 → 只准 DISCARD，弃到上限后自动进入下一回合
  if (state.pendingHandLimit) {
    return me.hand.map((c) => ({ type: 'DISCARD', uid: c.uid }));
  }
  switch (state.phase) {
    case 'MAIN1': return [...mainPhaseActions(state, true), { type: 'ADVANCE_PHASE' }];
    case 'BATTLE': return [...battleActions(state), { type: 'ADVANCE_PHASE' }];
    case 'MAIN2': return [...mainPhaseActions(state, false), { type: 'ADVANCE_PHASE' }];
    case 'END': return [{ type: 'ADVANCE_PHASE' }];
    default: return []; // DRAW/STANDBY 瞬时经过，不作为停留阶段
  }
}

/** applyAction 前的统一校验入口：直接与 legalActions 生成的动作比对，杜绝两套判定漂移 */
export function isLegalAction(state: GameState, action: GameAction): boolean {
  return legalActions(state).some((a) => sameAction(a, action));
}

function sameAction(a: GameAction, b: GameAction): boolean {
  if (a.type !== b.type) return false;
  switch (a.type) {
    case 'NORMAL_SUMMON':
      return b.type === 'NORMAL_SUMMON'
        && a.uid === b.uid
        && a.position === b.position
        && sameTributes(a.tributes, b.tributes);
    case 'FLIP_SUMMON':
    case 'CHANGE_POSITION':
    case 'DISCARD':
      return a.uid === b.uid;
    case 'ATTACK':
      return a.attackerUid === b.attackerUid && a.targetUid === b.targetUid;
    case 'ENTER_BATTLE':
    case 'ADVANCE_PHASE':
      return true;
  }
}

/** 祭品按多重集合比较（顺序无关） */
function sameTributes(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  const sa = [...a].sort((x, y) => x - y);
  const sb = [...b].sort((x, y) => x - y);
  return sa.every((v, i) => v === sb[i]);
}

/** 主要阶段（MAIN1/MAIN2）通用动作：通常召唤 / 反转召唤 / 表示变更 /（MAIN1 限定）进入战斗 */
function mainPhaseActions(state: GameState, canEnterBattle: boolean): GameAction[] {
  const acts: GameAction[] = [];
  const me = state.players[state.turnPlayer];
  const field = myMonsters(me);
  const freeSlots = me.monsterZones.length - field.length;

  if (!me.normalSummonUsed) {
    for (const card of me.hand) {
      if (card.def.cardType !== 'MONSTER') continue;
      const need = tributeCount(card.def.level);
      if (need === 0) {
        if (freeSlots < 1) continue;
        for (const position of SUMMON_POSITIONS) {
          acts.push({ type: 'NORMAL_SUMMON', uid: card.uid, position, tributes: [] });
        }
      } else {
        // D4：祭品可以是自己的任意怪兽（含盖放）；祭品召唤占用本回合通常召唤次数
        if (field.length < need) continue;
        for (const tributes of combinations(field.map((m) => m.uid), need)) {
          for (const position of SUMMON_POSITIONS) {
            acts.push({ type: 'NORMAL_SUMMON', uid: card.uid, position, tributes });
          }
        }
      }
    }
  }

  for (const m of field) {
    // D5：反转召唤——盖放怪兽翻成正面攻击；召唤/盖放当回合不可，每回合每只 1 次
    if (
      m.position === 'FACE_DOWN_DEFENSE'
      && m.summonedTurn !== state.turnCount
      && !m.positionChangedThisTurn
    ) {
      acts.push({ type: 'FLIP_SUMMON', uid: m.uid });
    }
    // D5：表示变更——召唤回合不可、每回合每只 1 次、攻击过不可
    if (
      isFaceUp(m.position)
      && m.summonedTurn !== state.turnCount
      && !m.positionChangedThisTurn
      && !m.attackedThisTurn
    ) {
      acts.push({ type: 'CHANGE_POSITION', uid: m.uid });
    }
  }

  // D2：先攻第一回合不能进入战斗阶段
  if (canEnterBattle && state.turnCount > 1) {
    acts.push({ type: 'ENTER_BATTLE' });
  }
  return acts;
}

/** 战斗阶段动作：攻击宣言（D6：正面攻击表示且本回合未攻击；D7：直接攻击条件） */
function battleActions(state: GameState): GameAction[] {
  const acts: GameAction[] = [];
  const opp = state.players[opponentOf(state.turnPlayer)];
  const oppMonsters = opp.monsterZones.filter((z): z is CardInstance => z !== null);
  for (const m of myMonsters(state.players[state.turnPlayer])) {
    if (m.position !== 'FACE_UP_ATTACK' || m.attackedThisTurn) continue;
    if (oppMonsters.length === 0) {
      acts.push({ type: 'ATTACK', attackerUid: m.uid, targetUid: null });
    } else {
      for (const t of oppMonsters) {
        acts.push({ type: 'ATTACK', attackerUid: m.uid, targetUid: t.uid });
      }
    }
  }
  return acts;
}

function myMonsters(p: { monsterZones: (CardInstance | null)[] }): CardInstance[] {
  return p.monsterZones.filter((z): z is CardInstance => z !== null);
}

/** tributeCount 上限为 2，只需 k=1/2 的组合 */
function combinations(uids: number[], k: number): number[][] {
  const out: number[][] = [];
  if (k <= 1) {
    for (const u of uids) out.push([u]);
    return out;
  }
  for (let i = 0; i < uids.length; i++) {
    for (let j = i + 1; j < uids.length; j++) {
      out.push([uids[i]!, uids[j]!]);
    }
  }
  return out;
}
