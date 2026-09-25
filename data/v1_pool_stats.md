# V1 卡池机器初筛统计（WO-003）

数据源：`data/cards_clean.json`（14,281 张）·
规则：`docs/workorders/WO-003-v1-pool-screening.md` §2 ·
黑名单依据：`docs/effect-system.md` §11 ❌

## 总览

| 类别 | 数量 |
|---|---:|
| 入池合计（reason=OK） | 2,599 |
| - 普通怪兽 C0 | 685 |
| - 通常魔法 C1? | 862 |
| - 通常陷阱 C1? | 1,052 |
| 留待后续 EXTRA_PENDING（融合/仪式，不算失败） | 729 |
| 排除合计（其余 reason） | 10,953 |
| **全库合计** | **14,281** |

## 入池构成

- **C0 普通怪兽 685 张**：全库 NORMAL 怪兽 723 张，
  其中灵摆普通怪兽 38 张因 lscale 被结构排除；其余全部入池
  （含普通怪兽·协调 14 张——TUNER 不在工单结构排除清单内，按规则入池）。
- **C1? 通常魔陷 1,914 张**（问号 = 待人工定级）：
  通常魔法 862 张 + 通常陷阱 1,052 张，
  均无黑名单命中、非装备/场地/永续/速攻/反击种类。

## 排除原因分布（互斥，按判定优先级；不含 OK / EXTRA_PENDING）

| reason | 数量 |
|---|---:|
| STRUCT_MECH:SYNCHRO | 537 |
| STRUCT_MECH:XYZ | 601 |
| STRUCT_MECH:LINK | 469 |
| STRUCT_PENDULUM | 352 |
| STRUCT_FLAG:TOON | 17 |
| STRUCT_FLAG:SPIRIT | 34 |
| STRUCT_FLAG:UNION | 40 |
| STRUCT_FLAG:DUAL | 45 |
| STRUCT_KIND:RITUAL | 83 |
| STRUCT_KIND:EQUIP | 282 |
| STRUCT_KIND:FIELD | 339 |
| STRUCT_KIND:QUICKPLAY | 574 |
| STRUCT_KIND:CONTINUOUS | 1,082 |
| STRUCT_KIND:COUNTER | 179 |
| EFFECT_MONSTER | 5,820 |
| BLACKLIST:除外后再回到 | 22 |
| BLACKLIST:指示物 | 27 |
| BLACKLIST:超量 | 130 |
| BLACKLIST:骰子 | 9 |
| BLACKLIST:同调 | 123 |
| BLACKLIST:灵摆 | 54 |
| BLACKLIST:连接 | 68 |
| BLACKLIST:衍生物 | 56 |
| BLACKLIST:硬币 | 9 |
| BLACKLIST:每次…可以发动 | 1 |
| **排除合计** | **10,953** |

## EXTRA_PENDING 构成（V1 引擎未建，后续阶段可捞回）

| summon_mech | 数量 |
|---|---:|
| FUSION（融合） | 576 |
| RITUAL（仪式） | 153 |

## 黑名单逐词命中（基数 = 全部通常魔陷 2,413 张 = 入池 1,914 + 黑名单排除 499）

逐词独立计数，一张卡可命中多个词（与上表互斥计数有重叠），仅作复核。

| 关键词 | 命中卡数 |
|---|---:|
| 同调 | 123 |
| 超量 | 156 |
| 多维 | 0 |
| 灵摆 | 61 |
| 连接 | 83 |
| 衍生物 | 65 |
| 代币 | 0 |
| 指示物 | 30 |
| 硬币 | 9 |
| 骰子 | 10 |
| Xyz(英文) | 0 |
| Synchro(英文) | 0 |
| Pendulum(英文) | 0 |
| Link(英文) | 0 |
| Token(英文) | 0 |
| Counter | 0 |
| 一回合一次×2 | 0 |
| 除外后再回到 | 30 |
| 每次…可以发动 | 1 |
| 特殊召唤方式不同 | 0 |

## 口径说明

- 输出 `data/v1_pool.json` 为**全库打标**：`reason: "OK"` 即候选池（Phase 4 人工挑选的输入），
  其余 reason 为排除/留待原因，可按 id 对照 `tools/query_card.py` 核对卡面。
- reason 取判定顺序中首个命中；黑名单逐词命中表为独立计数，与排除分布存在重叠。
- 黑名单只作用于通常魔陷的效果文本（`desc`+`pdesc`）；普通怪兽为无效果卡，文本不参与检查，
  故工单括注"仅怪兽文本"的 `Counter` 词不会命中（保留在配置中仅为忠实工单定义）。
- 描述性短语落地正则：除外后再回到 = `除外[^。，；]*回(?:到|来)`；
  每次…可以发动 = `每次[^。？]*可以`；特殊召唤方式不同 = `这个方法|上述方法`；
  一回合一次×2 = `[一1]回合[一1]次` 出现 ≥2 次（"各能使用1次"等变体不计入，
  避免把卡名使用限制误判为多个一回合一次；本库通常魔陷上该主正则 ≥2 次命中 0 张）。
- 补充同义词：多维（超量旧译，0 命中）。已考虑但放弃：投掷硬币、掷骰
  （分别为"硬币"/"骰子"的子串，冗余）。
- 判定顺序：summon_mech → 灵摆 lscale → TOON/SPIRIT/UNION/DUAL → 魔陷种类 →
  黑名单关键词 → 普通怪兽/效果怪兽归类。
- 幂等：输出按 id 排序、无时间戳，连跑两次逐字节一致。
