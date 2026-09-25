# A1（WO-001 自研规则引擎）验收记录 —— ✅ 通过，冻结归档

- 执行：worker A ｜ 提交：`901153f` ｜ 验收：PM（2026-09-25）
- **v2 处置：验收通过后冻结为 NO-GO fallback 资产，不再迭代**（主线已转 ocgcore，见 `docs/architecture-v2.md`）

## 验收结果（对照工单第 7 节）

| # | 标准 | 结果 |
|---|---|---|
| 1 | npm test 全绿 + 用例名覆盖 | ✅ 33/33；工单第 6 节 30 个用例名 **30/30 完全一致** |
| 2 | 改坏断言验证测试有效性 | ✅ 临时放开"每回合一次召唤"限制 → 恰好 `test_one_normal_summon_per_turn` 变红（10 过 1 挂）；还原后 33/33 恢复 |
| 3 | 架构红线 grep | ✅ 槽位直写仅 move.ts；无 `.lp -=`；无卡名硬编码分支 |
| 4 | 完整对局（真实卡库数据） | ✅ `test_full_game_with_real_db_data` 在套件内通过 |
| 5 | 接口契约 | ✅ createDuel/legalActions/applyAction + 七种 GameAction 按工单实现 |

## worker A 的关键实现决定（记录备查）

- endReason 取枚举值 `LP_ZERO` / `DECK_OUT`（工单只要求写入，枚举化合理）
- createDuel 不校验卡组张数（留给 Free Duel 卡组系统，符合分工）
- changeLp 归属 battle.ts；起手 P0/P1 交替各抽 5

## 保留价值

1. NO-GO 时的完整回退路线（规则基准 = 归档的 v1-rules.md）
2. 30 个规则测试可作为将来 ocgcore 行为的对照参考（基础召唤/战斗语义）
3. node:test 骨架与 TS 工程习惯被 Adapter/UI 复用
