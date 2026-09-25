# vendor/ 版本锚定（WO-005 / D1）

> 本目录全部内容（除本文件）不入库：源码与二进制体积大，且 ocgcore / CardScripts 为
> AGPL-3.0-or-later（见 docs/architecture-v2.md §5）。复现步骤见
> docs/reports/OCGCORE_INTEGRATION_NOTES.md §0。

## 上游仓库（2026-09-25 探针当日锁定）

| 组件 | 来源 | 精确版本 | 说明 |
|---|---|---|---|
| ygopro-core（=架构文档所称 "ocgcore"） | https://github.com/edo9300/ygopro-core | commit `efc21aa433b88cd35b7c37db4072a35c58d9d435`（master，2026-09-25T08:05Z） | C API 11.0；EDOPro 官方 submodule 指向此仓（ProjectIgnis/ocgcore 仓库名不存在） |
| CardScripts | https://github.com/ProjectIgnis/CardScripts | commit `3e09ff8b3ce089b8e6197e095ee60f86a832a568`（master，2026-09-25T06:09Z） | official/ 12702+ 卡脚本（发行版 script/ 为同源拷贝） |
| Lua（core 子模块） | https://github.com/lua/lua | submodule SHA `6e22fedb74cf0c9b6656e9fce8b7331db847c605`（5.4 开发树，35 个 .c） | 与 core 捆绑编译，按 C++ 编译 |

## EDOPro 发行包（cards.cdb 来源）

| 项 | 值 |
|---|---|
| 包 | `ProjectIgnis-EDOPro-41.0.2-windows.zip`（tag 41.0.2，repo ProjectIgnis/edopro-assets） |
| 大小 / MD5 | 94,798,514 B / `da39df030fc95f570cec6320e2e232ca`（与官方下载页一致） |
| 内含 | `ProjectIgnis/ocgcore.dll`（**32 位 x86**）、`expansions/cards.cdb`（datas+texts 各 13728 行）、`script/`（CardScripts 拷贝）、WindBot |
| cards.cdb 口径 | 发行版快照，落后 CardScripts master；新卡脚本先行、cdb 行滞后（见 D1-report P4） |

## 探针工具链（未安装系统级软件）

| 工具 | 版本 | 获取 |
|---|---|---|
| zig（当 C++17 编译器，clang 前端 + mingw-w64 静态运行时） | 0.16.0 | `pip install ziglang`（PyPI，无需 GitHub） |
| Python | 3.11.9（本机已有） | ctypes 调 DLL |
| Node | 24.14.0（本机已有） | 未用于探针（见 D1-report §3） |

## 本地产物

| 路径 | 说明 |
|---|---|
| `vendor/repos/ygopro-core/` | core 源码（含 lua/src 子模块已填充） |
| `vendor/repos/CardScripts/` | 卡脚本仓库 |
| `vendor/edopro/ProjectIgnis/` | EDOPro 41.0.2 解包 |
| `spike/ocg/out/ocgcore.dll` | 自编译 64 位核心（zig，见 spike/ocg/build_dll.sh），产物不入库 |
