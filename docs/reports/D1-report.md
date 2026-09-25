# D1 报告：Phase P 探针 —— ocgcore + CardScripts 集成验证（WO-005）

> 执行：worker D ｜ 日期：2026-09-25 ｜ 结论先行：**建议 GO**。
> 详细技术依据见 `docs/reports/OCGCORE_INTEGRATION_NOTES.md`；探针源码 `spike/ocg/`；
> 版本锚定 `vendor/VERSIONS.md`；可复跑产物 `spike/ocg/out/p{2,3,4}_*.json`。

## 0. 一句话结论

四探针全部通过：64 位 ocgcore（API 11.0）在 Windows 上自编译成功并完全脱离 EDOPro
客户端跑通真实规则对局，CardScripts 官方卡脚本零改动正确结算，三源卡片密码对齐
（C1 经典池 99.73% 可玩、零 ID 错位）。Go 标准五项全部满足。

## 1. P1~P4 逐条结论

### P1 获取并理解现有项目 —— ✅ 通过（验收：能加载并调用核心）
- 命名勘误：所谓 "ProjectIgnis/ocgcore" 不存在；EDOPro 官方 submodule 指向
  **edo9300/ygopro-core**（AGPL-3.0，C API 11.0，2026-09-25 仍在提交）。
- 构建三路实测：①EDOPro 发行版 DLL —— 32 位 x86，64 位宿主不可加载（WinError 193），仅取其 cards.cdb/script；
  ②premake5 官方路线（未走，本机无 VS）；③**pip 装 zig 当编译器，一条命令编出 64 位
  ocgcore.dll（1.75MB），ctypes 冒烟 OCG_GetVersion=11.0** ✅。
- 注意：本机网络 git 协议不通（api/raw/codeload 通），用 codeload 源码包等效浅克隆；Lua 为 core 子模块需按 SHA 单独下载。

### P2 最小 Duel —— ✅ 通过（验收：不依赖 EDOPro 跑完一场且状态正确）
- `spike/ocg/miniduel.py`：40 卡小队（三只通常怪兽），DUEL_TEST_MODE，LP8000/起手5。
- 全自动应答（p0 进取/p1 消极）打完整场：**9/9 断言通过**，0 次 MSG_RETRY。
  通常召唤→表攻直攻→LP 8000→0（4×2000 战斗伤害）→WIN(reason=1)；先攻第 1 回合
  无抽牌（现行规则实证）；transcript `out/p2_transcript.json`（43KB，含全部消息解码）。

### P3 CardScripts —— ✅ 通过（验收：零自研效果逻辑，6 类效果正确执行）
- `spike/ocg/p3_scripts_duel.py`：Debug.AddCard 确定性开局（EDOPro 谜题同款机制），
  7 张真实卡全部经 `official/c{id}.lua` 结算，**10/10 断言通过**，transcript
  `out/p3_transcript.json`：
  | 卡 | 结算（实测） |
  |---|---|
  | 强欲之壶 55144522 | 发动后抽 2 张（记录实际卡码） |
  | 黑洞 53129443 | 结算后双方怪兽区清空（查询验证） |
  | 死者苏生 83764718 | 特召对方墓地 Leotron（SPSUMMONING con=0） |
  | 杀人番茄 83011277 | 被战斗破坏触发，从卡组特召 DARK（第13号墓） |
  | 突进 70046172（陷阱） | 连锁链中指定目标 ATK 1200→1900（查询验证） |
  | 圣防 44095762（陷阱） | 攻击宣言时连锁，破坏对方全部攻表怪 |
- 链路 `Card ID → c{id}.lua → ocgcore → 结局` 全程无一行自研效果代码。

### P4 中文卡库映射 —— ✅ 通过（验收：结论明确可复核，附抽样明细）
- `spike/ocg/p4_id_alignment.py`，固定种子抽 50 张 + C1 卡池全集：
  - 随机 50 张：47 张三方对齐；3 张"YGOCDB/脚本有、发行版 cdb 无"——均为最新卡
    （cdb 是 41.0.2 发行快照，脚本库更新在前），**ID 本身一致，属版本时序差而非错位**。
  - **C1 经典卡池底稿 2599 张：issues=0**；cdb 命中 2486（95.65%），official 脚本
    1907 + 通常怪无脚本 685 → **可玩率 99.73%**（其余 7 张同为最新卡滞后）。
  - 全集：cards_clean 14281 / cdb 13728 / official 脚本 13541。
- **结论：passcode 可以作为 YGOCDB = cdb = c{id}.lua 三源统一主键。**
  （附注：通常怪兽无脚本文件是正常路径；alias 字段"当作"指向 298 张，需在 metadata 层透传。）

## 2. 摩擦点清单（量化）

| # | 摩擦 | 量化 |
|---|---|---|
| 1 | 消息协议无文档，须读 core writer | 消息枚举共 **95 个**；探针已实现 **26 种完整解码**+51 种命名，覆盖 P2/P3 全程（两场对局零未解码消息）。首期 Adapter 建议覆盖 **约 40 种**（全部 SELECT_*、移动/召唤/连锁/伤害/阶段流），其余按需补 |
| 2 | 构建环境 | 本机无 MSVC/CMake/make；`pip install ziglang` 方案 **15 分钟**出 64 位 DLL，零系统安装；官方 premake5 路线保留为备选 |
| 3 | 32 位发行版核心不可 FFI | 必须自编译（一次性成本，已有脚本 `build_dll.sh`） |
| 4 | 网络可达性 | git smart-http 被重置，codeload/API 通道可用（对构建管线无影响，一次性的） |
| 5 | 查询/消息格式细节坑 | QueryLocation 首部 u32 前缀、字段 len 不含自身头、SELECT_PLACE flag 反语义、duelist≠0=TAG 副卡组、WIN 不强制 END、唯一可选触发走 EFFECTYN —— 共 11 项已全部记录并绕过（NOTES §7） |
| 6 | cdb 版本滞后 | 3/50 抽样 + 池内 7 张新卡；处置：cdb 随 EDOPro 发行版/自家构建管线定期刷新，或接受新卡延后入库 |
| 7 | 消息解码与 core 版本耦合 | 布局取自 core writer，升级 core 需回归（探针代码即回归集） |

## 3. Adapter 实现形式建议

**推荐：C++ sidecar 进程 + JSON over stdio/本地 socket；备选：TS 侧 FFI（koffi/napi）。**

| 方案 | 实测依据 | 权衡 |
|---|---|---|
| **C++ sidecar（推荐）** | 探针证明：宿主只需实现 cardReader/scriptReader/logHandler 三个回调 + cdb/文件读取。sidecar 进程内直接读 cdb(SQLite) 与脚本文件（**回调全部内部化，Node 不接触二进制**），对外只吐结构化 JSON（对局状态/可选动作）与收 JSON（玩家选择）——与架构图"JSON 结构化协议唯一交互面"一致 | 多一个进程生命周期管理；调试跨进程；但协议边界=JSON，TS 侧零原生代码 |
| TS FFI（备选） | 本次用 Python ctypes 证明 C ABI 极易绑定（绑定+驱动 ~500 行，1 天内含调试）；koffi 同类能力 | 回调（scriptReader 高频调用）需在 JS 侧持函数指针与缓冲生命周期；95 消息解码若放 TS，布局改动回归面更大 |
| 不推荐 | — | 自研规则/解释消息之外再造核心包装层（例如把 core 静态链进 Node addon）：构建复杂度最高，收益与 sidecar 相同 |

无论哪种形式，**消息解码层（95 个 MSG 的二进制布局）必须集中一处**（探针的
`miniduel.py` 解码器即雏形），禁止散落在 UI/AI。

## 4. Go / No-Go 建议：**GO**

对照用户定义的 GO 标准：

| # | 条件 | 结果 |
|---|---|---|
| 1 | ocgcore 能独立运行 | ✅ P2/P3：脱离 EDOPro 全程驱动对局 |
| 2 | CardScripts 能加载 | ✅ P3：官方脚本零改动正确结算（含触发/陷阱/连锁） |
| 3 | 我们能读取并提交决斗选择 | ✅ P2/P3：解码 95 枚举中 26 种布局、6 类 SELECT 响应，两场对局 0 非法应答 |
| 4 | 中文 Card ID 可靠映射 | ✅ P4：passcode 三源主键成立，C1 池 99.73% 可玩、零错位 |
| 5 | Adapter 技术路径可接受 | ✅ §3：sidecar 首选路径已由探针全程验证，工作量集中在消息解码层（已知 95 个枚举、26 种已实现） |

No-Go 条件（构建不稳/API 不可用/脚本不可脱离/映射系统性问题）均未触发。
"集成复杂"的部分（消息布局、加载契约）已全部量化并沉淀为可复用代码与笔记，
不存在未探明的技术黑域。

## 5. 给主线的建议（非工单，供 PM 参考）

1. 正式立项 v2 Adapter 时沿用探针的层划分：`core 绑定/解码层`（吃二进制）与
   `JSON 网关层`（出结构化状态）分离。
2. "Classic"规则时代直接试 `DUEL_MODE_MR1/GOAT` 等预设（core 原生支持旧 Master Rule
   +按时代禁卡位），无需任何自定义规则——与 v2 §3 一致。
3. cdb 刷新机制与 metadata 层（enabled/pool/ai_tags）按 v2 §2 双库并存方案推进。
4. 架构文档中 "ProjectIgnis/ocgcore" 建议改为 "edo9300/ygopro-core（俗称 ocgcore）"。
