# 项目任务树（Classic Duel）

> 本文档是项目的唯一任务管理入口。每个 Phase 含：状态 / 依赖 / 任务清单 / 验收标准。
> 任何新需求先判断归属模块（数据/规则/效果/AI/UI/模式/测试），再登记到对应 Phase，不临时堆功能。

## 模块 → 目录映射

| 模块 | 目录 | 说明 |
|---|---|---|
| Card Database | `data/` + `tools/*.py` | 卡库下载、清洗、统计、查询 |
| Rule Engine | `src/core/` + `src/engine/` | 状态模型、区域/移动 API、回合/阶段、召唤、战斗、胜负 |
| Effect Engine | `src/effects/`（Phase 4 起） | 结构化效果解释执行（契约：`docs/effect-system.md`） |
| Deck System | `src/deck/` | 卡组合法性、卡池筛选、预设卡组 |
| AI | `src/ai/` | Legal Action 消费者、评价函数、搜索（绝不直接改状态） |
| UI | `src/ui/` | 主菜单、决斗界面、卡组编辑器 |
| Game Modes | `src/modes/` | Free Duel、Test Mode |
| Test Framework | `tests/` | node:test 单元/规则/AI/完整对局测试 |

## 技术栈（已定）

- **引擎/AI/UI**：TypeScript，Node ≥ 24 直接执行（type stripping），测试用 node:test，零 npm 依赖。
- **数据管道**：Python（`tools/`），产出 `data/cards_clean.json` 供游戏读取。
- **主键**：卡片密码 `id`（数字）。游戏内卡牌实例用运行时 `uid` 区分同名副本。

---

## Phase 0：项目骨架 —— ✅ 完成（2026-09-25）

- 依赖：无
- 任务：
  - [x] 项目目录结构（src/core、src/engine、tests、docs、data、tools）
  - [x] Git 仓库初始化 + .gitignore
  - [x] 配置文件（package.json / tsconfig.json / 规则配置 `src/core/config.ts`）
  - [x] 基础日志系统（`src/core/log.ts`，分级，默认静默）
  - [x] 测试框架（node:test，`npm test`）
  - [x] 游戏状态数据模型（`src/core/`：CardDef / CardInstance / Zone / PlayerState / GameState / RNG）
- 验收：`npm test` 通过冒烟测试，项目可启动。

## Phase 1：中文卡库 —— ✅ 完成（2026-09-25）

- 依赖：Phase 0（目录约定）
- 任务：
  - [x] 下载 YGOCDB 整库（14325 条）并本地保存
  - [x] 清洗为内部格式 `cards_clean.json`（14281 张，过滤 44 张 id=0 动画卡）
  - [x] 统计报告 `docs/db-stats.md`（大类/召唤机制/魔陷种类/字段完整度）
  - [x] 内部 Card Schema 定型（见 README 字段表）
  - [x] Card ID 查询工具 `tools/query_card.py`
  - [ ] YGOPRODeck 补充数据（Link 箭头/禁限表/系列）——推迟到需要时
- 验收：✅ 通过 Card ID 可查询中文名/英文名/类型/ATK/DEF/Level/效果文字。
- 报告：`docs/reports/phase-1-report.md`

## Phase 2：卡图 —— 📋 工单已定义，可并行分发（WO-002）

- 依赖：Phase 1
- 决策：卡图不阻塞引擎/AI，可与 Phase 3 并行；Phase 7（真实卡组+UI）前必须完成。
- 任务：
  - [ ] 卡图下载器（id.jpg，本地缓存，只下载缺失，失败重试，禁止热链）
  - [ ] 简中 → 其他版本 fallback
- 验收：随机抽 20 张卡正确显示对应卡图。

## Phase 3：最小 Rule Engine —— 📋 工单已定义，待分发（WO-001）

- 依赖：Phase 0
- 范围：**只用普通怪兽**。Deck / Hand / Monster Zone / Graveyard / Draw / 通常召唤 / 盖放 / 反转召唤 / 祭品召唤 / 位置变更 / 回合 / 阶段 / 战斗 / LP / 胜负 / 手牌上限。
- 明确不做：效果、魔法陷阱、连锁、特殊召唤（接口预留：special_summon_limit 进配置）。
- 架构要求（WO-001 中已细化为接口契约）：统一 moveCard API、数据化 Action（legalActions/applyAction）、GameState 可 structuredClone、RNG 种子化。
- 规则基准：`docs/v1-rules.md`（冻结版）；已固定选项：**先攻第一回合不抽牌**。
- 任务与验收：见 `docs/workorders/WO-001-phase3-rule-engine.md`
- 验收：两套普通怪兽卡组可脚本驱动完整打完一局并正确判胜，全程无非法状态。

## Phase 4：Effect Engine V1 —— ⬜ 未开始

- 依赖：Phase 3
- 首批 Action（任务书 §16）：DRAW / DESTROY / GAIN_ATK / DAMAGE / GAIN_LP
- 任务：
  - [ ] `src/effects/` 执行器：解释 effect-system.md 的结构化效果（timing/cost/target/actions/duration）
  - [ ] V1 卡池数据格式 `data/cards/*.json` + 校验脚本
  - [ ] 少量测试卡（真实卡，从 cards_clean.json 取数 + 手写结构化效果）
- 验收：所有已支持 Action 有自动测试（能发动/不能发动/合法与非法目标/正确结算）。

## Phase 5：Spell / Trap —— ⬜ 未开始

- 依赖：Phase 4
- 任务：通常魔法 / 通常陷阱 / 盖放 / 发动 / 基础 Chain（速度与后进先出，fizzle 规则）
- 验收：玩家可用基础魔法陷阱完成一局。

## Phase 6：AI V1 —— ⬜ 未开始

- 依赖：Phase 3（动作模型）、Phase 5（魔陷决策）
- 任务：Legal Action 消费者 / 基础评价函数（LP·怪兽·ATK·手牌·后场·墓地·斩杀线）/ 战斗+召唤+发动决策 / 有限深度搜索
- 任务书 §30 专项：Test AI-001（空场直接攻击）、Test AI-002（死者苏生斩杀识别）
- 验收：AI 全自主完整决斗，零非法操作（引擎级断言）。

## Phase 7：第一批真实卡组 —— ⬜ 未开始

- 依赖：Phase 4、5、6、2（卡图）
- 任务：龙族/青眼 vs 战士族，各 40 张；Test Mode（残局构造）就绪
- 验收：玩家 vs AI 从 8000 LP 完整对局（**第一里程碑**）。

## Phase 8：扩展至 100～150 张 —— ⬜ 未开始

- 依赖：Phase 7
- 任务：按 effect-system.md 枚举能力从全库筛卡，标 SUPPORTED / PARTIAL / UNSUPPORTED
- 验收：每张入库卡有结构化效果且通过校验脚本。

---

## 横切任务（不属于单一 Phase）

| 任务 | 归属 | 状态 |
|---|---|---|
| 卡池筛选（supported/complexity 打标） | Card Database | 📋 初筛工单 WO-003，可并行分发 |
| Test Mode（指定 LP/手牌/墓地起局） | Game Modes | ⬜ Phase 6 前就绪（AI 残局测试依赖） |
| YGOPRODeck 补充数据 | Card Database | ⬜ 按需 |
| 卡图下载 | Card Database | ⏸ Phase 7 前 |

## 工单索引（PM 制定，用户分发，完成后 PM 验收）

| 工单 | 内容 | 依赖 | 优先级 | 状态 |
|---|---|---|---|---|
| `workorders/WO-001-phase3-rule-engine.md` | 最小规则引擎 + 规则测试套件 | Phase 0（已完成） | 🔴 关键路径 | 待分发 |
| `workorders/WO-002-card-images.md` | 卡图下载器（本地缓存） | Phase 1（已完成） | 🟡 可并行 | 待分发 |
| `workorders/WO-003-v1-pool-screening.md` | V1 卡池机器初筛打标 | Phase 1（已完成） | 🟢 低 | 待分发 |

## 阶段报告索引

- `docs/reports/phase-0-report.md`
- `docs/reports/phase-1-report.md`
