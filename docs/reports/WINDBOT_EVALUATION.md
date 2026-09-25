# WindBot 技术调查（WO-006 / D2）

> 执行：worker D ｜ 日期：2026-09-25 ｜ 结论先行：**REFERENCE_ONLY（只作设计参考）**。
> 对象：ProjectIgnis/windbot（"WindBot Ignite"，IceYGO WindBot 的 EDOPro 协议移植版），
> commit `bffe6b62679c8b2fafea8f59740e03a132517da4`（master，2026-08-27），
> 源码 clone 于 `vendor/repos/windbot/`（gitignore，版本见 `vendor/VERSIONS.md`）。
> 下文路径均相对该目录；行数为当前版本实测（C#，共 143 文件 / 96,002 行）。
> 许可证：AGPL-3.0（COPYING；与 ocgcore/CardScripts 同代，本地自玩无碍，公开分发需遵守 AGPL）。

## 1. 它如何与 duel engine 通讯（协议、进程模型）

**独立进程的 TCP 网络玩家，不直连 ocgcore**——中间隔着 YGOPro/EDOPro 服务器（房主进程）：

- 入口 `Program.cs:24-56`：单局模式（命令行 host/port）或 `ServerMode`（HTTP 端口 2399，批量造 bot）。
- 连接 `Game/GameClient.cs:52-95`：`new YGOClient()` → `Connection.Connect(host, port)`，
  握手按 YGOPro 房间协议发 `CtosMessage.PlayerInfo`（20 字节 Unicode 名）+ `JoinGame`（pro version + 房间密码）。
- 传输层 `YGOSharp.Network/AsyncYGOClient.cs`（消息 = 1 字节 CtosMessage + payload）、
  `AsyncBinaryClient.cs:130-137`（帧头：客户端方向 u16 长度；服务端方向 u32；另有 `AsyncNetworkServer.cs`）。
- 消息语义与 D1 探到的 ocgcore `MSG_*`（95 个）**同源**（WindBot 侧叫 `StocMessage`/`GameMessage`，
  枚举定义在 `YGOSharp.Network/Enums/`），但传输模型是"房间客户端 ↔ YGOPro 服务器"，
  服务器再驱动内嵌 ocgcore——**不是进程内绑定**。

## 2. 它如何获取合法动作

与我们的 Adapter 计划完全同构：**合法动作 = 服务器 SELECT_* 消息的内容**，不是自己算的：

- `Game/GameBehavior.cs`（2148 行）：`_messages`/`_packets` 字典分发（106-200 行注册），
  解析 SELECT_IDLECMD/BATTLECMD/CARD/CHAIN/POSITION 等，把可执行项填进结构化列表。
- 可执行列表载体：`ExecutorBase/Game/MainPhase.cs`（SummonableCards / SpecialSummonableCards /
  ActivableCards+ActivableDescs / MonsterSetableCards / ReposableCards / SpellSetableCards +
  CanBattlePhase/CanEndPhase）与 `BattlePhase.cs`（AttackableCards、ActivableDescs、CanMainPhaseTwo）；
  场面状态在 `ExecutorBase/Game/ClientField.cs` + `ClientCard.cs`，对局总状态 `Duel.cs`（240 行）。
- 即：WindBot 从不需要"判断合法性"——core 的 SELECT 消息已经枚举了合法项，AI 只做挑选
  （与 D1 P2/P3 探针驱动所见一致）。

## 3. 它如何选择动作（决策结构）

**有序规则表 × 通用默认函数 × 每卡组覆写**，三层：

1. **注册顺序即优先级**：Deck Executor 构造函数里 `AddExecutor(ExecutorType.X, [CardId,] 函数)`
   生成 `CardExecutor` 列表（`ExecutorBase/Game/AI/CardExecutor.cs`，17 行：CardId+Type+Func）。
   ExecutorType 共 15 种动作类目（`ExecutorBase/Game/AI/ExecutorType.cs`：Summon/SpSummon/
   Activate/Repos/MonsterSet/SpellSet/GoToBattlePhase/GoToMainPhase2/GoToEndPhase/Surrender…）。
2. **决策循环**：`ExecutorBase/Game/GameAI.cs`（1236 行）`OnSelectIdleCmd`（477 行起）/
   `OnSelectBattleCmd`（228 行起）：**外层遍历 Executors（按优先级），内层遍历当前动作列表**，
   命中即返回（每次应答只做一个动作，靠服务器再次询问推进）。过滤逻辑 `ShouldExecute`
   （GameAI.cs:1208）：卡片 id/效果 desc 匹配、被无效化预判、防重复选择等。
3. **两层决策体**：
   - 通用层 `ExecutorBase/Game/AI/DefaultExecutor.cs`（1,829 行，**62 个 `Default*` 默认决策**：
     DefaultMonsterSummon/DefaultMonsterRepos/DefaultHeavyStorm/DefaultDarkHole/DefaultTrap/
     DefaultDontChainMyself/DefaultSolemnJudgment/灰流丽/墓穴指名者…）；
   - 专用层每卡组覆写：示例 `Game/AI/Decks/DoEveryThingExecutor.cs`（47 行）= 全默认 +
     2 个 CardId 常量即可成军；`OldSchoolExecutor.cs`（109 行）给经典卡逐个 `AddExecutor(Activate, CardId.X, DefaultX)`；
     现代展开卡组则长至 3,000-6,000 行（AlbazExecutor 5,861 行 / LabrynthExecutor 4,352 行）。
   - 选择类应答（选卡/选位置/选选项）通过覆写 `OnSelectCard/OnSelectPlace/OnSelectOption` 等钩子
     （基类 `ExecutorBase/Game/AI/Executor.cs`，318 行）。

## 4. 是否可以作为我们的 AI V0（直接用 / 包一层用）

**不能直接用，也不建议包一层用。** 三个结构性障碍：

1. **进程/组件模型不符**：WindBot 必须连一个 YGOPro 服务器才有对局（§1）；我们的 v2 架构
   （architecture-v2.md §1/§2）是"UI/AI → Adapter → ocgcore DLL"单进程栈，没有也不想要
   YGOPro 服务器这一层。引入服务器只为喂 WindBot，违背 Adapter 唯一交互面原则，且
   C#/.NET 运行时整栈进入部署。
2. **决策与卡组强绑定**：官方 README 明言 "Decks for this bot player **must** be specifically
   prepared and compiled as individual executors"；我们的经典卡池（C1 底稿 2,599 张）没有任何
   现成 executor，逐卡组写 C# 等于把 AI 工作量变成永久性的脚本工程（见 §6 占比）。
3. **决策质量定位**：官方自述 "simple, deterministic artificial intelligence"——规则表 +
   优先级 + 默认函数，与 AI V0 目标（heuristic 打完一局、零非法操作）**风格一致**，但这正是
   我们可以按同一设计自己实现的（量级见 §6：通用部分仅 ~1.2 万行，其中决策默认函数约 1,800 行）。

## 5. 通信层是否可以复用（与我们 Adapter 的关系）

**传输层不复用；语义层与解析结构高度可参考。**

- 不复用：`YGOSharp.Network`（983 行）是 TCP 客户端 + YGOPro 房间握手（JoinGame/PlayerInfo/
  房间密码），与我们的"进程内调用 ocgcore.dll + 内存缓冲"（D1 NOTES §5：`[u32 len][消息]` 缓冲、
  `OCG_DuelGetMessage/SetResponse`）是两个世界。
- 高价值参考：
  - **消息语义对照表**：`YGOSharp.Network/Enums/` 的 StocMessage/GameMessage/CTOS 枚举 + 
    `GameBehavior.cs` 的 2148 行分发/解析 = 一份"core 消息 → 客户端该回什么"的参考实现，
    与 D1 的 `spike/ocg/message_writers.txt`（core 侧 writer）正好互为对账（writer↔parser 双向验证）。
  - **"SELECT→结构化可执行列表→决策→响应"的分层**（MainPhase/BattlePhase/ClientField/GameAI）
    正是我们要的 Adapter 内部结构模板；其"优先级规则表 + 默认决策 + 覆写"三层也是 AI V0
    的现成设计蓝本。
- 结论：按 architecture-v2.md 的边界，WindBot 代码不进 Adapter；它的**结构进设计文档，个别
  枚举/解析写法进实现时的参考书签**。

## 6. Deck Executor vs 通用逻辑占比（量化）

按当前源码逐文件统计（C# 行数，`wc -l`）：

| 层 | 位置 | 文件数 | 行数 | 占比 |
|---|---|---|---|---|
| **Deck Executors（每卡组专用）** | `Game/AI/Decks/` | **66** | **84,197** | **87.7%** |
| 通用 AI 框架（状态+决策骨架+默认函数） | `ExecutorBase/`（Game/AI、Game、OCGWrapper） | 46 | 7,491 | 7.8% |
| 协议消息解析（→AI 状态） | `Game/`（GameBehavior 等 5 文件，不含 Decks） | 5 | 2,469 | 2.6% |
| 网络传输 | `YGOSharp.Network/` | 14 | 983 | 1.0% |
| 入口/配置 | 根目录 Program/Config/WindBot 等 | 12 | 664 | 0.7% |
| 合计 | — | 143 | 96,002 | 100% |

- **Deck 专用 : 通用 ≈ 84,197 : 11,805 ≈ 7.1 : 1**。
- 专用层内部也极不均匀：最小 36 行（MokeyMokeyExecutor，几乎全默认）→ 最大 5,861 行
  （AlbazExecutor）；现代卡组普遍 3,000+ 行/个。
- 通用层中真正"决策知识"集中在 `DefaultExecutor.cs`（1,829 行 / 62 个 Default* 函数）与
  `AIUtil.cs`（工具判定）；其余是数据结构（Enums 929 行、ClientField/ClientCard 等）。

## 7. 使用任意自定义卡组时的限制（无 Deck Executor 时）

- **没有"纯默认兜底"机制**：`Game/DecksManager.cs:70-88` `Instantiate()` —— deck 名在注册表
  中找不到时，**随机加载一个 `Level=="Normal"` 的现成 executor**（"Deck not found, loading
  random: …"）。即任意卡组跑起来≠通用 AI，而是"穿着别人剧本打牌"：召唤/发动决策与手牌内容
  基本无关（规则表按硬编码 CardId 匹配，自定义卡的 id 不在任何表里 → 全部落空），只剩
  DefaultExecutor 里与 id 无关的默认行为（如 DefaultMonsterSummon 的泛型召唤、OnSelectPlace
  的泛型选址）还在起作用——表现接近"随机路人对局"，且不可预期。
- 卡组文件本身也要配套：`Decks/AI_*.ydk`（60+ 份）按 executor 的 `[Deck("名","文件","难度")]`
  特性（`ExecutorBase/Game/AI/DeckAttribute.cs`）关联。
- 对我们的含义：AI V0 若按 WindBot 模式自研（Adapter 喂合法动作 → 我们的 TS 规则表决策），
  **必须自带"无卡组脚本也能打"的默认层**——WindBot 的 62 个 Default* 函数 + 
  DoEverything/OldSchool 两个极简 executor 是最好的抄写对象（设计抄写，不是代码移植：
  我们是 TS/Adapter，它是 C#/网络客户端）。

## 结论：REFERENCE_ONLY

四选一对比：
- USE ✗：进程模型（需 YGOPro 服务器）与栈（.NET）不符，决策层与卡组硬绑定（87.7%）。
- PARTIAL_USE ✗：唯一可复用的"通信层"（983 行 TCP）恰是我们架构里不存在的东西；
  消息解析虽同语义，但我们 Adapter 的解码层在 D1 已按 core writer 自建（26 种布局已实现），移植 C# 反而引入第二次维护面。
- **REFERENCE_ONLY ✓**：三层决策设计（优先级规则表 / 62 个默认决策 / 每卡组薄覆写）、
  "SELECT→可执行列表→决策→响应"的分层、GameBehavior↔message_writers 互为对账——
  这三样直接进 AI V0 与 Adapter 的设计输入。
- NOT_SUITABLE ✗：不至于——AGPL 同代、语义同源、设计同构，参考价值实在。

## 对 AI V0 的具体建议

1. **照抄结构，不抄代码**：AI V0 = "Adapter 喂 MainPhase/BattlePhase 结构化可执行列表 →
   TS 有序规则表决策 → 回响应"。规则表条目类型直接对齐 ExecutorType 的 15 种动作类目。
2. **先实现"Default 层"**：目标卡池（经典 2,599 张）里效果怪/魔陷的通用处理
   （泛型召唤/直攻/常规魔陷时机），对齐 DefaultExecutor 的 62 个函数中与我们卡池相关的子集
   （HeavyStorm/DarkHole/Raigeki/MonsterSummon/MonsterRepos/Trap 等经典卡都在列）；
   单卡特判只在效果默认值不对时逐卡加——这正是 WindBot executor 随卡组膨胀的反面教材
   （87.7% 行卡在专用层）。
3. **零非法操作天然达成**：合法性由 core 的 SELECT 枚举保证（D1/P2-P3 已验证），AI 永远
   在合法集内挑选；需要防的只有"死循环/空过"——参考 WindBot 的 Surrender/防重复机制
   （GameAI.cs:44、1208）。
4. Adapter 侧留一个 `AI 视角状态` 输出（隐藏手牌等私有信息过滤），供 AI V0 与未来
   V1（搜索/clone）共用同一状态源——WindBot 的 ClientField/ClientCard 结构是字段清单的现成参考。
