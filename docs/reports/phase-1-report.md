# Phase 1 报告：中文卡库（2026-09-25）

> 卡库下载与清洗在先前会话完成，本次按任务书 §34 完成验收确认与查询工具。

## 数据产出

| 文件 | 内容 |
|---|---|
| `data/cards_raw.json` | YGOCDB 原始整库 14325 条 |
| `data/cards_clean.json` | 清洗版 14281 张（过滤 44 张 id=0 动画卡） |
| `data/cards.zip` + `.cards_md5` | 原始下载包与版本基线 |
| `docs/db-stats.md` | 统计报告 |
| `data/quality_notes.md` | 数据质量记录 |

## 统计结论（详见 docs/db-stats.md）

- 总卡牌：**14281**；怪兽 **9329** / 魔法 **2874** / 陷阱 **2078**
- 召唤机制：融合 576、仪式 153、同调 537、超量 601、连接 469、灵摆 390
- 普通怪兽 723、效果怪兽 8521；召唤条件怪兽 352
- 魔法：通常 1080 / 速攻 574 / 永续 516 / 装备 282 / 场地 339 / 仪式 83
- 陷阱：通常 1333 / 永续 566 / 反击 179

## 中文字段完整度

- cn_name（YGOPro 译名）100%；desc 效果文本 100%
- sc_name（官方简中）56%（回退链 cn→sc→jp 已在清洗层处理）
- en_name 97%；md_name 98%

## Card ID 情况

- 统一主键 = 卡片密码数字 `id`，与卡图文件名、YGOPRODeck API 一致
- 44 张 `id=0` 动画卡已过滤（无数据无中文）

## 卡图资源可获取性

- 本库（YGOCDB）不含图片；计划用 YGOPRODeck API 下载 `id.jpg` 本地缓存（须本地图，禁止热链）
- 卡图属于 Phase 2，已决策推迟到 Phase 7（真实卡组）前，不阻塞引擎开发

## 内部 Card Schema（已定型）

见 README「cards_clean.json 字段」一节。关键点：`flags` 数组（NORMAL/EFFECT/FUSION…可叠加）、`summon_mech`（额外卡组判定）、type 位图为 Master Duel 布局（勿按 ygocore 常量解读）、显示名走中文回退链。

## 验收结果

✅ **通过**。`python -X utf8 tools/query_card.py 89631139` 可查出：中文名（青眼白龙）、类型（MONSTER/NORMAL）、ATK/DEF（3000/2500）、Level（8）、效果文本。统计八项指标齐备。

## 已知问题

- Link 箭头整库缺失（level 只有连接数）；待 YGOPRODeck `linkmarkers` 补充（V1 不做 Link，不阻塞）
- 灵摆 16 张缺 pdesc（V1 不做灵摆，不阻塞）
- Link 怪 `def` 为占位值（清洗时已置空）

## 下一阶段

Phase 3：最小 Rule Engine（普通怪兽即可完整对局）。
