# 项目任务树（Classic Duel）—— v2 方向修正版（2026-09-25）

> 本文档是项目的唯一任务管理入口。
> **v2 重大修正（用户方向书）**：放弃自研规则/效果引擎主线，改用 Project Ignis `ocgcore + CardScripts` 作为规则与卡牌执行层；"Classic" = 卡池选择，不再自定义规则。
> 架构基准：`docs/architecture-v2.md` ｜ 决策过程：`docs/engine-route-assessment.md`

## 0. 修正后原则（最高优先级，覆盖旧文档冲突处）

1. **能够让 ocgcore 负责的规则，不重新实现**（回合/阶段/召唤合法/战斗/连锁/时点/目标合法/结算/胜负全归 core）
2. 卡牌效果 = CardScripts（`c{passcode}.lua`），不手写 Trigger/Target/Action；自然语言解析最多作为未来缺脚本的辅助
3. "Classic" = 卡池与预设卡组选择，不是规则修改。**已取消**：每回合 3 次特殊召唤上限、简化连锁、自研召唤规则等全部自定义规则
4. YGOCDB 只做中文显示层，不是规则真相源
5. 自有数据层只放 metadata（enabled / pool / ai_tags / 收藏解锁 / 卡组），不改原始 CardScripts 与中文卡库
6. 卡图语言与游戏语言解耦（`docs/card-display.md`），英文卡图不阻塞任何事
7. **Phase P 探针结束前禁止**：手写几十张卡效、自研连锁、重写召唤规则、批量生成 T/T/A、特殊召唤限制、大规模 UI、RL、复杂搜索 AI

## 1. 新优先级（P0~P8）

| 优先级 | 内容 | 对应任务 | 状态 |
|---|---|---|---|
| **P0** | ocgcore/CardScripts 技术探针（Phase P：P1~P4） | **D1**（`WO-005`） | 📋 待派发 🔴 |
| **P0** | WindBot 技术调查（AI V0 参照） | **D2**（`WO-006`） | 📋 待派发 |
| P1 | 中文卡库与 ID 映射（数据层已就绪；三方 ID 对齐在 D1-P4 验证） | 数据层 + **C1** | 🔄 C1 执行中 |
| P2 | Classic Duel Adapter（D1=GO 后开单） | 未来工单 | ⏸ 等 P0 |
| P3 | 最小 UI（中文，原画+中文渲染卡面） | 未来工单 | ⏸ |
| P4 | 玩家完整进行一局真实规则决斗（第一里程碑 v2） | — | ⏸ |
| P5 | AI V0（heuristic，经 Adapter，零非法操作） | 未来工单 | ⏸ |
| P6 | 经典卡池建立（C1 产出 + 人工挑卡 + metadata） | C1 + 后续 | 🔄 |
| P7 | 卡组编辑器 | 未来工单 | ⏸ |
| P8 | 扩卡与 AI 增强（AI V1 届时再评估搜索/clone/replay） | — | ⏸ |

## 2. 变更清单（对既有任务的处置：KEEP / MODIFY / PAUSE / REMOVE / NEW）

| 既有项 | 处置 | 说明 |
|---|---|---|
| 中文卡库数据层（cards_clean.json 等 + 工具） | **KEEP** | 核心资产，P1 优先级的主体；ID 映射由 D1-P4 验证 |
| 卡面体系（card-display.md + B1 下载器） | **KEEP** | 与方向书 §九 完全一致 |
| B2 原画工单（WO-004） | **KEEP** | 待派发，不阻塞主线 |
| C1 卡池初筛（worker C 执行中） | **KEEP，语义 MODIFY** | 客观过滤规则不变；产出语义从"effect-system 可表达性"改为"**经典卡池适合度**"（排除 Link/灵摆/同调/超量核心与现代高速展开）；complexity 字段降级为参考 |
| A1 自研规则引擎（worker A 已回报完成） | **验收后 PAUSE（冻结为 fallback）** | 交付价值：No-Go 回退路线 + 规则行为对照参考 + 测试骨架；验收后冻结，不再迭代 |
| src/core 状态模型 + node:test 骨架 | **PAUSE（随 A1 归档）** | v2 的 GameState 来自 Adapter；测试骨架供 Adapter/UI 复用 |
| Phase 4 自研 Effect Engine（原已冻结） | **REMOVE（主线）** | effect-system.md 归档为 fallback 设计 |
| Phase 5 自研 Spell/Trap | **REMOVE（主线）** | ocgcore 原生处理 |
| 每回合 3 次特殊召唤等自定义规则 | **REMOVE** | 从正式需求删除；仅存在于 fallback 代码归档（src/core/config.ts 的 specialSummonLimit 随归档保留，主线不引用） |
| v1-rules.md / effect-system.md | **ARCHIVE** | fallback 设计文档，已加归档头注；NO-GO 时恢复 |
| AI 计划（原 Phase 6：Minimax/clone 搜索） | **MODIFY** | AI V0 = heuristic 经 Adapter；AI V1 等 Adapter 稳定再研究（不预设 Minimax）；WindBot 调查（D2）决定复用 |
| 原 Phase 7/8（真实卡组/扩卡） | **MODIFY** | 并入新 P4/P6/P7/P8；扩卡成本因 CardScripts 大幅下降 |
| Phase P 探针（D1）、WindBot 调查（D2）、Adapter、metadata 层 | **NEW** | 见 P0~P2 与 §3~§5 |

## 3. Phase P：OCGCore Integration Probe（D1，WO-005）

总目标：回答"**ocgcore + CardScripts 能否作为 Classic Duel 的真正后台规则引擎**"。产出决策数据，不是生产代码。细节（输入/内容/验收/失败条件/下一步）见工单 `docs/workorders/WO-005-ocgcore-spike.md`。

| 探针 | 目标 | 关键验收 | 失败条件 |
|---|---|---|---|
| P1 | 获取并理解现有项目（读当前版本实际代码，不凭印象） | `OCGCORE_INTEGRATION_NOTES.md`（API/初始化/载卡/载脚本/消息机制/Windows 构建七要素） | 拿不到核心且无法构建 |
| P2 | 最小 Duel（脱离 EDOPro UI） | 普通怪兽完整最小决斗（抽/召/战斗/回合推进） | API 无法脱离客户端驱动 |
| P3 | CardScripts 真实效果卡 | 5~10 张简单卡（抽牌/破坏/改ATK/墓地特招/陷阱/触发）零自研逻辑正确执行 | 脚本无法脱离 EDOPro 加载 |
| P4 | 中文卡库 ID 映射 | 随机 20~50 张三方对齐，"passcode 可否作统一主键"有明确结论 | 系统性 ID 不对齐 |

### Go / No-Go（用户定义标准，探针后执行）

> **✅ 判定结果（2026-09-25）：GO**（见 `reports/D1-acceptance.md`）。ocgcore + CardScripts 正式确定为主线；P2 Adapter 工单已开（E1/WO-007）。

- **GO**：ocgcore 独立运行 ✚ CardScripts 可加载 ✚ 能读取并提交决斗选择 ✚ 中文 ID 可靠映射 ✚ Adapter 路径可接受 → 正式确定主线，开 Adapter 工单
- **NO-GO**：仅在明确技术阻塞（Windows 构建不稳 / API 无法满足客户端控制 / CardScripts 无法脱离 EDOPro / 数据映射系统性问题）→ 重评自研路线（fallback 资产在归档区）
- ⚠️ **不因"看起来集成复杂"提前 No-Go**——复杂度本身就是探针要量化的交付物

## 4. WindBot 调查（D2，WO-006）

七问（通讯方式/合法动作获取/决策结构/可否作 AI V0/通信层复用/Deck Executor 占比量化/自定义卡组限制）→ `docs/reports/WINDBOT_EVALUATION.md`，结论 USE / PARTIAL_USE / REFERENCE_ONLY / NOT_SUITABLE。只调查不采用。

## 5. AI 路线（v2 重定义）

- **AI V0**：经 Adapter 获取当前可执行选择，heuristic/rule-based 完整打一局；会召唤、发动基础效果、攻击、选合法目标、结束回合，零非法操作
- **AI V1**：Adapter 稳定后研究——公开 Game State 获取 / duel clone / 快速 replay / seed 确定性 / 短程搜索适配性；**不预设 Minimax，不做 RL**

## 6. 架构（v2）

见 `docs/architecture-v2.md`：`UI / AI / 卡组卡池 → Adapter(JSON 协议) → ocgcore(C API) + CardScripts`；YGOCDB 独立做中文显示层；自有 metadata 层管卡池/标签/收藏。UI 与 AI 只面对 Adapter，不直接处理 core 二进制消息。

## 7. 工单索引（PM 制定 → 用户派发 → worker 执行 → PM 验收）

> 编号规则：任务编号 = worker 字母 + 序号。工单文件名沿用 WO-xxx（已派发会话按旧路径领取，勿改名）。

| 任务编号 | 执行者 | 内容 | 依赖 | 优先级 | 状态 |
|---|---|---|---|---|---|
| A1（`WO-001`） | worker A | 自研规则引擎（fallback 资产） | — | 已降级 | ✅ 验收通过（`reports/A1-acceptance.md`），**已冻结归档** |
| B1（`WO-002`） | worker B | 卡图下载器（L3） | — | — | ✅ 验收通过（`reports/B1-acceptance.md`） |
| B2（`WO-004`） | worker B | 原画下载（L1）+ 简中可得率（L2） | B1 ✅ | 🟡 | ✅ 验收通过（`reports/B2-acceptance.md`；L1 源实测修正为 YGOPRODeck cards_cropped） |
| C1（`WO-003`） | worker C | 卡池机器初筛（语义=经典适合度） | — | P1/P6 | ✅ 验收通过（`reports/C1-acceptance.md`，入池 2599 张候选） |
| **D1**（`WO-005`） | worker D | **Phase P 探针 P1~P4（路线决策）** | 无 | 🔴 P0 | ✅ 验收通过，**判定 GO**（`reports/D1-acceptance.md`，提交 `feeede7`） |
| **D2**（`WO-006`） | worker D（D1 后）或另派 | WindBot 技术调查 | 建议 D1-P1 后 | P0 | 待派发 |
| **E1**（`WO-007`） | worker E | **Adapter v0：JSON 协议服务（P2 关键路径）** | D1 ✅ GO | 🔴 P2 | 待派发 |

> 秘书 worker（`SECRETARY.md`）：PM 直接控制的小改动子代理，规则不变。

## 8. 归档区（fallback，不删除）

- `docs/v1-rules.md`、`docs/effect-system.md`（已加归档头注）
- src/core + src/engine（A1 交付验收后冻结）及其测试
- 原 Phase 3~8 计划文本（git 历史可溯）
- **恢复条件**：Phase P = NO-GO 时整体解冻，按原路线继续

## 9. 阶段报告索引

- `docs/reports/phase-0-report.md`、`phase-1-report.md`、`B1-acceptance.md`
- `docs/engine-route-assessment.md`（路线决策记录）
- 待产：`OCGCORE_INTEGRATION_NOTES.md`（D1-P1）、`D1-report.md`、`WINDBOT_EVALUATION.md`（D2）
