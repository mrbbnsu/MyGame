# 效果系统规范（引擎契约）

> 引擎**不解析卡片文字**。每张卡是结构化数据，效果 = 触发时机 + 费用 + 对象 + 动作序列。
> 加新卡 = 填数据；只有出现新的动作/时机类型时才改引擎。
> 本文与 `data/cards/*.json` 一一对应，校验脚本 `tools/validate.js` 会检查所有枚举。

## 1. 卡片结构

### 1.1 怪兽（主卡组）

```json
{
  "id": "M001",
  "name": "青眼白龙",
  "type": "MONSTER",
  "deck": "MAIN",
  "kinds": ["NORMAL"],
  "attribute": "LIGHT",
  "race": "DRAGON",
  "level": 8,
  "atk": 3000,
  "def": 2500,
  "text": "以力量著称的传说之龙。",
  "effects": [],
  "procedures": []
}
```

- `kinds`：`NORMAL` / `EFFECT` / `FLIP` / `FUSION` / `RITUAL` 的任意组合。翻转怪兽 = `["EFFECT","FLIP"]`。
- `procedures`：非通常召唤的出场流程（见 §6）。

### 1.2 魔法 / 陷阱

```json
{
  "id": "S023",
  "name": "恶魔之斧",
  "type": "SPELL",
  "deck": "MAIN",
  "spell_kind": "EQUIP",
  "text": "装备怪兽攻击力上升1000。",
  "effects": [ { "speed": 1, "timing": "OPEN", ... } ]
}
```

- `spell_kind`：`NORMAL` / `QUICK` / `CONTINUOUS` / `EQUIP` / `FIELD` / `RITUAL`
- `trap_kind`：`NORMAL` / `COUNTER` / `CONTINUOUS`
- 额外卡组卡（融合怪兽）：`"deck": "EXTRA"`，带 `fusion` 字段。

## 2. 效果结构

```json
{
  "timing": "TRIGGER",
  "speed": 1,
  "event": "ON_SUMMON",
  "event_filter": {},
  "condition": null,
  "cost": [],
  "target": null,
  "actions": [],
  "duration": null,
  "restriction": null
}
```

| 字段 | 说明 |
|---|---|
| `timing` | `IGNITION` 起动效果（主要阶段手动发动，速度1）/ `TRIGGER` 诱发效果 / `QUICK` 诱发即时效果（速度2）/ `STATIC` 永续效果 / `OPEN` 自由发动（通常陷阱用） |
| `speed` | 1 / 2 / 3，决定连锁权限 |
| `event` | `timing=TRIGGER` 时必填，见 §3 |
| `event_filter` | 收窄触发条件，如 `{"side":"OPPONENT"}`、`{"atk_min":1000}` |
| `condition` | 发动条件（不是代价），如 `{"exists":{"zone":"FIELD","side":"SELF","name":"黑魔术师"}}` |
| `cost` | 支付代价，见 §5。发动时支付，付不起不能发动 |
| `target` | 发动时选定的对象，见 §4 |
| `actions` | 结算时依序执行的动作，见 §6 |
| `duration` | 变动类效果的持续时间，见 §7 |
| `restriction` | `ONCE_PER_TURN` / `LIMIT_1`（同名卡组限制1张） |

### STATIC（永续）效果用 `aura` 代替 target/actions：

```json
{
  "timing": "STATIC",
  "speed": 0,
  "aura": {
    "filter": { "zone": "FIELD", "side": "SELF", "race": "DRAGON" },
    "mod": { "cannot_be_targeted": true }
  }
}
```

- `filter` 选中"持续受影响的卡"（场上卡，随卡进出实时生效）。
- `include_self: true` 表示把自己也算进 aura 范围。

## 3. 触发事件（V1 全集）

| event | 时机 |
|---|---|
| `ON_SUMMON` | 自己场上出现怪兽（召唤/特殊召唤） |
| `ON_OPPONENT_SUMMON` | 对方场上出现怪兽 |
| `ON_ANY_SUMMON` | 任一方场上出现怪兽 |
| `ON_FLIP` | 自己的卡被翻开 |
| `ON_ATTACK` | 怪兽被宣言攻击（含直接攻击） |
| `ON_OPPONENT_ATTACK` | 对方怪兽宣言攻击 |
| `ON_DESTROYED_BY_BATTLE` | 自己的怪兽被战斗破坏 |
| `ON_SENT_TO_GY` | 自己的卡送去墓地 |

触发卡的 `event_filter` 可用：`side` / `atk_min` / `atk_max` / `level_max` / `race` / `position`。
被触发事件的当事卡（攻击者、被破坏的卡等）记为 `$THIS`，动作里可用模板引用。

## 4. 对象（target）

```json
{
  "count": 1,
  "optional": false,
  "filter": {
    "zone": "FIELD",
    "side": "OPPONENT",
    "type": "MONSTER",
    "face": "UP",
    "position": "ANY",
    "race": "DRAGON",
    "attribute": "LIGHT",
    "level_max": 4,
    "atk_min": 0,
    "atk_max": 1500,
    "name": "黑魔术师",
    "sort": "ATK_ASC",
    "auto_select": false
  }
}
```

| 字段 | 取值 |
|---|---|
| `zone` | `FIELD` / `GY` / `HAND` / `DECK` / `ANY_FIELD`（双方场上）/ `ANY_GY`（双方墓地）/ `FIELD_OR_GY` |
| `side` | `SELF` / `OPPONENT` / `ANY` |
| `type` | `MONSTER` / `SPELL` / `TRAP` / `ANY` |
| `face` | `UP` / `DOWN` / `ANY` |
| `position` | `ATTACK` / `DEFENSE` / `ANY` |
| `sort` + `auto_select` | 无需玩家选择，引擎自动选（如"地割"选最低攻） |

结算时对象已离场 → 该动作空发，继续结算后续动作。

## 5. 费用（cost）

| cost | 参数 |
|---|---|
| `LP` | `amount` |
| `HALVE_LP` | 无 |
| `DISCARD` | `count`（玩家自选手牌） |
| `TRIBUTE` | `count` + `filter`（解放自己场上的怪兽） |
| `TRIBUTE_LEVELS` | `min`（解放的祭品等级合计 ≥ min，仪式用） |
| `SEND_SELF_TO_GY` | 无（自身送去墓地） |

## 6. 动作（actions，V1 全集）

| action | 参数 | 说明 |
|---|---|---|
| `DRAW` | `count` | 抽卡 |
| `DISCARD` | `count` | 弃手牌（自选） |
| `DISCARD_RANDOM` | `count` | 随机弃手牌 |
| `DISCARD_ALL_DRAW_SAME` | — | 手牌全部弃掉，再抽相同数量 |
| `GAIN_LP` | `amount` | 回复 LP |
| `DAMAGE_TO_OPPONENT` | `amount` | 效果伤害 |
| `DAMAGE_TO_SELF` | `amount` | 自己受效果伤害 |
| `DAMAGE_TO_ATTACKER` | — | 给攻击者 ATK 值的伤害（魔法之筒） |
| `DAMAGE_BOTH` | `source: "TARGET_ATK"` | 双方各受对象 ATK 伤害（破坏轮） |
| `DESTROY` | — | 破坏 target |
| `BANISH` | — | 除外 target |
| `SEND_TO_GY` | — | target 送去墓地 |
| `RETURN_TO_HAND` | — | target 回手牌 |
| `SPECIAL_SUMMON` | `from` / `filter` / `position` / `count` | 特殊召唤，`from`: `GY`/`HAND`/`DECK`，`position`: `ATTACK`/`DEFENSE`/`ANY`；`same_state: true` 按原状态复活（时间机械） |
| `SEARCH` | `filter` | 从卡组把符合条件的卡加入手牌 |
| `SEND_DECK_TO_GY` | `filter` | 从卡组送卡去墓地 |
| `ATK_MOD` | `amount` | 攻击力变动（可负数，配合 duration） |
| `DEF_MOD` | `amount` | 守备力变动 |
| `CHANGE_POSITION` | `to` | `ATTACK` / `DEFENSE` / `FACE_DOWN_DEFENSE` |
| `FLIP_FACE_UP` | — | 翻开（盖卡翻开触发 ON_FLIP） |
| `TAKE_CONTROL` | — | 获得对象控制权（配合 duration） |
| `NEGATE_ATTACK` | — | 无效那次攻击 |
| `END_BATTLE_PHASE` | — | 结束战斗阶段 |
| `NEGATE_ACTIVATION` | — | 无效发动（反击陷阱）；`then: "DESTROY"` 表示无效后破坏 |
| `FUSION_SUMMON` | `from: "HAND_OR_FIELD"` | 融合召唤：按融合素材把卡送墓地，从额外卡组出场 |
| `RITUAL_SUMMON` | — | 仪式召唤：配合 cost `TRIBUTE_LEVELS`，从手牌出场 |
| `EQUIP` | — | 装备魔法挂到 target 上 |
| `CANNOT_ATTACK` | — | 对象本效果 duration 内不能攻击 |

## 7. 持续时间（duration）

| 值 | 到何时为止 |
|---|---|
| `THIS_TURN` | 本回合结束 |
| `UNTIL_NEXT_OWN_STANDBY` | 到自己下次准备阶段（光之护封剑） |
| `WHILE_EQUIPPED` | 装备魔法挂在期间 |
| `WHILE_ON_FIELD` | 该卡在场上期间（永续陷阱的锁定类） |
| `PERMANENT` | 永久（咒术师的减攻） |

## 8. aura 的 mod（永续效果参数）

| mod | 类型 | 说明 |
|---|---|---|
| `atk` / `def` | 数字 | 攻/守变动（可负） |
| `pierce` | bool | 获得贯穿 |
| `cannot_attack` | bool | 不能攻击 |
| `cannot_be_targeted` | bool | 不能被卡的效果指定 |
| `cannot_be_destroyed_by_battle` | bool | 不会被战斗破坏 |
| `cannot_activate` | bool | 该类卡不能发动（王宫的通告锁魔法） |

## 9. 出场流程（procedures）

写在怪兽卡上，引擎在主要阶段提供"可以这样做吗/执行"入口：

```json
"procedures": [
  {
    "kind": "SPECIAL_SUMMON",
    "from": "HAND",
    "position": "ANY",
    "condition": { "exists": { "zone": "FIELD_OR_GY", "side": "SELF", "name": "青眼白龙" } }
  }
]
```

仪式怪兽：

```json
"procedures": [
  { "kind": "RITUAL", "ritual_spell": "混沌之仪式", "tribute_levels_min": 8 }
]
```

## 10. 连锁结算模型（V1）

1. `发动`：卡从手牌/盖放状态翻开进入连锁堆栈，支付 cost，锁定 target。
2. `响应`：对手（然后双方交替）可用 speed ≥ 当前堆栈顶 speed 的卡响应。反击陷阱 speed 3 可以响应一切；速度1不能被速度1响应。
3. `结算`：从堆栈顶（最后发动的）开始逆序逐张结算 actions。若发动者自身在结算前已离场，V1 简化为**照常结算**（不做"效果不适用"细判）。
4. 触发式效果在事件结算完成后统一入栈询问（不做错过时点判定，一切"可以发动的时机"都询问玩家，默认可关闭自动发动）。

## 11. 卡牌准入检查单（加新卡时自问）

✅ V1 可以加：
- 效果能用 §3~§8 的枚举表达出来
- 最多 2～3 个效果段
- 限制统一用 `ONCE_PER_TURN` / `LIMIT_1`

❌ V1 先不加：
- 4～5 个独立效果段
- 多种不同名称的"一回合一次"
- 连锁中除外自身再返回
- 依特殊召唤方式变化的效果
- 同时修改规则、区域和召唤条件
- 掷硬币 / 指示物 / 衍生怪 / 动态计数数值（+500×墓地里魔法的数量之类）

需要新 action/event/mod 的情况 → 先在本文登记枚举，再改引擎，再加卡。
