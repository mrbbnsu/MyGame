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
