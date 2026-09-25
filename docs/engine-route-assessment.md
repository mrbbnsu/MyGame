# 引擎路线评估：自研 Effect Engine vs ocgcore + CardScripts（2026-09-25）

> 状态：**已决策（用户方向书拍板：主线转 ocgcore + CardScripts，"Classic"=卡池而非规则）**。本文保留作为决策过程记录；探针（D1，WO-005）只负责验证集成可行性与量化摩擦，不再承担"是否转路线"的论证。最终架构见 `docs/architecture-v2.md`。

## 1. 问题

V1 最大技术风险：卡牌效果怎么实现。当前路线（`docs/effect-system.md`）= 自研结构化效果（timing/cost/target/actions/duration），每张卡手写 JSON，引擎解释执行。

## 2. 提议路线（用户提供参考）

**Project Ignis 体系**：EDOPro 的 `ocgcore`（C++ 自动决斗规则引擎）+ `CardScripts`（Lua 5.3 官方卡牌脚本库，`c{passcode}.lua` 按卡片密码命名）。

- 效果、发动时点、目标合法性、连锁、破坏触发——全部现成，几千张卡持续维护
- 卡 ID 与我们主键（卡片密码）天然对齐，零映射表
- EDOPro 资源结构（script/ + cards.cdb + pics/）本就解耦

新架构：`我们的游戏（中文 UI / 卡组系统 / AI / 经典规则配置）→ Adapter → OCGCore（CardScripts + 卡数据库）`

## 3. 评估

### 收益（承认）

| # | 收益 | 影响 |
|---|---|---|
| 1 | 卡效果零边际成本 | 自研路线 Phase 4+7+8 的大部分工作量消失 |
| 2 | 裁定权威性 | 连锁/时点/目标合法性由实战检验过的核心保证 |
| 3 | 卡池扩张上限 | 从 100~150 张 → 理论上全库 |
| 4 | 中文显示不受影响 | YGOCDB 数据继续负责 cn_name/效果文本/原画（见 card-display.md） |

### 成本与风险（参考方案低估的部分）

| # | 风险 | 说明 | 缓解 |
|---|---|---|---|
| 1 | **集成成本** | ocgcore 是 C++ DLL + 二进制消息协议（packet 驱动），无强文档；我们 TS/Node 需 FFI（koffi 等）或自建桥接进程；Windows 构建链未验证 | D1 探针第一道门：先拿到能跑的核心再谈其他 |
| 2 | **Classic Mode 自定规则** | "每回合 ≤3 次特殊召唤"是我们自创规则，core 不认识。只能在 Adapter 层过滤动作（可行前提：人类走我们的 UI、AI 走我们的适配层，所有动作都过我们手）；禁同调/超量/连接靠卡池筛选举制（C1 职责） | D1 探针第二道门必须验证：core 返回的合法操作可被外部过滤 |
| 3 | **AI 搜索变贵** | 自研引擎状态纯 JSON 可 structuredClone；ocgcore 做搜索需"种子+动作序列重放"模拟，Phase 6 架构重设计 | D1 探针第三道门验证确定性重放；AI 可先用 1 层贪心+全重放 |
| 4 | **AGPL-3.0** | ocgcore/CardScripts 均 AGPL。本地自玩无障碍；若公开分发，整个游戏需遵守 AGPL 开源要求。卡图/名称另有 Konami/集英社版权（EDOPro 自声明非官方） | 决策记录在案；公开发布前再评估 |
| 5 | **ocgcore 全量规则的复杂度回流** | core 会返回我们不想要的东西（错过的时点、复杂连锁窗口），UI/AI 要处理的动作空间变大 | Adapter 层做"经典化"裁剪；C1 筛简单卡降低局面复杂度 |

## 4. 决定

1. **D1 探针 = 新关键路径**（`docs/workorders/WO-005-ocgcore-spike.md`），三道 Go/No-Go 门，通过才正式转路线
2. **A1 不停**：继续完成（作为 fallback 引擎 + 规则语义参照 + 测试资产，沉没成本极低）
3. **Phase 4 冻结**：D1 通过 → 取消自研 Effect Engine，开 Adapter 工单（新 Phase 4'）；D1 失败 → 按原计划恢复
4. **C1 / B2 不受影响**：C1 在 ocgcore 路线下语义升级（supported ≈ 有官方脚本 + 经典适合度）；B2 原画体系两路线通用

## 5. 路线对照

| 事项 | 自研路线（A1→4→5→6） | ocgcore 路线（D1→4'→…） |
|---|---|---|
| 规则引擎 | A1（进行中） | ocgcore（现成） |
| 卡效果 | 手写结构化 JSON（周级/百张） | CardScripts（零成本，全库） |
| Classic 限制 | 引擎原生（special_summon_limit 已在配置） | Adapter 过滤 + 卡池筛选举制 |
| AI | 纯 JSON 状态克隆搜索 | 重放模拟搜索（较贵） |
| 关键风险 | 工作量与裁定正确性 | 集成与维护成本 |
| 失败回退 | —— | A1 引擎仍在，随时回 |
