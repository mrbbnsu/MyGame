# D1（WO-005 Phase P 探针）验收记录 —— ✅ 通过，Go/No-Go 判定：**GO**

- 执行：worker D ｜ 提交：`feeede7` ｜ 验收：PM（2026-09-25）

## 验收结果（对照工单第 4 节）

| # | 标准 | 结果 |
|---|---|---|
| 1 | P1~P4 逐条结论 + 证据 | ✅ D1-report.md 结论先行、每条附实测证据；NOTES.md 七要素齐全（获取构建/13 个 C API/初始化/载卡/载脚本/消息交互/状态查询 + §7 十一项坑 + §8 复跑清单） |
| 2 | transcript 可复现 | ✅ PM 亲自复跑 P2/P3/P4 三个脚本：P2 全 PASS（召唤/攻击/4×2000 伤害/LP 归零/先攻不抽牌）；P3 十项全 PASS（强欲之壶抽2/黑洞清场/死者苏生特召/杀人番茄触发/突进连锁改攻/圣防连锁）；P4 复现 99.73% 可玩、0 错位 |
| 3 | friction 量化 | ✅ 95 个消息枚举（26 已解码、首期建议 ~40）、构建 15 分钟（pip zig 方案）、32 位发行版不可 FFI、11 项格式坑已记录 |
| 4 | AGPL/版权提醒 | ⚠️ 小瑕疵：报告正文未提（在 VERSIONS.md 与 architecture-v2 §5 有）——不阻塞，记录在案 |
| 5 | 明确建议 | ✅ GO，五项标准逐条对照满足 |

## Go/No-Go 判定（PM 依用户标准确认）

**GO。** 五项标准全过：核心独立运行 ✅ / 脚本零改动加载 ✅ / 读取并提交选择 ✅ / passcode 三源统一主键 ✅ / Adapter 路径已验证（sidecar + JSON）✅。No-Go 条件（构建不稳/API 不可控/脚本不可脱离/映射系统性问题）零触发。**ocgcore + CardScripts 正式确定为规则与卡牌执行主线**（fallback 资产继续封存）。

## worker D 的关键事实修正与情报（入档）

1. **命名勘误**：ProjectIgnis/ocgcore 不存在；实际核心 = `edo9300/ygopro-core`（EDOPro 官方 submodule，AGPL，C API 11.0）——架构文档已同步修正
2. 32 位发行版 DLL 不可 FFI → zig 自编译 64 位 DLL 方案（15 分钟，已固化 build_dll.sh）
3. cdb 是发行版快照会滞后最新卡（3/50 + C1 池 7 张）→ 需定期刷新机制；alias 字段 298 张需 metadata 透传
4. core 原生支持 MR1/GOAT 等旧 Master Rule 预设——"经典规则时代"未来可直接用，无需自研

## 后续（PM 已开单）

- E1（WO-007）：Classic Duel Adapter v0（JSON 协议服务），v0 用 Python 复用探针绑定，JSON 边界锁定
- D2（WO-006）：WindBot 调查仍待派发（AI V0 前）
