/**
 * 对局状态。纯 JSON 结构（无类实例、无函数），可 structuredClone 供 AI 搜索推演。
 */
import type { CardDef, CardInstance } from './card.ts';
import type { GameRulesConfig } from './config.ts';
import type { PlayerIndex } from './zones.ts';

export type Phase =
  | 'DRAW'
  | 'STANDBY'
  | 'MAIN1'
  | 'BATTLE'
  | 'MAIN2'
  | 'END';

export interface PlayerState {
  lp: number;
  /** 卡组（顶在数组末尾，draw 即 pop） */
  deck: CardInstance[];
  hand: CardInstance[];
  monsterZones: (CardInstance | null)[];
  spellTrapZones: (CardInstance | null)[];
  fieldZone: CardInstance | null;
  graveyard: CardInstance[];
  banished: CardInstance[];
  extraDeck: CardInstance[];
  /** 本回合已用通常召唤（含盖放、祭品召唤） */
  normalSummonUsed: boolean;
  /** 本回合特殊召唤次数（Classic 上限用） */
  specialSummonsThisTurn: number;
}

export interface GameState {
  players: [PlayerState, PlayerState];
  turnPlayer: PlayerIndex;
  /** 全局回合数，从 1 开始；1 = 先攻第一回合 */
  turnCount: number;
  phase: Phase;
  rules: GameRulesConfig;
  /** uid 分配器 */
  nextUid: number;
  /** 对局是否已结束及原因 */
  winner: PlayerIndex | null;
  endReason: string | null;
  /** 结束阶段弃牌前的等待标记（手牌 > 上限） */
  pendingHandLimit: boolean;
}

export function opponentOf(p: PlayerIndex): PlayerIndex {
  return p === 0 ? 1 : 0;
}

export function createGameState(
  deckDefs: [CardDef[], CardDef[]],
  rules: GameRulesConfig,
  firstPlayer: PlayerIndex = 0,
): GameState {
  let uid = 1;
  const buildPlayer = (defs: CardDef[]): PlayerState => {
    const deck = defs.map((d) => ({ uid: uid++, def: d }));
    return {
      lp: rules.lp,
      deck,
      hand: [],
      monsterZones: Array.from({ length: rules.monsterZones }, () => null),
      spellTrapZones: Array.from({ length: rules.spellTrapZones }, () => null),
      fieldZone: null,
      graveyard: [],
      banished: [],
      extraDeck: [],
      normalSummonUsed: false,
      specialSummonsThisTurn: 0,
    };
  };
  return {
    players: [buildPlayer(deckDefs[0]), buildPlayer(deckDefs[1])],
    turnPlayer: firstPlayer,
    turnCount: 1,
    phase: 'MAIN1',
    rules,
    nextUid: uid,
    winner: null,
    endReason: null,
    pendingHandLimit: false,
  };
}
