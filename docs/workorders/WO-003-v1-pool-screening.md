# WO-003：V1 卡池机器初筛打标

> **任务编号 C1 ｜ 执行：worker C。** 文件名保留 WO-003 不变（已派发会话按此路径领取，勿改名）。

> 优先级：🟢 低（可并行，不阻塞任何工单；为 Phase 4/7/8 供料）
> 依赖：Phase 1 已完成
> 本工单自包含；只改 `tools/` 与 `data/`，不碰引擎代码。

## 0. 背景

V1 目标卡池 100~150 张（任务书 §7/§8）。全库 14281 张需要先做一轮**机器可判定**的粗筛，产出"候选池 + 排除原因"，人工挑卡在 Phase 4 之后进行。本工单只做客观规则过滤，**不做语义理解**（效果文本只用于关键词黑名单，不做解析）。

复杂度分级标准（任务书 §7）：C0 普通无效果 / C1 单一简单效果 / C2 有条件目标或简单特招 / C3 触发、墓地、基本连锁 / C4 多效果或复杂持续 / C5 高度现代化。

## 1. 交付物

```
tools/screen_v1_pool.py     初筛脚本（幂等，可重跑）
data/v1_pool.json           候选池：[{id, name, card_type, flags, spell_kind/trap_kind, reason, complexity_hint}]
data/v1_pool_stats.md       统计：各级数量、被排除类别分布
```

## 2. 筛选规则（客观、可复核）

**入选**（`reason: "OK"`）：
1. 普通怪兽：`flags` 含 `NORMAL` 且不含 `EFFECT`/`RITUAL`/`SPIRIT`/`UNION`/`DUAL`，atk/def 为数字、level 为数字 → `complexity_hint: "C0"`
2. 通常魔法 / 通常陷阱（`spell_kind`/`trap_kind` = `NORMAL`）且效果文本**不命中黑名单** → `complexity_hint: "C1?"`（问号=待人工定级）

**黑名单关键词**（命中即排除，`reason` 记录命中词；来源 = `docs/effect-system.md` §11 ❌ 清单 + V1 不做项）：
同调 / 超量 / 灵摆 / 连接 / 衍生物 / 代币 / 指示物 / 硬币 / 骰子 / 一回合一次出现≥2次 / 除外后再回到 / 特殊召唤方式不同 / Xyz / Synchro / Pendulum / Link / Token / Counter(仅怪兽文本) / 每次…可以发动多次

**结构排除**（先于关键词）：`summon_mech` 非空（融合/仪式/同调/超量/连接）、灵摆（有 lscale）、`flags` 含 `TOON`/`SPIRIT`/`UNION`/`DUAL`。
（注：融合/仪式不是永久排除，只是 V1 引擎未建——`reason` 写 `"EXTRA_PENDING"` 单独归类，不算 failed。）

黑名单清单允许 worker 在实现时补充明显同义的词（如"投掷硬币"），但**每加一个词都要在完成说明里列出**。

## 3. 验收标准（PM 执行）

1. `python -X utf8 tools/screen_v1_pool.py` 幂等：连跑两次输出 diff 为空
2. 普通怪兽（stats 应约 723 减去结构排除）全部入池且 complexity_hint=C0；抽查青眼白龙 89631139 在池内
3. 抽查 10 张被排除卡：`reason` 与卡面实际相符（PM 用 `tools/query_card.py` 核对）
4. 抽查 5 张 C1? 通常魔陷：确实无黑名单词、无持续/装备/速攻标记
5. `v1_pool_stats.md` 数字自洽（各类合计 = 候选总数）

## 4. 完成定义（DoD）

验收 1-5 全过 + git 提交（`V1 卡池机器初筛（WO-003）`）+ 完成说明（补充的黑名单词、异常卡记录）。
