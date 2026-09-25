# C1（WO-003 卡池机器初筛）验收记录 —— ✅ 通过

- 执行：worker C ｜ 提交：`38faff8` ｜ 验收：PM（2026-09-25）
- **v2 语义修正**：产出用途从"effect-system 可表达性"改为"**经典卡池适合度**"（Classic=卡池选择，见 architecture-v2.md）；complexity_hint 降级为参考信息

## 验收结果（对照工单第 3 节）

| # | 标准 | 结果 |
|---|---|---|
| 1 | 幂等（连跑两次输出一致） | ✅ PM 复跑 diff 为空 |
| 2 | 普通怪兽全入池且 C0 | ✅ 723 张 NORMAL 中 685 入池（38 张灵摆普通怪按结构规则排除，工单 §2 明列），青眼白龙 89631139 在池 reason=OK |
| 3 | 抽查被排除卡 reason 属实 | ✅ PM 抽 10 张 + 核实 3 张对照 cards_clean：调整魔术师 flags 确含 DUAL；深渊的电击魟、绚岚之权能确为 CONTINUOUS；reason 码体系自洽 |
| 4 | C1? 抽查确为通常魔陷 | ✅ 抽 5 张（身剑一体/废铁稻草人/急袭猛禽复制品/伪羽/借机巧旅笼藏）全部 NORMAL 陷阱 |
| 5 | 统计自洽 | ✅ 2599 OK + 729 EXTRA_PENDING + 10953 排除 = 14281 全库；v1_pool.json 覆盖全部 14281 条 |

## 产出

`tools/screen_v1_pool.py` + `data/v1_pool.json`（14281 条全量打标，reason 码：OK / EXTRA_PENDING / STRUCT_FLAG:* / STRUCT_KIND:* / EFFECT_MONSTER / 黑名单词）+ `data/v1_pool_stats.md`。

## v2 路线下的用途

- **P6 经典卡池的机器底稿**：2599 张候选（685 C0 普通怪 + 1914 C1? 通常魔陷）供人工挑卡
- 排除码可复用于将来"现代展开特征"扩充筛查
- EXTRA_PENDING 729 张（融合/仪式）在 ocgcore 路线下不再是"待实现"，属可选扩展卡
