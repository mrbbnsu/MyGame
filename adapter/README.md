# Classic Duel Adapter v0（E1/WO-007）

TS 侧（UI/AI）与 ocgcore 规则引擎之间的唯一交互面：JSON Lines over stdio 独立进程。
协议契约见 **protocol.md**（TS 侧唯一依据）；TS 类型在 `src/adapter/types.ts`，
客户端在 `src/adapter/client.ts`。

## 一条命令构建 DLL（zig 方案，一次性）

```bash
pip install ziglang          # zig 当 C++17 编译器（无需 MSVC/CMake）
bash spike/ocg/build_dll.sh  # -> spike/ocg/out/ocgcore.dll（64 位）
```

数据源（不入库，复现见 `vendor/VERSIONS.md` 与
`docs/reports/OCGCORE_INTEGRATION_NOTES.md §0`）：

- `vendor/edopro/ProjectIgnis/expansions/cards.cdb`
- `vendor/repos/CardScripts/`（constant.lua/utility.lua + official/ 卡脚本）

## 运行

```bash
python -X utf8 adapter/service.py                 # stdio 服务（TS 经 client.ts spawn）
python -X utf8 adapter/selftest.py                # 自测（无 TS 依赖，43 项断言）
npm test                                          # TS 集成测试（spawn 真服务）
```

路径配置（优先级：CLI 参数 > 环境变量 > 仓库默认值）：

| 目标 | CLI | 环境变量 | 默认 |
|---|---|---|---|
| ocgcore.dll | `--dll` | `CLASSIC_DUEL_DLL` | `spike/ocg/out/ocgcore.dll` |
| cards.cdb | `--cdb` | `CLASSIC_DUEL_CDB` | `vendor/edopro/ProjectIgnis/expansions/cards.cdb` |
| CardScripts 根 | `--scripts` | `CLASSIC_DUEL_SCRIPTS` | `vendor/repos/CardScripts` |

## 代码地图（二进制知识只在 Python 侧）

| 文件 | 职责 |
|---|---|
| `service.py` | JSON Lines 服务：请求分发、驱动循环、状态构建、视角隐藏（K3）、pending 归一化 |
| `decoder.py` | 全部二进制布局知识：95 个 MSG 枚举命名、79 种消息解码、core 应答编码（K4） |
| `core_binding.py` | ctypes 绑定 + cdb/脚本源 + 结构化错误（硬化自探针 `spike/ocg/`） |
| `selftest.py` | 进程内自测：完整局、信息隐藏、确定性、健壮性 |
| `protocol.md` | 协议契约（改协议必读必改） |
