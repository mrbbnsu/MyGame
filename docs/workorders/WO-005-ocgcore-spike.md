# WO-005：Phase P 探针 —— ocgcore + CardScripts 集成验证（P1~P4）

> **任务编号 D1 ｜ 执行：worker D（用户指派）。** 依赖：无。
> 背景：`docs/architecture-v2.md`（v2 方向：规则与卡效复用 Project Ignis 生态）。
> 本工单产出的是**决策数据，不是生产代码**。四个探针按序执行（P1→P4），每个都有独立验收与失败条件。
> 时间盒：全程建议 2~4 个工作日当量；单个探针卡住超半天，记录现象后收工汇报，不死磕。

## 0. 必读

1. `E:\Game\docs\architecture-v2.md` —— v2 架构与原则
2. `E:\Game\README.md` —— 项目现状；主键 = 卡片密码 id；cards_clean.json 结构
3. 参考对象（联网查证，非沙箱执行）：ProjectIgnis/EDOPro、ProjectIgnis/ocgcore、ProjectIgnis/CardScripts 的**当前版本实际代码 / README / 头文件 / 示例**——不许凭印象或过时资料设计接口

## P1：获取并理解现有项目

- **输入**：上述三个仓库的实际版本
- **内容**：
  1. Windows 下可用方式：直接用 EDOPro 发行版里的核心（优先），或源码编译
  2. C API：核心入口、初始化 Duel、加载卡牌数据（cards.cdb）、加载 Lua script 的方式与关系
  3. duel message / response 交互机制：客户端如何收到消息、如何提交选择
- **交付**：`vendor/`（核心二进制/源码 + CardScripts + cards.cdb，**全部 gitignore**，附 VERSIONS.md 记录精确版本/commit）+ `docs/reports/OCGCORE_INTEGRATION_NOTES.md`（上述七点逐条）
- **验收指标**：能加载并调用核心（语言不限：Node FFI / C++ 小桥接 exe / Python ctypes，选最快的）；笔记能让另一个工程师照着跑
- **失败条件**：拿不到可用核心且无法构建（记录具体报错与已尝试项）
- **下一步**：失败 → 上报 PM 评估；成功 → P2

## P2：最小 Duel

- **输入**：P1 的核心 + 笔记
- **内容**：完全脱离 EDOPro UI 的最小程序：创建 Duel（LP 8000、起手 5）→ 双玩家小卡组 → 抽牌 → 通常召唤 → 进入 Battle Phase → 攻击 → LP 变化 → 推进回合。普通怪兽即可
- **交付**：`spike/ocg/` 探针代码 + 可复跑的对局 transcript（JSON）
- **验收指标**：不依赖 EDOPro 原客户端，通过 ocgcore 完整走完一场最小决斗且状态正确；记录 core 的先攻抽牌行为（规则版本）
- **失败条件**：API 无法脱离客户端驱动对局
- **下一步**：成功 → P3

## P3：CardScripts

- **输入**：P2 环境
- **内容**：加入 5~10 张简单真实效果卡，覆盖：抽牌 / 破坏怪兽 / 改变 ATK / 墓地特殊召唤 / 简单陷阱 / 简单触发效果。验证 `Card ID → CardScripts → ocgcore → 效果正确执行`
- **验收指标**：零自研效果逻辑，真实卡效果正确执行（每张卡写下实际发生的结算）
- **失败条件**：CardScripts 无法脱离 EDOPro 加载
- **下一步**：成功 → P4

## P4：中文卡库映射

- **输入**：`data/cards_clean.json` + CardScripts 文件名清单 + EDOPro 卡数据库（cdb）
- **内容**：随机抽 20~50 张卡，三方 ID 对齐验证：`YGOCDB id = EDOPro cdb id = c{id}.lua 文件名`
- **交付**：匹配数 / 不匹配数 / 异常原因清单；明确结论：**passcode 能否作为三源统一主键**
- **验收指标**：结论明确且可复核（附抽样明细）
- **失败条件**：系统性 ID 不对齐（零星异常可记录后忽略）

## 最终交付

`docs/reports/D1-report.md`：P1~P4 逐条结论 + 集成摩擦点清单（量化，如消息枚举总量 vs Adapter 首期需覆盖量）+ Adapter 实现形式建议 + **Go / No-Go 建议**。

## Go / No-Go 标准（用户定义，照此判断）

**GO**（全部满足）：ocgcore 能独立运行；CardScripts 能加载；我们能读取并提交决斗选择；中文 Card ID 可靠映射；Adapter 技术路径可接受 → 正式确定主线。

**NO-GO**（仅在明确技术阻塞时）：Windows 构建无法稳定工作；API 无法满足客户端控制；CardScripts 无法脱离 EDOPro 使用；数据映射系统性问题 → 重评自研路线。

⚠️ **不因"看起来集成复杂"提前判 No-Go。** 复杂度本身就是探针要量化的交付物。

## 红线

- 不进 `src/`，不改 A1/B1/B2/C1 任何文件；探针代码隔离在 `spike/ocg/` 与 `vendor/`
- `vendor/` 一律 .gitignore（体积 + AGPL 边界）；版本记录 VERSIONS.md 提交
- 不预设 Adapter 形式——先实测再建议
- 联网命令非沙箱执行；卡住超半天记录后收工

## 完成定义（DoD）

验收（PM 按 P1~P4 指标逐条复核 + 重跑 transcript）通过 + git 提交（信息：`Phase P 探针：ocgcore+CardScripts 集成验证（D1/WO-005）`，只提交报告/VERSIONS/spike 源码）+ 完成说明给 PM。
