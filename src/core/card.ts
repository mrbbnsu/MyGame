/**
 * 卡牌静态定义（CardDef）与运行时实例（CardInstance）。
 * CardDef 对应卡库数据（cards_clean.json / V1 卡池），全局按卡片密码 id 唯一；
 * CardInstance 是一场对局内的实体，同名卡三张 = 三个不同 uid。
 */

export type CardType = 'MONSTER' | 'SPELL' | 'TRAP';

/** 怪兽表示形式。V1 规则：盖放只允许背面防守（不允许盖攻击）。 */
export type FacePosition =
  | 'FACE_UP_ATTACK'
  | 'FACE_UP_DEFENSE'
  | 'FACE_DOWN_DEFENSE';

export interface CardDef {
  /** 卡片密码（与卡库主键一致） */
  id: number;
  /** 显示名（中文回退链产物） */
  name: string;
  cardType: CardType;
  /** MONSTER 专属 */
  attribute?: string | null;
  race?: string | null;
  level?: number | null;
  atk?: number | null;
  def?: number | null;
  /** 效果文本（仅展示，引擎不解析） */
  text?: string;
}

export interface CardInstance {
  uid: number;
  def: CardDef;
  /** 在怪兽区时的表示形式 */
  position?: FacePosition;
  /** 本回合被召唤/盖放（限制反转召唤与位置变更） */
  summonedTurn?: number;
  /** 本回合已攻击 */
  attackedThisTurn?: boolean;
  /** 本回合已手动变更过表示形式（含反转召唤） */
  positionChangedThisTurn?: boolean;
}

export function makeInstance(def: CardDef, uid: number): CardInstance {
  return { uid, def };
}

export function isFaceUp(pos?: FacePosition): boolean {
  return pos === 'FACE_UP_ATTACK' || pos === 'FACE_UP_DEFENSE';
}

export function currentAtk(card: CardInstance): number {
  return card.def.atk ?? 0;
}

export function currentDef(card: CardInstance): number {
  return card.def.def ?? 0;
}

/** 需要的祭品数（v1-rules §4：Lv5~6 一个，Lv7+ 两个） */
export function tributeCount(level: number | null | undefined): number {
  if (level == null) return 0;
  if (level >= 7) return 2;
  if (level >= 5) return 1;
  return 0;
}
