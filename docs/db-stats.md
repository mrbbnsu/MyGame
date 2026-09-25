# 卡库统计报告

- 原始条目：14325（百鸽 YGOCDB）
- 可用（含数据）：14281，输出：14281
- 过滤：44 张 id=0 的动画卡/未收录卡（无类型数据、无中文）

## 大类
| 类型 | 数量 |
|---|---|
| 怪兽 | 9329 |
| 魔法 | 2874 |
| 陷阱 | 2078 |

## 召唤机制（怪兽，可叠加，故总数 > 怪兽数）
| 机制 | 数量 |
|---|---|
| FUSION | 576 |
| RITUAL | 153 |
| SYNCHRO | 537 |
| XYZ | 601 |
| LINK | 469 |
| PENDULUM | 390 |
| FLIP | 212 |
| TOON | 18 |
| SPIRIT | 42 |
| UNION | 40 |
| DUAL | 45 |
| TUNER | 604 |
| NORMAL | 723 |
| EFFECT | 8521 |

- 灵摆（含各种召唤法交叉）：390 张
- 召唤条件怪兽（不能通常召唤）：352 张
- 无等级非连接怪兽：0 张

## 魔法种类
| 种类 | 数量 |
|---|---|
| NORMAL | 1080 |
| QUICKPLAY | 574 |
| CONTINUOUS | 516 |
| EQUIP | 282 |
| FIELD | 339 |
| RITUAL | 83 |

## 陷阱种类
| 种类 | 数量 |
|---|---|
| NORMAL | 1333 |
| CONTINUOUS | 566 |
| COUNTER | 179 |

## 字段完整度
- cn_name（YGOPro 中文译名）：14281/14281
- sc_name（官方简中）：8027/14281（未覆盖的回退 cn_name）
- md_name（Master Duel 中文）：14002/14281
- en_name：13878/14281
- 效果文本 desc：14281/14281
- 灵摆卡缺 pdesc：16 张
- Link 箭头：本库不提供（level 仅含连接数），后续用 YGOPRODeck `linkmarkers` 补充
- 名字/文本均缺失：{'sc_name': 6254, 'en_name': 403, 'md_name': 279}

> 种类不一致与异常记录见 `data/quality_notes.md`。