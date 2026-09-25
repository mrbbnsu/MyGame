# E1（WO-007 Adapter v0）验收记录 —— ✅ 通过

- 执行：worker E ｜ 提交：`d8e1436` ｜ 验收：PM（2026-09-25）

## 验收结果（对照工单第 5 节）

| # | 标准 | 结果 |
|---|---|---|
| 1 | selftest + npm test 全绿 | ✅ PM 亲自跑：selftest **43/43**（含信息隐藏、确定性专项），npm test **38/38** |
| 2 | 集成测试打完整局 | ✅ 断言实打实：ready 握手（core_api_version 11.0）、new_duel（普通怪+效果卡）自动应答到 winner=0/reason=1/败方 LP=0/回合≥3/事件>50，含驱动停摆检测（>4000 步报错） |
| 3 | 信息隐藏（K3） | ✅ 专项测试 + **PM 破坏性验证**：临时改 `vis = True` 放开隐藏 → 恰好两条隐藏测试变红；还原后 43/43 恢复 |
| 4 | 确定性回放 | ✅ "同 seed 同脚本事件流逐字节一致" PASS（selftest 内） |
| 5 | 解码覆盖 ≥40 + 协议一致 | ✅ **79 种**（95 枚举全命名），清单在 decoder.py 顶部且标注来源（探针实跑/core writer）；protocol.md 与 types.ts 抽查一致 |
| 6 | 红线 grep | ✅ src/ 零二进制解析；解码仅在 decoder.py（service.py 的 MSG_ 引用仅为注释/重试计数）；viewer 隐藏集中 build_state/_redact_event |

## 交付物

`adapter/`（service/core_binding/decoder/protocol.md/selftest/README）+ `src/adapter/`（client.ts/types.ts）+ `tests/adapter_integration.test.ts`。vendor 未入库。

## 质量点评

- 超额：解码 79 种（要求 40）；自测覆盖输入校验/重试环/事件脱敏等边角
- respond 带 viewer、事件流同步脱敏（_redact_event）——比工单字面要求更完整地落实了 K3
- retry 上限（64 次 → DUEL_RETRY_LOOP 错误）解决了"core 应答被拒死循环"的隐患

## 后续

P2（Adapter）✅。下一单：F1（WO-008，P3 最小 UI）——建立在这套协议上。
