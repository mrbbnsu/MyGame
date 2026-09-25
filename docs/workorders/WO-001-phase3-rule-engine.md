# WO-001：Phase 3 最小 Rule Engine（TS）+ 规则测试套件

> 优先级：🔴 关键路径（Phase 4/5/6/7 全部依赖本工单）
> 依赖：Phase 0 已完成（骨架存在，见下）
> 工作量预估：引擎 6 个文件 + 测试 4 个文件
> 本工单自包含：不需要会话上下文，所有规则以本文与引用文档为准。

## 0. 必读材料（按序）

1. `docs/v1-rules.md` —— **冻结版规则基准**，实现以它为准；发现本文与它冲突时以它为准并在完成说明里记录
2. `docs/TASKS.md` —— 项目阶段全景与架构要求
3. `src/core/*.ts` —— **已定型的状态模型（固定基础，禁止重写，可增量扩展）**：
   - `config.ts`（GameRulesConfig / CLASSIC_RULES）、`log.ts`（LOG）、`rng.ts`（makeRng）
   - `card.ts`（CardDef / CardInstance / FacePosition / tributeCount）
   - `zones.ts`（ZoneKind / ZoneRef）、`state.ts`（GameState / PlayerState / Phase / createGameState）
4. `tests/phase0_smoke.test.ts` —— 测试写法样例（node:test + assert/strict）
5. 运行环境：Node ≥ 24，`npm test`（= `node --test`，递归发现 `*.test.ts`）。**零 npm 依赖，禁止引入任何第三方包**；TS 须为可擦除语法（不用 enum/namespace/参数属性）。

## 1. 目标

只用**普通怪兽**（无效果、无魔法陷阱），双方从 8000 LP 开始，脚本驱动即可完整打完一局并正确判胜。这是任务书第一里程碑的地基。

## 2. 交付物（文件清单）

```
src/engine/
  move.ts      统一区域移动 API（一切卡牌移动的唯一入口）
  turn.ts      回合/阶段机（一切阶段转换的唯一入口）
  battle.ts    统一战斗解算器（一切战斗伤害/破坏的唯一入口）
  actions.ts   GameAction 数据类型 + isLegalAction + legalActions
  apply.ts     applyAction（校验 + 执行）
  index.ts     createDuel 对局门面
tests/
  engine_summon.test.ts
  engine_battle.test.ts
  engine_turn.test.ts
  engine_full_game.test.ts   （用真实卡库数据打完整局）
```

## 3. 接口契约（必须一字不差地满足，Phase 6 AI 与 UI 将直接消费）

```ts
// index.ts
createDuel(opts: {
  deckDefs: [CardDef[], CardDef[]];   // 两副卡组定义（允许同名×3）
  rules?: GameRulesConfig;            // 缺省 CLASSIC_RULES
  seed?: number;                      // 缺省 20260925，洗牌用
  firstPlayer?: 0 | 1;                // 缺省 0
}): {
  state: GameState;                   // 唯一状态源，纯 JSON（structuredClone 可复制）
  legalActions(): GameAction[];       // 当前全部合法动作；对局结束返回 []
  apply(action: GameAction): void;    // 非法动作必须 throw（禁止静默忽略）
  readonly over: boolean;             // state.winner !== null
}
```

```ts
// actions.ts —— 动作是纯数据（能 JSON.stringify 比较）
type GameAction =
  | { type: 'NORMAL_SUMMON'; uid: number; position: 'FACE_UP_ATTACK'|'FACE_UP_DEFENSE'|'FACE_DOWN_DEFENSE'; tributes: number[] }
  | { type: 'FLIP_SUMMON'; uid: number }
  | { type: 'CHANGE_POSITION'; uid: number }
  | { type: 'ATTACK'; attackerUid: number; targetUid: number | null }  // null = 直接攻击
  | { type: 'ENTER_BATTLE' }
  | { type: 'ADVANCE_PHASE' }   // MAIN1→MAIN2 / BATTLE→MAIN2 / MAIN2→END→下回合
  | { type: 'DISCARD'; uid: number };  // 仅结束阶段手牌超限时出现
```

不可协商的四条架构红线（任务书 §14/§20/§21）：
1. **一切卡牌移动**（抽/召唤/祭品/破坏/弃牌）只经 `moveCard(state, uid, from: ZoneRef, to: ZoneRef)`，其余代码不得直接增删任何区域数组
2. **一切战斗伤害与破坏**只经 `resolveAttack(state, attackerUid, targetUid|null, opts?)`
3. **一切 LP 变化**只经 `changeLp(state, playerIdx, delta)`；LP≤0 或抽空卡组时立即写入 `state.winner` + `state.endReason`
4. **applyAction 先校验 isLegalAction，非法即 throw** —— AI/输入层只从 legalActions() 列表里选，从架构上杜绝作弊与非法操作

## 4. 规则细节（v1-rules.md 之外，PM 已补充拍板的决定）

| # | 决定 |
|---|---|
| D1 | 阶段流：`startTurnSequence` 内自动走 DRAW→STANDBY→MAIN1（Phase 3 无准备阶段效果，两个阶段瞬时经过即可，Phase 枚举必须保留） |
| D2 | 先攻第一回合：不抽牌（`firstTurnDraw=false`）且不能进入战斗阶段（`turnCount===1` 时 ENTER_BATTLE 不合法） |
| D3 | 通常召唤三种落场：正面攻击 / **正面防守（本项目特有，v1-rules §4）** / 背面防守（=盖放）；每回合共 1 次，祭品召唤也占用 |
| D4 | 祭品数用 `tributeCount(level)`（src/core 已给）：Lv5-6→1、Lv7+→2；祭品可以是自己的任意怪兽（含盖放） |
| D5 | 反转召唤与表示变更：召唤/盖放当回合不可；每回合每只 1 次；攻击过的怪兽当回合不可变更表示 |
| D6 | 防守表示怪兽不能攻击宣言；攻击宣言要求正面攻击表示且本回合未攻击 |
| D7 | 直接攻击条件：对方怪兽区全空（含盖放怪也算占用） |
| D8 | ATKvsATK：高者破坏低者并造成差值伤害；相同则同时破坏、无伤害 |
| D9 | ATKvsDEF：ATK>DEF 破坏无伤害；ATK<DEF 攻击方受差值伤害；相等无事 |
| D10 | 盖放怪兽被攻击：先翻成正面防守（Phase 4 起此处将触发 ON_FLIP，现在只翻），再按 D9 结算 |
| D11 | `resolveAttack` 预留 `opts.pierce`（贯穿：破坏守备怪时超出 DEF 部分作伤害），默认 false，有独立测试 |
| D12 | 手牌上限：MAIN2 推进到 END 时若手牌 > `rules.handLimit`(6)，置 `state.pendingHandLimit=true`，此状态下 legalActions 只剩 DISCARD，弃到 ≤6 后自动进入下一回合 |
| D13 | 起手各 5 张（createDuel 内完成，先手不因 firstTurnDraw 少拿起手）；卡组顶 = deck 数组末尾（`pop()` 即抽） |
| D14 | 胜负只有两种：LP 归零 / 抽牌时卡组为空；`state.winner`/`state.endReason` 写入后 legalActions 必须返回 [] |
| D15 | `specialSummonsThisTurn` 计数器与 `rules.specialSummonLimit` 本阶段只建字段不实现逻辑（Phase 4 用） |
| D16 | 怪兽离场（送墓等）时清掉 position/attackedThisTurn/positionChangedThisTurn/summonedTurn，保证未来复活语义干净 |

## 5. 明确不做（防止范围蔓延）

效果系统、魔法/陷阱、连锁、特殊召唤、Token、指示物、装备、场地、除外回收、控制权变更、AI、UI。任何"顺手实现"的魔陷字段都算违规。

## 6. 测试要求（验收=我逐条核对）

每个测试用 `node:test` 的 `test()`，命名与下表一致（验收脚本按名检查）。测试卡牌用内联合成 CardDef（id 任意、数值自定）；完整对局测试用真实库。

**engine_summon.test.ts**
- [ ] test_normal_summon_face_up_attack —— 召唤后场上 FACE_UP_ATTACK、手牌减一、normalSummonUsed
- [ ] test_normal_summon_face_up_defense —— v1 特有正面防守召唤合法
- [ ] test_set_monster_face_down_defense —— 盖放 = FACE_DOWN_DEFENSE，占用通常召唤次数
- [ ] test_one_normal_summon_per_turn —— 已召唤后，另一只 4 星的 NORMAL_SUMMON 不在 legalActions
- [ ] test_tribute_summon_lv5_needs_1 —— 场上 1 怪时 Lv5 召唤动作含 1 祭品；执行后祭品入墓
- [ ] test_tribute_summon_lv7_needs_2 —— 场上 2 怪时 Lv7 可召；场上仅 1 怪时 Lv7 无合法召唤动作
- [ ] test_tribute_insufficient_illegal —— 伪造祭品数不符的动作，apply 抛错
- [ ] test_monster_zone_full_blocks_summon —— 5 怪占满后无 NORMAL_SUMMON 动作
- [ ] test_flip_summon_not_same_turn_as_set —— 盖放当回合 FLIP_SUMMON 不合法
- [ ] test_flip_summon_next_turn_ok —— 下回合合法，执行后 FACE_UP_ATTACK
- [ ] test_change_position_rules —— 召唤回合不可变更；下回合可；变更后当回合不可再变；攻击后不可变更

**engine_battle.test.ts**
- [ ] test_attack_vs_attack_higher_wins / lower_loses / tie_both_destroyed
- [ ] test_attack_vs_defense_destroy_no_damage / lower_attacker_takes_damage / equal_nothing
- [ ] test_attack_face_down_flips_first —— 攻击盖放怪先翻正面防守再按 DEF 结算
- [ ] test_direct_attack_empty_field / test_direct_attack_blocked_with_monster
- [ ] test_monster_attacks_once_per_turn / test_defense_position_monster_cannot_attack
- [ ] test_pierce_option —— 直接调 resolveAttack 传 {pierce:true} 验证贯穿伤害

**engine_turn.test.ts**
- [ ] test_first_turn_no_draw_no_battle —— 开局 turnCount=1、phase=MAIN1、双方手牌 5/5、ENTER_BATTLE 不在动作里
- [ ] test_second_player_draws —— 轮到后手时手牌 6（抽 1）
- [ ] test_hand_limit_discard_at_end —— 用 rules={...CLASSIC_RULES, handLimit:5} 构造超限，验证 pendingHandLimit→只准 DISCARD→弃到 5 后自动下回合
- [ ] test_deck_out_loses —— 6 张卡组（5 起手+1）第 2 个自己回合抽空 → 对方胜
- [ ] test_lp_zero_loses_and_no_actions_after —— LP 归零（可用小 lp 配置）→ winner 写入、legalActions()=[]、再 apply 抛错
- [ ] test_deterministic_same_seed —— 同一 seed 两个对局，用同一动作序列驱动，状态轨迹一致

**engine_full_game.test.ts（验收核心）**
- [ ] test_full_game_with_real_db_data —— 读 `data/cards_clean.json`，筛 `flags` 含 `"NORMAL"`、atk/def 为数字、level≤4、atk≥1000 的怪兽，组成两套各 20 张卡组；用贪心策略（优先 ATTACK → 最高 ATK 召唤 → ENTER_BATTLE → ADVANCE_PHASE）驱动至终局；断言：不抛错、步数 < 2000、winner 非空

## 7. 验收流程（PM 执行）

1. `npm test` 全绿且测试名覆盖第 6 节清单（我会 diff 清单）
2. 抽查测试：故意改一个断言（如把"每回合一次召唤"放开），确认有测试变红（测试真的在测）
3. 架构红线检查：`grep -rn "monsterZones\[" src/engine/` —— 除 move.ts 外不得出现直接槽位写入；`grep -rn "lp -=" src/engine/` 应为空
4. 无卡名硬编码：`grep -rn "== *['\"].*[龙魔战]" src/` 无按名字分支的代码
5. 完成说明：附文件清单 + 相对 v1-rules/本文的任何偏离及原因

## 8. 完成定义（DoD）

全部测试绿 + PM 验收通过 + git 提交（信息：`Phase 3: 最小规则引擎 + 测试（WO-001）`）+ 在 `docs/TASKS.md` 把 Phase 3 勾为完成。
