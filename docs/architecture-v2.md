# Classic Duel 架构 v2（2026-09-25 用户方向书落地）

> v2 修正核心：**不重新开发《游戏王》**。规则与卡牌效果复用 Project Ignis 生态（ocgcore + CardScripts）；"Classic"由卡池选择实现，不再自定义规则。本文是主线路径的架构基准，取代自研引擎路线（后者归档为 fallback，见任务树归档区）。

## 1. 整体架构

```text
                    Classic Duel（我们开发的部分）
                         │
        ┌────────────────┼────────────────┐
        │                │                │
       UI              AI             卡组/卡池
   （中文界面）    （V0 heuristic）   （经典卡池/编辑器）
        │                │                │
        └────────────────┼────────────────┘
                         │  JSON / 结构化协议（唯一交互面）
                         ▼
                Classic Duel Adapter
                         │  ocgcore C API（形式待探针定：FFI / C++ sidecar / …）
                         ▼
                     ocgcore（规则执行：回合/阶段/召唤合法/战斗/连锁/时点/目标合法/结算/胜负）
                         │
                Project Ignis CardScripts（c{passcode}.lua，卡牌效果）
```

```text
YGOCDB / 百鸽（中文显示层，不是规则真相源）
      │
      ▼
中文卡名 / 中文效果文本 / 中文类型描述 / ATK·DEF 等 UI 信息 / 图片关联
```

## 2. 层职责与原则

| 层 | 负责 | 原则 |
|---|---|---|
| ocgcore | 游戏王规则本身（回合流程、阶段、召唤合法性、战斗、连锁、时点、对象合法性、效果结算、区域、胜负） | **能够让 ocgcore 负责的，不重新实现**。规则执行以 core+脚本为准 |
| CardScripts | 每张卡的具体效果 | `c{card_id}.lua` 与卡片密码直接对应；不手写 Trigger/Target/Action；自然语言解析最多作为未来缺脚本的辅助 |
| YGOCDB（已有 cards_clean.json） | 中文显示数据 | 只服务 UI；与规则冲突时服从 ocgcore |

**双库并存说明（常见疑问："EDOPro 不是自带卡库吗？"）**：是，EDOPro 自带 `cards.cdb`（id/类型位图/攻守/等级/种族/属性/setcode 等机器字段 + 某语言的 name/desc 文本）。它**必须保留并直接使用**——core 与 Lua 脚本要读它的机器字段做规则判断，我们不自己造 cdb。但它**不替代 YGOCDB 层**：其文本的语言/译名口径不受我们控制，而百鸽数据有完整中文回退链（cn_name/sc_name/md_name）与中文效果文本（14281 张全覆盖），这是我们 UI 的既定数据源。两库按 passcode 关联（D1-P4 实测验证，注意 cdb 里可能有预发行/原创 id 与 alias 字段异常）。自有 metadata 层（enabled/pool/ai_tags）独立于两库之上，不改任何一方。
| 自有 metadata 层（新增） | `{id, enabled, pool, ai_tags, 收藏/解锁, 卡组}` | 不修改原始 CardScripts 与中文卡库来保存这些内容 |
| Adapter（我们开发的核心） | core 二进制消息 ↔ JSON 结构转换（如 SELECT_ACTION + actions 列表） | UI/AI 只面对 Adapter；TS 项目不得到处直接处理 core 二进制消息；实现形式（native bridge / C++ sidecar / …）由探针决定，不预设 |
| UI / AI | 中文界面；AI V0 heuristic | 卡图语言与游戏语言解耦（card-display.md），英文卡图不阻塞任何事 |

## 3. "Classic" 的定义（v2）

**标准游戏王规则 + 我们筛选的经典节奏卡池。**

- 经典化手段：卡池准入（不加 Link/灵摆核心、高速同调/超量展开、一回合十几步的现代展开组）、预设卡组选择
- 不是规则修改：每回合 3 次特殊召唤上限等自定义规则**已全部取消**
- 若未来想玩历史时期正式规则 → 研究 ocgcore 已有的旧 Master Rule 支持（非第一阶段重点）

## 4. AI 路线（v2）

- **AI V0**：经 Adapter 获取当前可执行选择，heuristic / rule-based 完整打完一局，零非法操作（会召唤/发动基础效果/攻击/选合法目标/结束回合）。可参照 WindBot（调查工单 D2 决定复用程度）
- **AI V1**：Adapter 稳定后再研究——公开 Game State 获取、duel clone / 快速 replay / seed 确定性 / 短程搜索适配性。**不预设 Minimax**，不做 RL

## 5. 许可与版权（记录在案）

- ocgcore / CardScripts：**AGPL-3.0-or-later**。本地自玩无障碍；若公开分发，需遵守 AGPL 开源要求
- 卡图/卡名/素材：Konami / 集英社版权；EDOPro 自声明非官方项目。公开发布前必须重新评估

## 6. 探针结束前禁止事项

手写几十张卡效、自研连锁系统、重写召唤规则、批量生成 Trigger/Target/Action、特殊召唤次数限制、大规模 UI、强化学习、复杂搜索 AI——全部可能因 ocgcore 集成成功而变成重复工作。
