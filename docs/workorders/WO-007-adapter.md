# WO-007：Classic Duel Adapter v0（JSON 协议服务）

> **任务编号 E1 ｜ 执行：worker E（用户指派）。** 依赖：D1 ✅ GO（`reports/D1-acceptance.md`）。
> 目标：把探针验证过的 ocgcore 驱动能力硬化为**正式的 Adapter 服务**——TS 侧（UI/AI）与规则引擎之间的唯一交互面。这是 P2 关键路径，P3（最小 UI）与 P5（AI V0）都建立在它上面。

## 0. 必读（按序）

1. `E:\Game\docs\architecture-v2.md` —— Adapter 在架构中的位置与原则（v2）
2. `E:\Game\docs\reports\D1-report.md` —— 探针结论、摩擦清单（95 消息/26 已解码）、Adapter 形式建议
3. `E:\Game\docs\reports\OCGCORE_INTEGRATION_NOTES.md` —— C API/加载契约/11 项坑（实现时的技术手册）
4. `E:\Game\spike\ocg\` —— 探针源码（**ctypes 绑定 + 26 种消息解码器 = 本工单的种子代码**）
5. `vendor/VERSIONS.md` —— 版本锚定与 DLL 构建方式

## 1. PM 已拍板的决策（不再讨论，直接执行）

| # | 决策 | 理由 |
|---|---|---|
| K1 | v0 实现语言 = **Python**（硬化探针的 ctypes 绑定），服务形态 = **JSON Lines over stdio** 独立进程 | 绑定与解码器已被探针验证（两场对局零失败）；本地单机对性能无要求。**JSON 协议是永久契约**，将来换 C++ 实现不影响 TS 侧 |
| K2 | Adapter **只说 passcode 与规则语义**：状态里卡 = `{code, pos, face, ...}`，不含任何中文文本/图片 | 中文显示数据由 TS 侧按 passcode join `cards_clean.json` 与卡图——双库并存原则（architecture-v2 §2） |
| K3 | **信息隐藏是架构红线**：`get_state(viewer)` 必须只暴露该玩家可见信息（对方手牌内容、背面卡身份必须隐藏为 `code: null`） | UI 与 AI 同权，从架构上杜绝 AI 作弊 |
| K4 | **消息解码层集中一处**（`adapter/decoder.py`），TS 侧零二进制解析 | D1 建议 + 探针教训（布局与 core 版本耦合，回归面要可控） |
| K5 | 首期消息解码覆盖 **≥40 种**（全部 SELECT_*、移动/召唤/战斗/连锁/伤害/阶段流；探针已有 26 种） | D1 摩擦清单 #1 的首期建议量 |

## 2. 交付物

```
adapter/
  service.py        主服务：stdin 读请求行 → stdout 写响应行，生命周期管理
  core_binding.py   ctypes 绑定（硬化自 spike/ocg/ocgcore_ctypes.py；DLL 缺失时给结构化错误）
  decoder.py        消息枚举 → JSON 事件（95 枚举命名齐全，≥40 种完整解码；未知消息 → {type:"UNKNOWN", raw_size})
  protocol.md       协议契约文档（请求/响应/状态/pending 结构全量定义，TS 侧唯一依据）
  selftest.py       无 TS 依赖的自测（进程内直接调 service 函数）
src/adapter/
  client.ts         TS 客户端：spawn 服务 + JSON Lines 解析 + 请求 id 关联 + 类型
  types.ts          协议 TS 类型定义（与 protocol.md 逐条对应）
tests/adapter_integration.test.ts   集成测试（node:test，spawn 真服务）
```

## 3. 协议契约（v0 最小集，写进 protocol.md 并实现）

统一请求 `{id, cmd, ...}`，统一响应 `{id, ok: true, result}` 或 `{id, ok: false, error: {code, message}}`：

| cmd | 入参 | 出参（result） |
|---|---|---|
| `new_duel` | `decks: [number[], number[]]`（passcode 数组）、`opts: {lp, start_hand, seed, mode?}` | `duel_id` + 初始 `state` |
| `get_state` | `viewer: 0\|1` | 完整**该视角**状态 + 当前 `pending`（见下） |
| `respond` | `choice`（pending.choices 的下标或结构化值）、可选 `cancel: true` | 应用后的新 `state`（含新 pending；无 pending 表示等待下一个输入） |

`state` 至少含：`duel_id, turn_player, turn_count, phase, winner, reason, players[2]{lp, deck_count, hand[](viewer 视角决定 code 可见性), monster_zones[5]{code,pos,face,has_attacked?}, spell_trap_zones[5], graveyard[](code), banished[](code), extra_count}`

`pending`：`{type: "SELECT_CARD"|"SELECT_PLACE"|"SELECT_YESNO"|"SELECT_OPTION"|"SELECT_CHAIN"|"SELECT_POSITION"|"SELECT_BATTLE"|"EFFECT_YESNO"|"IDLE", prompt, choices: [...], cancelable: bool}`（按 core 实际消息归一化，未覆盖类型 → `SELECT_OTHER` 并保留原始参数）

## 4. 功能要求

1. DLL 构建可复跑：沿用/封装 `spike/ocg/build_dll.sh`（zig 方案），`adapter/README` 写清一条命令构建
2. cards.cdb / CardScripts 从 `vendor/` 加载，路径可配置（环境变量或 config 文件）
3. **确定性**：同 `seed` + 同 respond 序列 → 事件/状态序列逐字节一致（AI 回放与测试的根基）
4. 健壮性：core 返回异常/未知消息 → 结构化错误返回，服务进程不崩；stdin EOF → 干净退出
5. `new_duel` 前置校验：卡组非空、双方 passcode 数组格式正确（**不做**卡组合法性规则校验——那是卡组系统的工单）

## 5. 验收标准（PM 执行）

1. `python -X utf8 adapter/selftest.py` 全绿 + `npm test`（含集成测试）全绿
2. 集成测试内容必须覆盖：spawn 服务 → new_duel（双方卡组 = 普通怪兽 + ≥2 张效果卡，如 死者苏生/强欲之壶）→ 自动应答循环打完整局 → winner/reason 正确
3. **信息隐藏测试**：viewer=0 的 state 中，p1 手牌每项 `code` 为 null（数量保留）；p1 背面卡 code 为 null
4. **确定性测试**：同 seed 两局 + 同应答脚本 → 两份事件流完全一致
5. 解码覆盖 ≥40 种，`decoder.py` 顶部有覆盖清单注释；`protocol.md` 与 `types.ts` 抽查一致
6. 红线 grep：`src/` 下无二进制解析（无 Buffer 读消息布局的代码）；解码只存在于 `adapter/decoder.py`

## 6. 边界（不做）

UI、AI 决策、卡组合法性规则、中文数据 join、网络对局、观战/录像功能、多对局并发（v0 单对局即可，duel_id 预留）。

## 7. 完成定义（DoD）

验收 1-6 通过 + git 提交（信息：`Adapter v0：JSON 协议服务（E1/WO-007）`；`vendor/` 保持不入库）+ 完成说明给 PM（协议偏离点、解码覆盖清单、已知限制）。
