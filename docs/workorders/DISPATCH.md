# 工单分发命令（PM 维护）

> **状态（2026-09-25）：三单已由用户派发完毕，本文仅作存档，勿再分发。**
> 编号对照：worker A → A1 = WO-001（规则引擎）；worker B → B1 = WO-002（卡图）；worker C → C1 = WO-003（卡池初筛）。
> 秘书 worker（PM 直接控制的小改动子代理）见 `SECRETARY.md`。

---

## 发给【规则引擎 Worker】

```
你是 Classic Duel 项目的实现 worker。工作目录：E:\Game（Windows + Git Bash，Node ≥ 24 已装好）。

任务：完成工单 WO-001（Phase 3 最小规则引擎 + 测试套件）。

第一步必读（按序，读完再动手）：
1. E:\Game\docs\workorders\WO-001-phase3-rule-engine.md  ← 本任务完整定义：目标、接口契约、规则细节、测试清单、验收标准
2. E:\Game\docs\v1-rules.md                              ← 冻结版规则基准
3. E:\Game\src\core\ 下的 6 个 .ts 文件                    ← 已定型的状态模型，禁止重写，只可增量扩展

硬性要求（工单里有完整版，此处是红线摘要）：
- 零 npm 依赖；TS 用可擦除语法（不用 enum/namespace/参数属性）；测试用 node:test，npm test 必须全绿
- 接口契约一字不差：createDuel / legalActions / applyAction + 七种 GameAction（工单第 3 节）
- 四条架构红线：一切卡牌移动走 moveCard、一切战斗走 resolveAttack、一切 LP 变化走 changeLp、applyAction 对非法动作必须 throw
- 测试用例按工单第 6 节清单逐条实现且命名一致（PM 按名验收）
- 只新增 src/engine/ 与 tests/ 下文件；不改 src/core/、不改 docs/（TASKS.md 状态行除外）、不实现魔法陷阱/效果/连锁

遇到工单没覆盖的规则问题：以 docs/v1-rules.md 为准；仍无答案就在完成说明里记录你的决定，不要静默发挥。卡壳就停下汇报，不要扩大范围。

完成定义（全部满足才算完）：
1. npm test 全绿
2. git 提交，信息：Phase 3: 最小规则引擎 + 测试（WO-001）
3. 把 docs/TASKS.md 工单索引里 WO-001 的状态改为「已完成」
4. 完成说明（回复给 PM）：文件清单、相对工单的任何偏离及原因、遗留问题
```

---

## 发给【卡图 Worker】

```
你是 Classic Duel 项目的工具 worker。工作目录：E:\Game（Windows + Git Bash，Python 3.11）。

任务：完成工单 WO-002（卡图下载器）。

第一步必读：E:\Game\docs\workorders\WO-002-card-images.md ← 完整定义（命令行参数、跳过/重试/报告格式、验收标准）

环境注意（重要，实测结论）：
- 本机 bash 里联网命令必须以非沙箱方式执行；DNS 解析失败 ≠ 域名错误，先换执行方式再怀疑数据源
- Python 一律用 python -X utf8 运行（Windows 控制台编码）
- 先用 5 张卡小样本验证 YGOPRODeck API 响应结构与图片直链，禁止假设字段名；API 整体不可达就停下汇报，不要瞎换源

硬性要求：
- 只新增 tools/download_images.py 与 data/images/；不改 cards_clean.json，不碰 src/
- 卡图本地存储，文件名 = 卡片密码.jpg，禁止热链；已有文件跳过；单张失败重试 2 次不中断批次；请求间隔 ≥ 200ms
- 本工单只要求 --sample 20 的样本量，禁止全库 14281 张跑批（全库由 PM 另行批准）

完成定义：
1. 工单第 4 节验收 1-5 全部自测通过
2. .gitignore 增加 data/images/（样本图不入库）
3. git 提交，信息：Phase 2: 卡图下载器（WO-002）
4. 完成说明（回复给 PM）：实际 API 字段结构记录、failed 卡及原因、实现中的补充决定
```

---

## 发给【卡池初筛 Worker】

```
你是 Classic Duel 项目的数据 worker。工作目录：E:\Game（Windows + Git Bash，Python 3.11）。

任务：完成工单 WO-003（V1 卡池机器初筛打标）。

第一步必读（按序）：
1. E:\Game\docs\workorders\WO-003-v1-pool-screening.md ← 完整定义（筛选规则、黑名单来源、输出格式、验收标准）
2. E:\Game\docs\effect-system.md 第 11 节（卡牌准入清单，黑名单的依据）
3. E:\Game\README.md 的 cards_clean.json 字段表（注意 type 位是 Master Duel 布局，勿按旧 ygocore 常量解读）

硬性要求：
- 只做客观规则过滤，不做效果语义理解；效果文本只用于关键词黑名单
- 黑名单词可补充明显同义词，但每加一个都要记进完成说明
- 幂等：连跑两次输出完全一致
- 产出：tools/screen_v1_pool.py + data/v1_pool.json + data/v1_pool_stats.md
- 只改 tools/ 和 data/，不碰 src/ 和 docs/

完成定义：
1. 工单第 3 节验收 1-5 全部自测通过
2. git 提交，信息：V1 卡池机器初筛（WO-003）
3. 完成说明（回复给 PM）：各级数量统计、补充的黑名单词、异常卡记录
```

---

## 发给【卡面 Worker B】—— B2（2026-09-25 新增，卡面策略变更后）

```
你是 Classic Duel 项目的工具 worker B（继续负责卡面资源线）。工作目录：E:\Game（Windows + Git Bash，Python 3.11）。

任务：完成工单 B2（WO-004：卡面资源体系 V2 —— 原画下载 + 简中实体图可得率）。

背景：B1 验收通过后卡面策略已变更（见 E:\Game\docs\card-display.md）：游戏核心展示改用「原画 + 中文数据自渲染卡面」，实体卡图降为详情页资源。你只做数据侧，不做游戏内渲染。

第一步必读（按序）：
1. E:\Game\docs\card-display.md —— 新策略（L1 原画 / L2 简中实体图 / L3 英文实体图三层）
2. E:\Game\docs\workorders\WO-004-card-art.md —— 本任务完整定义（探针要求、交付物、验收）
3. E:\Game\tools\download_images.py —— 你 B1 的实现，CLI 与报告格式保持一致

红线提醒：
- 一切 URL 形态先探针实测：/ygoimg/sc/{id}.webp 和 !art 参数都是待验证假设（!art 可能是路径后缀也可能是查询参数），用 89631139 等已知 id 实测后再写批量逻辑
- 先查 data/cards_raw.json 是否自带各语言发行/图片字段——若自带，简中可得率统计零网络请求完成
- 只动 tools/download_art.py、data/art/、data/sc_coverage.{json,md}；不动 B1 的文件；L2/L3 不批量下载；L1 只做样本量
- 联网命令非沙箱执行；Python 一律 python -X utf8；API 整体不可达就停下汇报

完成定义：
1. 工单第 4 节验收 1-5 自测通过
2. data/art/ 加入 .gitignore；git 提交（信息：卡面资源 V2：原画下载 + 简中可得率（B2/WO-004））
3. 完成说明（回复 PM）：探针确切结论（URL 形态+格式+!art 行为）、日/英目录探测结果、cards_raw.json 字段结论、可得率口径与数字、failed 与补充决定
```

---

## 发给【探针 Worker D】—— D1（2026-09-25 新增，v2 路线关键路径）

```
你是 Classic Duel 项目的集成探针 worker D。工作目录：E:\Game（Windows + Git Bash，Node ≥ 24 / Python 3.11 / 可用 C++ 工具链自行确认）。

任务：完成工单 D1（WO-005：Phase P 探针——ocgcore + CardScripts 集成验证，P1~P4）。

背景：项目已定 v2 方向（E:\Game\docs\architecture-v2.md）：规则与卡牌效果复用 Project Ignis ocgcore + CardScripts，不再自研。你的探针回答"这条路能不能走通"，产出决策数据，不是生产代码。

第一步必读（按序）：
1. E:\Game\docs\architecture-v2.md —— v2 架构与原则
2. E:\Game\docs\workorders\WO-005-ocgcore-spike.md —— P1~P4 完整定义（每步的输入/内容/验收/失败条件/下一步）
3. E:\Game\README.md —— 项目现状与数据主键（卡片密码 id）

关键纪律：
- P1 必须读当前版本实际代码/README/头文件，禁止凭印象设计接口
- 四探针串行 P1→P4；单个卡住超半天，记录现象收工汇报，不死磕
- vendor/ 一律 gitignore（体积+AGPL 边界），版本写 vendor/VERSIONS.md 并提交
- 探针代码隔离在 spike/ocg/，不进 src/，不动其他 worker 的文件
- 不预设 Adapter 形式；联网命令非沙箱执行
- ⚠️ 不因"看起来集成复杂"提前判 No-Go——复杂度量化本身是交付物

完成定义：
1. docs/reports/OCGCORE_INTEGRATION_NOTES.md（P1 七要素）+ docs/reports/D1-report.md（P1~P4 结论 + 摩擦量化 + Adapter 形式建议 + Go/No-Go 建议）
2. git 提交（信息：Phase P 探针：ocgcore+CardScripts 集成验证（D1/WO-005）），只提交报告/VERSIONS/spike 源码
3. 完成说明（回复 PM）：四探针逐条结论、Go/No-Go 建议、最大摩擦点
```

---

## 发给【WindBot 调查 Worker】—— D2（可在 D1 的 P1 笔记之后做，用户指派同一人或另一人）

```
你是 Classic Duel 项目的技术调查 worker。工作目录：E:\Game（Windows + Git Bash）。

任务：完成工单 D2（WO-006：WindBot 技术调查）。纯调查，不写采用代码。

第一步必读：
1. E:\Game\docs\workorders\WO-006-windbot-evaluation.md —— 七个调查问题与结论格式
2. E:\Game\docs\architecture-v2.md —— 我们的 Adapter 架构（评估复用边界时对照）

纪律：clone 到 vendor/（gitignore，版本记 vendor/VERSIONS.md）；结论必须基于当前版本实际代码并附文件路径证据；第 6 问（Deck Executor vs 通用逻辑占比）要有量化数据；联网非沙箱执行。

完成定义：
1. docs/reports/WINDBOT_EVALUATION.md（七问逐条 + 对 AI V0 的建议 + 结论四选一：USE / PARTIAL_USE / REFERENCE_ONLY / NOT_SUITABLE）
2. git 提交（信息：WindBot 技术调查（D2/WO-006））
3. 完成说明（回复 PM）：结论 + 与 Adapter 的边界划分建议
```

---

## 发给【Adapter Worker E】—— E1（2026-09-25 新增，D1=GO 后的 P2 关键路径）

```
你是 Classic Duel 项目的 Adapter worker E。工作目录：E:\Game（Windows + Git Bash，Node ≥ 24 / Python 3.11）。

任务：完成工单 E1（WO-007：Classic Duel Adapter v0——JSON 协议服务）。

背景：D1 探针已验收判定 GO（E:\Game\docs\reports\D1-acceptance.md）——ocgcore+CardScripts 正式成为规则主线。你把探针验证过的驱动能力硬化成正式 Adapter 服务：TS 侧（UI/AI）与规则引擎之间的唯一交互面。P3 最小 UI 和 P5 AI V0 都建在它上面。

第一步必读（按序）：
1. E:\Game\docs\workorders\WO-007-adapter.md —— 本任务完整定义（PM 已拍板的 5 项决策 K1~K5、协议契约、验收标准）
2. E:\Game\docs\architecture-v2.md —— 架构原则
3. E:\Game\docs\reports\D1-report.md 和 OCGCORE_INTEGRATION_NOTES.md —— 探针结论与技术手册（11 项坑都在里面）
4. E:\Game\spike\ocg\ —— 探针源码（ctypes 绑定 + 26 种消息解码器 = 你的种子代码）
5. vendor\VERSIONS.md —— 版本锚定与 DLL 构建（zig 方案）

关键纪律：
- K1~K5 拍板项直接执行不重议（Python v0 / JSON Lines over stdio / 只说 passcode / 信息隐藏红线 / 解码集中一处 ≥40 种）
- vendor/ 不入库不改动；DLL 用现成构建脚本或封装它，不重复造
- TS 侧零二进制解析；测试用 node:test（集成测试 spawn 真服务）
- 不做 UI/AI/卡组合法性/中文 join（后续工单的事）
- 卡住超半天记录后收工汇报

完成定义：
1. 工单第 5 节验收 1-6 自测通过（含信息隐藏与确定性两个专门测试）
2. git 提交（信息：Adapter v0：JSON 协议服务（E1/WO-007））
3. 完成说明（回复 PM）：协议偏离点、解码覆盖清单、已知限制
```

---

## 发给【UI Worker】—— F1（2026-09-25 新增，E1 验收通过后的 P3）

```
你是 Classic Duel 项目的 UI worker（若你就是 E1 的 worker，继续做上下文最省）。工作目录：E:\Game（Windows + Git Bash，Node ≥ 24 / Python 3.11）。

任务：完成工单 F1（WO-008：最小 UI——浏览器完整打一局）。

背景：Adapter v0 已验收通过（E:\Game\docs\reports\E1-acceptance.md），JSON 协议就绪。你做玩家实际能打的界面：双人热座、从 8000 LP 完整对局到胜负。丑没关系，完整和正确是唯一标准。

第一步必读（按序）：
1. E:\Game\docs\workorders\WO-008-minimal-ui.md —— 本任务完整定义（K1~K6 拍板项、交付物、验收）
2. E:\Game\adapter\protocol.md —— 协议唯一依据
3. E:\Game\docs\card-display.md —— 卡面三层策略（场上=原画+中文自渲染）
4. E:\Game\src\adapter\client.ts —— 现成的 Adapter TS 客户端，直接用

关键纪律：
- 零 npm 依赖、无构建步骤：node 服务跑 TS（Node ≥24 原生），浏览器端纯 JS ES Modules
- UI 一切经本地服务 /api，前端不碰二进制、不 spawn 进程；服务只监听 127.0.0.1
- pending 全类型都要能操作（含 cancelable 的取消）；viewer 跟随 turn_player（K6）
- 两套预设卡组从 data/v1_pool.json（reason=OK）挑：经典普通怪兽为主+E1 验证过的效果卡，各 40 张；原画用 python -X utf8 tools/download_art.py --ids 预下载
- 无图卡（100268001/003/201/010 等）用统一占位图
- npm test 保持全绿（新增 /api 端点测试）

完成定义：
1. 工单第 3 节验收 1-5 自测通过
2. git 提交（信息：最小 UI：浏览器完整打一局（F1/WO-008））
3. 完成说明（回复 PM）：pending 各类型的实测情况、协议偏离点、已知限制
```
