/**
 * createDuel 对局门面 —— Phase 6 AI 与 UI 的唯一消费入口（接口契约见 WO-001 §3）。
 */
import type { CardDef } from '../core/card.ts';
import { CLASSIC_RULES } from '../core/config.ts';
import type { GameRulesConfig } from '../core/config.ts';
import type { GameState } from '../core/state.ts';
import { createGameState } from '../core/state.ts';
import type { PlayerIndex } from '../core/zones.ts';
import { makeRng } from '../core/rng.ts';
import { applyAction } from './apply.ts';
import { legalActions } from './actions.ts';
import type { GameAction } from './actions.ts';
import { moveCard } from './move.ts';
import { drawOne } from './turn.ts';

export interface Duel {
  /** 唯一状态源，纯 JSON（structuredClone 可复制） */
  state: GameState;
  /** 当前全部合法动作；对局结束返回 [] */
  legalActions(): GameAction[];
  /** 非法动作必须 throw（禁止静默忽略） */
  apply(action: GameAction): void;
  readonly over: boolean;
}

export function createDuel(opts: {
  deckDefs: [CardDef[], CardDef[]];   // 两副卡组定义（允许同名×3）
  rules?: GameRulesConfig;            // 缺省 CLASSIC_RULES
  seed?: number;                      // 缺省 20260925，洗牌用
  firstPlayer?: 0 | 1;                // 缺省 0
}): Duel {
  const rules = opts.rules ?? CLASSIC_RULES;
  const seed = opts.seed ?? 20260925;
  const firstPlayer: PlayerIndex = opts.firstPlayer ?? 0;

  const state = createGameState(opts.deckDefs, rules, firstPlayer);
  const rng = makeRng(seed);
  rng.shuffle(state.players[0].deck);
  rng.shuffle(state.players[1].deck);

  // D13：起手各 5 张（先手不因 firstTurnDraw 少拿起手），交替抽
  for (let i = 0; i < 5; i++) {
    drawOne(state, 0);
    drawOne(state, 1);
  }
  if (rules.firstTurnDraw) drawOne(state, firstPlayer);

  return {
    state,
    legalActions: () => legalActions(state),
    apply: (action: GameAction) => applyAction(state, action),
    get over() {
      return state.winner !== null;
    },
  };
}

// 引擎公共 API 再导出，方便下游单点引入
export { applyAction } from './apply.ts';
export { isLegalAction, legalActions } from './actions.ts';
export type { GameAction } from './actions.ts';
export { changeLp, resolveAttack } from './battle.ts';
export type { AttackOpts } from './battle.ts';
export { moveCard } from './move.ts';
export { drawOne, startTurnSequence } from './turn.ts';
