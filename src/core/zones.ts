/**
 * 区域定义（任务书 §14）。所有移动必须经 engine/move.ts 的 moveCard，禁止直接改数组。
 */
export type ZoneKind =
  | 'DECK'
  | 'HAND'
  | 'MONSTER'
  | 'SPELL_TRAP'
  | 'FIELD'
  | 'GRAVEYARD'
  | 'BANISHED'
  | 'EXTRA';

export type PlayerIndex = 0 | 1;

export interface ZoneRef {
  player: PlayerIndex;
  kind: ZoneKind;
  /** 槽位区（MONSTER / SPELL_TRAP）的格子下标；列表区省略 */
  index?: number;
}

export function zoneName(ref: ZoneRef): string {
  const p = ref.player === 0 ? 'P1' : 'P2';
  return ref.index != null ? `${p}.${ref.kind}[${ref.index}]` : `${p}.${ref.kind}`;
}
