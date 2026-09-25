# Classic Duel Adapter 协议 v1（E1/WO-007）

> TS 侧（UI/AI）与本服务的唯一契约。与 `src/adapter/types.ts` 逐条对应；
> 类型以本文件为准，改协议必须两处同步。
> 红线：协议里只有 **passcode 与规则语义**（K2）；`code: null` = 该视角不可见（K3）；
> TS 侧零二进制解析，字节级知识只在 Python 侧 decoder.py（K4）。

## 0. 传输与帧

- 形态：独立进程（Python v0 实现），**JSON Lines over stdio**：一行一个 UTF-8 JSON，`\n` 结尾。
- 服务启动即向 stdout 写一行 ready：
  `{"id":null,"ok":true,"result":{"ready":true,"service_version":"…","protocol_version":1,"core_api_version":"11.0"}}`
  启动失败则写 `{"id":null,"ok":false,"error":{...},"fatal":true}` 后退出（exit 1）。
- 请求统一 `{id, cmd, ...}`；响应统一 `{id, ok:true, result}` 或 `{id, ok:false, error:{code,message}}`。
  响应与请求按 `id` 一一对应（客户端关联）。
- stdin EOF → 服务清理并退出（exit 0）。协议错误（坏 JSON 行等）返回结构化错误，进程不崩。
- 诊断/日志全部走服务进程 **stderr**；stdout 只承载协议行。

## 1. 命令

### new_duel
```json
{"id":1,"cmd":"new_duel",
 "decks":[[<passcode>…],[<passcode>…]],
 "opts":{"lp":8000,"start_hand":5,"seed":[u64…1~4 个],"mode":"default"},
 "viewer":0}
```
- 前置校验：decks 恰好 2 个非空数组、元素为 0~2^32-1 整数；seed 1~4 个 u64；
  mode ∈ `default|MR1|MR2|MR3|MR4|MR5|GOAT`（规则时代预设；缺省 default=现行规则）。
  **不做**卡组合法性校验（卡组系统工单的事）。
- `viewer` 可选：提供时 state/events 按该视角隐藏；省略/null = 全可见（驱动/测试模式）。
- result：`{duel_id, state, events}`。v0 单对局：再次 new_duel 销毁旧局，duel_id 递增。

### get_state
```json
{"id":2,"cmd":"get_state","viewer":0}
```
- result：`{state}`。纯读，不驱动 core，不产生事件。

### respond
```json
{"id":3,"cmd":"respond","choice":<下标|下标数组>}
{"id":3,"cmd":"respond","cancel":true}
```
- 应用选择后驱动 core 到下一个输入点（或终局）。
- result：`{state, events}`。state 内含新 `pending`；`pending:null` 且 `winner:null`
  表示无需输入（正常不会出现；出现即服务内部停摆保护）。
- 对局结束后 respond → 错误 `DUEL_OVER`。

## 2. state 结构

```jsonc
{
  "duel_id": 1,
  "turn_player": 0, "turn_count": 3,
  "phase": "MAIN1",            // DRAW/STANDBY/MAIN1/BATTLE_START/BATTLE_STEP/
                               // DAMAGE/DAMAGE_CAL/BATTLE/MAIN2/END
  "winner": null,              // null=进行中；0/1=胜者；2=平局
  "reason": null,              // 1=LP归零；2=卡组抽尽；0=认输；null=未分胜负
  "protocol_version": 1,
  "players": [
    {
      "lp": 8000,
      "deck_count": 30,
      "hand": [{"code":55144522}, {"code":null}],   // 长度=手牌数；不可见⇒null
      "monster_zones": [ null | {…卡位}, … ],        // 下标=seq，v0 按 core 布局 7 槽
      "spell_trap_zones": [ null | {…卡位}, … ],     // 下标=seq，v0 按 core 布局 8 槽
      "graveyard": [{…卡位}…],                       // 公开区
      "banished": [{…卡位}…],                        // 公开区（里侧除外⇒code null）
      "extra_count": 0
    }, …×2 ],
  "pending": null | {…见 §3}
}
```
卡位（ZoneCard）：
```jsonc
{"code":83764718|null, "pos":"faceup_attack", "face":true,
 "atk":1900, "def":null, "has_attacked":true}
```
- `pos`: `faceup_attack|facedown_attack|faceup_defense|facedown_defense|facedown|faceup`
  （`facedown`=盖放未定向）。`face`=表侧布尔。
- `atk/def` 仅怪兽区、且**该视角可见**时给出（效果改变后的当前值，规则语义）。
- `has_attacked`：本回合已宣言攻击（由 ATTACK 事件推导）。
- 区域长度按 core 实际布局 7/8 槽（工单写 [5] 的偏差，见 §6）；经典卡池下 5/6 槽恒空。

### 视角可见性规则（K3 红线）
| 位置 | 规则 |
|---|---|
| 手牌 | 仅本人可见 code，对手全 null（数量保留） |
| 卡组/额外 | 永不暴露内容（只给 count） |
| 怪兽区/魔陷区 | 己方卡（含自己盖的）可见；对方面向 code=null（面向/pos 保留） |
| 墓地/除外 | 公开；里侧除外 code=null |
| pending/events | 同规则过滤（事件流不泄漏对手抽牌/盖卡身份） |

## 3. pending（等待应答的选择）

公共字段：`{type, player, prompt, cancelable, choices, …附加}`。
`player` = 应答方（工单表没有、v0 补充：热座 UI 切操作权/AI 判断轮次必需）。
`prompt`/`desc` 是效果描述 id（数值），中文文本由 TS 侧 join 卡库获得（K2）。

| type | 来源消息 | choices 元素 | 应答 |
|---|---|---|---|
| `IDLE` | SELECT_IDLECMD | `{kind:"summon"\|"spsummon"\|"reposition"\|"mset"\|"sset",card}` `{kind:"activate",card,desc}` `{kind:"shuffle"}` `{kind:"to_bp"}` `{kind:"to_ep"}` | `choice`: choices 下标 |
| `SELECT_BATTLE` | SELECT_BATTLECMD | `{kind:"attack",attacker,direct}` `{kind:"activate",card,desc}` `{kind:"to_m2"}` `{kind:"to_ep"}` | 同上 |
| `SELECT_CHAIN` | SELECT_CHAIN | `{kind:"chain",card,desc,index}` | 下标=连锁该条；`cancel:true`=不连锁（forced 时不可取消） |
| `EFFECT_YESNO` | SELECT_EFFECTYN | `[{kind:"accept"},{kind:"decline"}]` | 0=发动 1=拒绝；附 `card,desc` |
| `SELECT_YESNO` | SELECT_YESNO | 同上 | 同上；附 `desc` |
| `SELECT_OPTION` | SELECT_OPTION | `{kind:"option",desc}…` | 下标 |
| `SELECT_CARD` | SELECT_CARD/TRIBUTE | `{card:{…}}` | `choice`: **下标数组**（min..max 张）；`min/max/tribute` 附在 pending |
| `SELECT_PLACE` | SELECT_PLACE/DISFIELD | `{kind:"place",zone,seq,owner,pick}`（flag 位=1 禁用已被剔除） | 下标或下标数组（长度=`count`） |
| `SELECT_POSITION` | SELECT_POSITION | `{kind:"position",pos}` | 下标 |
| `SELECT_OTHER` | 未覆盖类型（SELECT_SUM/ANNOUNCE_*/SORT_* 等） | `[]` | 仅 `cancel:true`（若 cancelable）；`msg/params` 保留原始解码供诊断 |

## 4. 事件（events）

core 消息按 core writer 布局解码为 `{type:<MSG名>, …字段}` 的数组，按发生顺序拼接
（new_duel 与每次 respond 的 events 相加 = 全局事件流）。要点：

- **SELECT_* 消息不进事件**——归一化为 `state.pending`；无法归一化的 SELECT_* →
  `SELECT_OTHER` pending + 一条 `{type:"UNKNOWN"}` 事件（raw_size）。
- `UNKNOWN`：95 枚举之外的消息（含 15 个 legacy 枚举若被未来版本写出）。
  `DECODE_ERROR`：已知消息但布局解析失败（长度/越界）——服务不崩，继续运行。
- 常见事件字段：`MOVE{code,from,to,reason}`、`DRAW{player,cards:[{code,pos}]}`、
  `DAMAGE/RECOVER/PAY_LPCOST{player,amount}`、`LPUPDATE{player,lp}`、
  `NEW_TURN{turn_player}`、`NEW_PHASE{phase,phase_name}`、
  `SUMMONING/SPSUMMONING/SET/FLIPSUMMONING{code,at}`、`ATTACK{attacker,target}`、
  `BATTLE{attacker,aa,ad,bd0,target,da,dd,bd1}`、`WIN{winner,reason,reason_name}`、
  `CHAINING{code,at,desc,chain_count,…}`、`RELOAD_FIELD{p0,p1,chains}`。
- 事件按 viewer 同样过滤（如对手的 DRAW 事件 code 全 null）。

## 5. 确定性（AI 回放根基）

同 `seed` + 完全一致的 respond 序列 ⇒ **事件流与状态序列逐字节一致**
（测试以 canonical JSON 比较通过）。注意：duel_id 是服务会话序号，不在此保证内。
卡组初始顺序 = 服务按 seed 派生 PRNG 对传入 decks 做的确定性洗牌
（core 的 Startup 不洗卡组，初始洗牌是宿主职责；传入顺序不影响抽牌序）。

## 6. v0 偏差与已知限制（PM 报备同文）

1. **区域槽数**：工单写 `monster_zones[5]`；core 布局为 7/8 槽（MR5 额外怪兽区），
   实现按 7/8 输出（下标=seq，多余槽恒 null）。卡池不涉 Link 时无差异。
2. **pending.player 为工单外补充字段**（2 人热座必需）；`SELECT_TRIBUTE` 归一化为
   `SELECT_CARD(tribute:true)`；`SELECT_DISFIELD` 归一化为 `SELECT_PLACE(disfield:true)`。
3. **SELECT_OTHER 只支持 cancel**：SELECT_SUM/ANNOUNCE_*/SORT_* 等的结构化应答留待
   后续工单（经典卡池主要路径不触发；触发时服务不崩，可取消或换策略）。
4. 效果描述 id（desc/prompt）语义解释、灵摆/超量素材明细、TAG 对局（TAG_SWAP 解码）
   均不在 v0。
5. ready 行是工单外的服务→客户端单向外加帧（便于 spawn 健康检查）。
