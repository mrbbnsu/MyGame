/**
 * 游戏规则配置（Game Rules Configuration）。
 * 项目自定规则（如 Classic 特殊召唤上限）只放这里，不进卡牌效果、不硬编码在引擎。
 */
export interface GameRulesConfig {
  /** 初始 LP */
  lp: number;
  /** 先攻第一回合是否抽牌（本项目已固定：不抽） */
  firstTurnDraw: boolean;
  /** Classic Mode 每回合特殊召唤上限；Original Mode = Infinity */
  specialSummonLimit: number | null;
  /** 结束阶段手牌上限 */
  handLimit: number;
  /** 主卡组张数范围（Free Duel 用；Test Mode / 测试可放宽） */
  mainDeckMin: number;
  mainDeckMax: number;
  extraDeckMax: number;
  monsterZones: number;
  spellTrapZones: number;
}

export const CLASSIC_RULES: GameRulesConfig = {
  lp: 8000,
  firstTurnDraw: false,
  specialSummonLimit: 3,
  handLimit: 6,
  mainDeckMin: 40,
  mainDeckMax: 60,
  extraDeckMax: 15,
  monsterZones: 5,
  spellTrapZones: 5,
};

export const ORIGINAL_RULES: GameRulesConfig = {
  ...CLASSIC_RULES,
  specialSummonLimit: null,
};
