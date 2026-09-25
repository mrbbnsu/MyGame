/**
 * E1/WO-007：Classic Duel Adapter 协议 TS 类型（与 adapter/protocol.md 逐条对应）。
 *
 * 红线（K2/K3/K4）：类型只描述 passcode 与规则语义；无文本/图片字段；
 * TS 侧零二进制解析——所有字节级知识都在 Python 服务（adapter/decoder.py）。
 * `code: null` = 该视角不可见（对手手牌/背面卡），数量信息始终保留。
 */

/** 表示形式（C API POS_*；"facedown" = 盖放未定向） */
export type CardPos =
  | 'faceup_attack'
  | 'facedown_attack'
  | 'faceup_defense'
  | 'facedown_defense'
  | 'facedown'
  | 'faceup';

/** 场上/墓地/除外的卡位（code 视视角而定） */
export interface ZoneCard {
  /** passcode；该视角不可见时为 null */
  code: number | null;
  pos: CardPos | null;
  /** 是否表侧 */
  face: boolean | null;
  /** 表侧时的当前攻击力（规则语义，可能已被效果改变）；仅怪兽区 */
  atk?: number;
  /** 表侧时的当前守备力；仅怪兽区 */
  def?: number;
  /** 本回合已宣言攻击；仅怪兽区 */
  has_attacked?: boolean;
}

export interface PlayerState {
  lp: number;
  deck_count: number;
  /** 手牌：viewer 本人可见 code，对手视角全 null；数组长度 = 手牌数 */
  hand: { code: number | null }[];
  /** 怪兽区，下标 = seq；空槽 null（v0 按 core 布局 7 槽） */
  monster_zones: (ZoneCard | null)[];
  /** 魔法陷阱区，下标 = seq；空槽 null（v0 按 core 布局 8 槽） */
  spell_trap_zones: (ZoneCard | null)[];
  /** 墓地（公开区，code 可见），seq 顺序 */
  graveyard: ZoneCard[];
  /** 除外（公开区；里侧除外的卡 code 为 null） */
  banished: ZoneCard[];
  extra_count: number;
}

/** 区域选择（SELECT_PLACE 的一个可选位置） */
export interface ZonePick {
  kind: 'place';
  zone: 'monster' | 'spell_trap';
  seq: number;
  /** 位置归属的玩家（SELECT_DISFIELD 时可为对方） */
  owner: 0 | 1;
  /** core 应答所需的原始定位（协议保留字段，客户端只读） */
  pick: { player: number; loc: number; seq: number };
}

export interface PendingChoice {
  kind:
    | 'summon' | 'spsummon' | 'reposition' | 'mset' | 'sset' | 'activate'
    | 'attack' | 'chain' | 'shuffle' | 'to_bp' | 'to_ep' | 'to_m2'
    | 'position' | 'place' | 'accept' | 'decline' | 'option';
  /** 动作针对的卡（视角过滤后的引用） */
  card?: CardRef | null;
  attacker?: CardRef | null;
  desc?: number;
  direct?: boolean;
  pos?: CardPos;
  zone?: 'monster' | 'spell_trap';
  seq?: number;
  owner?: 0 | 1;
  index?: number;
  pick?: ZonePick['pick'];
}

/** 卡引用（code 视视角而定） */
export interface CardRef {
  code: number | null;
  con: number;
  loc: number;
  seq: number;
  pos?: number;
}

export type PendingType =
  | 'IDLE' | 'SELECT_BATTLE' | 'SELECT_CHAIN' | 'EFFECT_YESNO'
  | 'SELECT_YESNO' | 'SELECT_OPTION' | 'SELECT_CARD' | 'SELECT_PLACE'
  | 'SELECT_POSITION' | 'SELECT_OTHER';

/** 当前等待应答的选择；state.pending 为 null 表示无需输入 */
export interface Pending {
  type: PendingType;
  /** 应由该玩家应答（v0 单客户端驱动双方；UI 用它切操作权） */
  player: 0 | 1;
  /** 提示文本的效果描述 id（数值；中文文本由 TS 侧按 id join 卡库） */
  prompt: number | null;
  cancelable: boolean;
  choices: PendingChoice[];
  /* ---- 类型附加字段 ---- */
  min?: number;
  max?: number;
  tribute?: boolean;
  count?: number;
  disfield?: boolean;
  forced?: boolean;
  card?: CardRef | null;
  desc?: number;
  /** SELECT_OTHER：原始消息名与解码参数（回退诊断用） */
  msg?: string;
  params?: Record<string, unknown>;
}

/** 对局状态快照（get_state / new_duel / respond 的 state 字段） */
export interface DuelState {
  duel_id: number;
  turn_player: 0 | 1;
  turn_count: number;
  /** 当前阶段名：DRAW/STANDBY/MAIN1/BATTLE_START/BATTLE_STEP/DAMAGE/DAMAGE_CAL/BATTLE/MAIN2/END */
  phase: string | null;
  /** 胜者；null = 对局进行中；2 = 平局 */
  winner: 0 | 1 | 2 | null;
  /** 胜利原因码（1=LP归零 2=卡组抽尽 0=认输）；null = 未分胜负 */
  reason: number | null;
  protocol_version: number;
  players: [PlayerState, PlayerState];
  pending: Pending | null;
}

/** 事件 = core 消息解码后的结构化记录（SELECT_* 不进事件，归一化进 pending） */
export interface AdapterEvent {
  type: string;
  enum?: number;
  [field: string]: unknown;
}

/** 请求（new_duel） */
export interface NewDuelOptions {
  lp?: number;
  start_hand?: number;
  /** 1~4 个 u64；同 seed + 同应答序列 => 事件流逐字节一致 */
  seed?: number[];
  /** 规则时代预设：default / MR1 / MR2 / MR3 / MR4 / MR5 / GOAT */
  mode?: string;
}

export interface NewDuelRequest {
  id: number | string;
  cmd: 'new_duel';
  decks: [number[], number[]];
  opts?: NewDuelOptions;
  /** 提供时 state/events 按该视角隐藏；省略 = 全可见（驱动/测试模式） */
  viewer?: 0 | 1 | null;
}

export interface GetStateRequest {
  id: number | string;
  cmd: 'get_state';
  viewer?: 0 | 1 | null;
}

export interface RespondRequest {
  id: number | string;
  cmd: 'respond';
  /** pending.choices 下标（SELECT_CARD/PLACE 可为数组） */
  choice?: number | number[];
  /** 取消（仅 cancelable 的 pending） */
  cancel?: boolean;
  viewer?: 0 | 1 | null;
}

export type AdapterRequest =
  | NewDuelRequest | GetStateRequest | RespondRequest;

export interface AdapterErrorBody {
  code: string;
  message: string;
}

export interface NewDuelResult {
  duel_id: number;
  state: DuelState;
  events: AdapterEvent[];
}

export interface RespondResult {
  state: DuelState;
  events: AdapterEvent[];
}

export interface GetStateResult {
  state: DuelState;
}

export type AdapterResult = NewDuelResult | GetStateResult | RespondResult;

/** 统一响应 */
export interface AdapterResponse<T = AdapterResult> {
  id: number | string | null;
  ok: boolean;
  result?: T;
  error?: AdapterErrorBody;
  /** 服务启动失败时的致命错误行 */
  fatal?: boolean;
}

/** 服务启动时的 ready 行 */
export interface ReadyLine {
  id: null;
  ok: true;
  result: {
    ready: true;
    service_version: string;
    protocol_version: number;
    core_api_version: string;
  };
}
