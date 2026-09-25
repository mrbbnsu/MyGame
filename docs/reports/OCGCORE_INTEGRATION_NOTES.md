# OCGCORE 集成笔记（WO-005 / P1）

> 目的：让另一个工程师照着跑通"脱离 EDOPro 客户端调用 ocgcore + CardScripts"。
> 所有结论基于 2026-09-25 实测（版本见 `vendor/VERSIONS.md`），条目均给出源码出处。
> 复现代码：`spike/ocg/`（构建 `build_dll.sh`，绑定 `ocgcore_ctypes.py`，对局 `miniduel.py`）。

## 0. 获取与构建（实测 15 分钟）

1. 下载源码（`git clone` 的 smart-http 协议在当前网络被重置，改用 codeload 源码包）：
   - `https://codeload.github.com/edo9300/ygopro-core/zip/refs/heads/master` → `vendor/repos/ygopro-core/`
   - `https://codeload.github.com/lua/lua/zip/6e22fedb74cf0c9b6656e9fce8b7331db847c605` → 解压为 `ygopro-core/lua/src/`（Lua 是 core 的 git submodule，zip 包不含，需按 submodule SHA 单独取）
   - `https://codeload.github.com/ProjectIgnis/CardScripts/zip/refs/heads/master` → `vendor/repos/CardScripts/`
2. 编译（README 推荐 premake5；本机无 MSVC/CMake，实测用 `pip install ziglang` 的 `zig c++` 一步编出 DLL）：
   ```bash
   bash spike/ocg/build_dll.sh
   # zig c++ -shared -std=c++17 -DOCGCORE_EXPORT_FUNCTIONS -DWIN32 -D_WIN32
   #   -DNOMINMAX -DUNICODE -D_UNICODE -fno-rtti -I. -Ilua/src -Ilua
   #   <根目录16个.cpp> -x c++ <lua/src 精选 .c> -x none -o ocgcore.dll
   ```
   Lua 的 .c 需按 C++ 编译（premake5.lua `compileas "C++"` 同款），并剔除
   `lbitlib/lcorolib/ldblib/linit/loadlib/loslib/ltests/lua.c/luac.c/lutf8lib/onelua`。
3. 冒烟：`python spike/ocg/smoke_test.py` → `OCG_GetVersion()=11.0`。
4. **EDOPro 发行版内的 `ocgcore.dll` 是 32 位 x86**（支持 WinXP 的历史包），64 位
   Python/Node 加载报 `WinError 193`——生产集成必须自编译 64 位核心，发行版包只取
   `cards.cdb` 与 `script/`。
5. 官方 premake 路线（备选）：`scripts/generate.bat`（VS）或
   `premake5 gmake2 && make -Cbuild TARGET=ocgcoreshared`（mingw）。

## 1. 核心入口（C API，ocgapi.h，共 13 个函数）

| 组 | 函数 |
|---|---|
| 信息 | `OCG_GetVersion(int*,int*)` → 实测 11.0 |
| 生命周期 | `OCG_CreateDuel(OCG_Duel*, const OCG_DuelOptions*)` / `OCG_DestroyDuel` / `OCG_DuelNewCard` / `OCG_StartDuel` |
| 处理 | `OCG_DuelProcess` / `OCG_DuelGetMessage` / `OCG_DuelSetResponse` / `OCG_LoadScript` |
| 查询 | `OCG_DuelQueryCount` / `OCG_DuelQuery`（单卡）/ `OCG_DuelQueryLocation`（整区）/ `OCG_DuelQueryField` |

纯 C ABI、无异常跨界，可被任意语言 FFI。核心内部持有全部状态；宿主不接触任何内部指针。

## 2. 初始化 Duel（OCG_DuelOptions，ocgapi_types.h）

```
seed[4] (u64, xoshiro256 种子) | flags (u64) | team1/team2 {startingLP, startingDrawCount, drawCountPerTurn}
cardReader / payload1 | scriptReader / payload2 | logHandler / payload3 | cardReaderDone / payload4 | enableUnsafeLibraries
```
- **所有字段必须显式赋值**（README 明言，含 4 个 payload）。
- `flags` 关键位（ocgapi_constants.h）：`DUEL_TEST_MODE 0x1`（脱离服务器的单进程模拟，探针用此）；
  `DUEL_1ST_TURN_DRAW 0x200` 等规则开关；**规则时代预设**：
  `DUEL_MODE_MR1 0x100`…`DUEL_MODE_MR5 0x4000` 及 `DUEL_MODE_GOAT`、
  `DUEL_MODE_MR1_FORB`（按时代禁 Link/灵摆等）——v2 的"经典节奏"可直接用旧 Master Rule 预设，无需自定义规则。
- 实测：LP8000/起手5、先攻第一回合无抽牌（现行规则）；`tag_swap` 仅在 duelist≠0 的 TAG 布置后才生效。

## 3. 卡牌数据加载（cardReader ← cards.cdb）

- `OCG_DuelNewCard(info)` / 脚本内首次读卡时，core 调 `cardReader(payload, code, OCG_CardData*)`（duel.cpp `read_card`，带 code→data 缓存）。
- 我们的实现：SQLite 查 `expansions/cards.cdb` 的 `datas` 表，映射规则（已抽样验证）：
  - `level & 0xFFFF → level`；`(level>>16)&0xFF → rscale`；`(level>>24)&0xFF → lscale`（灵摆双刻度同列）
  - `type & TYPE_LINK` 时：`def 列 → link_marker`（箭头位图），defense 置 0
  - `setcode` 列 = 至多 4 个 u16 序列（0 结尾），逐 16 位填入 `OCG_CardData.setcodes`
  - `alias`（298 张"当作"指向）原样传递；atk/def 的 `?` = 负值原样传递
  - **拆包责任在宿主**：core 对 level/lscale/rscale/link_marker 是独立字段直接 COPY（duel.cpp `card_data` 装载）
- `cardReaderDone` 在 setcodes 填完后回调（我们用 dict 保活 u16 缓冲防 GC）。
- 宿主还需维护 cdb→数据缓存；core 侧亦有 data_cache，重复读同 code 不会二次回调。

## 4. 脚本加载（scriptReader ← CardScripts）

- **宿主必须预载两个全局脚本**（core 自身不加载任何全局库）：
  `OCG_LoadScript(duel, constant.lua 内容, len, "constant.lua")` 然后 `utility.lua`
  （CardScripts CI 的加载顺序即此）。`utility.lua` 尾部以 `Duel.LoadScript(...)`
  自动链载 `debug_utility/chain/cards_specific_functions/proc_fusion/.../proc_gemini` 全套。
- 之后 core 按需回调 `scriptReader(payload, duel, name)`：卡脚本名固定 **`c{passcode}.lua`**
  （interpreter.cpp `load_card_script`，格式 `c%u.lua`）；`Duel.LoadScript` 传平面文件名（禁止路径分隔符，libduel.cpp 会拦截）。
- 我们的解析顺序：CardScripts 根库 → `official/` → `unofficial/` → `rush/` → `skill/` → `pre-errata/` → `goat/`。
- **通常怪兽没有脚本文件**（c32864.lua 等不存在）——scriptReader 返回失败是正常路径，core 照常建卡。
- EDOPro 谜题模式同款机制可用：StartDuel 之前 `OCG_LoadScript` 一段含
  `Debug.AddCard(code, owner, playerid, loc, seq, pos)` 的 Lua 即可确定性布置场地（P3 探针即此做法）。

## 5. duel message / response 交互

- 驱动循环：`OCG_DuelProcess()` 返回 `END(0)/AWAITING(1)/CONTINUE(2)`；
  AWAITING 时从 `OCG_DuelGetMessage` 解码出待答的 SELECT_* 消息，`OCG_DuelSetResponse` 提交答案，循环。
- **缓冲格式**：每次 GetMessage 返回 `[u32 len][len 字节消息]…` 的串联（duel.cpp `generate_buffer`）；
  **指针下次调用即失效，必须立即拷贝**。
- 消息类型 = `MSG_*` 枚举共 **95 个**（ocgapi_constants.h 207–301 行）。布局**核心仓不带文档**
  （README 只指到 YGOpen 的旧协议），本次从 core 各 writer 提取（`spike/ocg/message_writers.txt`，169 段）。
  通用要点：玩家号 u8；卡引用 = `loc_info{controler u8, location u8, sequence u32, position u32}`；
  效果引用 = `description u64 + client_mode u8`。
- **现行 core 不再发送 MSG_START**，开局状态用 `MSG_RELOAD_FIELD`（162，field.cpp `reload_field_info`）。
- 响应格式（本次实测覆盖）：

| 消息 | 响应 |
|---|---|
| SELECT_IDLECMD / SELECT_BATTLECMD | i32 = `t \| (s<<16)`；idlecmd t: 0召唤 1特召 2表示形式 3放置 4盖放 5发动 6进BP 7EP 8洗牌；battlecmd t: 0攻击链 1攻击 2M2 3EP |
| SELECT_CHAIN | i32：-1=不连锁，否则链索引；唯一可选触发改问 **SELECT_EFFECTYN**（player, code, loc_info, desc），i32 0/1 |
| SELECT_CARD / SELECT_TRIBUTE | i32 type（-1 取消 / 0=u32 索引表），后跟 u32 数量 + 索引 |
| SELECT_PLACE | 每项 3 字节 (player, LOCATION_MZONE/SZONE, seq)；**flag 位=1 表示禁用**（可用位被清零） |
| SELECT_POSITION | i32 = POS_* |

- **契约：core 的 END 仅表示"处理单元耗尽"；胜负终局由宿主在收到 MSG_WIN 后停止驱动**
  （EDOPro 客户端同款行为）。WIN 之后 core 可能还有残留询问窗口，宿主不应再喂新动作。
- 小卡组（<10 张）会在抽牌阶段 deck out 直接 WIN(reason=2)，验证脚本需用正常卡组规模。

## 6. 状态查询（读盘面）

- `OCG_DuelQueryLocation(duel, &len, OCG_QueryInfo{flags, con, loc, seq, overlay_seq})`：
  任意时刻可查（AWAITING 期间尤其实用）。**缓冲首部有 u32 总长前缀**，其后为逐卡字段流。
- 字段格式（card.cpp `CHECK_AND_INSERT_T`）：`[u16 len][u32 tag][value len-4]`；空槽位 = u16 0；
  每张卡首字段必为 QUERY_CODE。注意 `len` 值 = 4+value 长度（**不含 u16 头自身**），
  QUERY_IS_PUBLIC 恒定输出（1 字节），尾部有 QUERY_OVERRIDE(0x80000000) 终结标记。
- P2/P3 已用其验证场上卡 code/表示形式/ATK（含突进 +700 后读出 1900）。

## 7. 已知摩擦与坑（P1~P4 实测汇总）

| # | 摩擦点 | 量化/处置 |
|---|---|---|
| 1 | 发行版 core 是 32 位 | 64 位宿主不可用 → 自编译；zig 方案 ~15 分钟打通，无需装 MSVC |
| 2 | git clone 不可达 | codeload 源码包 + API 查 submodule SHA，等效浅克隆 |
| 3 | Lua 子模块缺失 | zip 包不含 `lua/src`，需按 submodule SHA 单独下载 |
| 4 | 协议无文档 | 95 个 MSG 布局要读 core writer；本次提取 169 段（spike/ocg/message_writers.txt），驱动实现 26 种解码 + 51 种命名 |
| 5 | 查询缓冲两个坑 | 首部 u32 总长前缀；字段 len 不含自身头 |
| 6 | OCG_NewCardInfo.duelist | =0 才是主卡组；非 0 是 TAG 副卡组（静默"丢卡"） |
| 7 | SELECT_PLACE flag 语义 | 位=1 为禁用，与直觉相反 |
| 8 | 唯一可选触发走 EFFECTYN | 不走 SELECT_CHAIN，Adapter 两处都要实现 |
| 9 | WIN 不强制 END | 终局由宿主停止驱动（EDOPro 同款契约） |
| 10 | cdb 版本滞后 | 发行版 cards.cdb 落后 CardScripts master（P4：3 张新卡） |
| 11 | "ProjectIgnis/ocgcore"不存在 | 实际为 edo9300/ygopro-core；架构文档命名需修正 |

## 8. 复跑清单

```bash
bash spike/ocg/build_dll.sh        # 编 64 位 ocgcore.dll
python spike/ocg/smoke_test.py     # API 11.0
python spike/ocg/miniduel.py       # P2 最小对局，9 项断言
python spike/ocg/p3_scripts_duel.py  # P3 六类真实卡效果，10 项断言
python spike/ocg/p4_id_alignment.py  # P4 三源对齐 + C1 卡池
```
