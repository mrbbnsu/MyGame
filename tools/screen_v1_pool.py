#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WO-003：V1 卡池机器初筛打标。

把 data/cards_clean.json 全库按客观规则粗筛，产出候选池 + 排除原因 + 统计报告。
只做关键词/结构过滤，不解析效果语义。

用法:
    python -X utf8 tools/screen_v1_pool.py
输出:
    data/v1_pool.json       全库打标数组（含被排除卡，reason != "OK" 即排除，
                            供 PM 用 tools/query_card.py 抽查排除原因）
    data/v1_pool_stats.md   数量统计 + 黑名单命中分布（无时间戳，幂等可重跑）

规则来源: docs/workorders/WO-003-v1-pool-screening.md §2
黑名单依据: docs/effect-system.md §11 ❌ 清单 + V1 不做项
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data" / "cards_clean.json"
POOL = ROOT / "data" / "v1_pool.json"
STATS = ROOT / "data" / "v1_pool_stats.md"

# ---- 黑名单关键词（命中即排除；子串匹配，作用于效果文本 desc+pdesc）----
# 简单词（工单原文列出；"多维"为补充同义词 = 超量旧译，0 命中冗余保险）
KEYWORDS = ["同调", "超量", "多维", "灵摆", "连接", "衍生物", "代币",
            "指示物", "硬币", "骰子"]
# 英文词（工单原文；忽略大小写）
ENGLISH_KEYWORDS = ["Xyz", "Synchro", "Pendulum", "Link", "Token"]
# 工单括注"仅怪兽文本"——本流程黑名单只检查通常魔陷，普通怪兽文本不参与，
# 此词按工单定义保留在配置中，实际不会命中（见 stats 口径说明）
MONSTER_ONLY_KEYWORDS = ["Counter"]
# "一回合一次"出现 >= 2 次 = 多个一回合一次（多效果卡）
ONCE_PER_TURN = re.compile(r"[一1]回合[一1]次")
# 工单描述性短语落到卡面措辞上的客观正则（逐条在完成说明/stats 记录）
REGEX_KEYWORDS = [
    ("除外后再回到", re.compile(r"除外[^。，；]*回(?:到|来)")),
    ("每次…可以发动", re.compile(r"每次[^。？]*可以")),
    ("特殊召唤方式不同", re.compile(r"(?:这个方法|上述方法)")),
]

# ---- 结构排除（先于关键词，按工单 §2 列举顺序取首个命中）----
MECH_PENDING = ("FUSION", "RITUAL")            # EXTRA_PENDING：V1 引擎未建，不算失败
FLAG_EXCLUDED = ("TOON", "SPIRIT", "UNION", "DUAL")
RULE1_BAN = {"EFFECT", "RITUAL", "SPIRIT", "UNION", "DUAL"}  # 普通怪兽不得叠加的 flag


def is_num(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def blacklist_hit(card: dict):
    """返回通常魔陷文本命中的黑名单词（按配置顺序取首个），无命中返回 None"""
    text = (card.get("desc") or "") + (card.get("pdesc") or "")
    for kw in KEYWORDS:
        if kw in text:
            return kw
    low = text.lower()
    for kw in ENGLISH_KEYWORDS:
        if kw.lower() in low:
            return kw
    if len(ONCE_PER_TURN.findall(text)) >= 2:
        return "一回合一次×2"
    for label, rx in REGEX_KEYWORDS:
        if rx.search(text):
            return label
    return None


def screen(card: dict):
    """按工单 §2 判定一张卡，返回 (reason, complexity_hint)"""
    mech = card.get("summon_mech")
    if mech:
        if mech in MECH_PENDING:
            return "EXTRA_PENDING", None
        return f"STRUCT_MECH:{mech}", None
    if card.get("lscale") is not None:
        return "STRUCT_PENDULUM", None
    flag_hit = next((f for f in FLAG_EXCLUDED if f in (card.get("flags") or [])), None)
    if flag_hit:
        return f"STRUCT_FLAG:{flag_hit}", None
    ctype = card["card_type"]
    if ctype in ("SPELL", "TRAP"):
        kind = card.get("spell_kind" if ctype == "SPELL" else "trap_kind")
        if kind != "NORMAL":
            return f"STRUCT_KIND:{kind}", None
        hit = blacklist_hit(card)
        if hit:
            return f"BLACKLIST:{hit}", None
        return "OK", "C1?"
    # 怪兽：工单入选规则 1（普通怪兽 -> C0）
    flags = set(card.get("flags") or [])
    if ("NORMAL" in flags and not (flags & RULE1_BAN)
            and is_num(card.get("atk")) and is_num(card.get("def"))
            and is_num(card.get("level"))):
        return "OK", "C0"
    return "EFFECT_MONSTER", None


def keyword_hit_counts(cards: list) -> Counter:
    """逐词独立计数（允许一张卡命中多个词），基数 = 全部通常魔陷，供复核"""
    counts: Counter = Counter()
    for c in cards:
        if not (c["card_type"] in ("SPELL", "TRAP")
                and c.get("spell_kind" if c["card_type"] == "SPELL" else "trap_kind") == "NORMAL"):
            continue
        text = (c.get("desc") or "") + (c.get("pdesc") or "")
        for kw in KEYWORDS:
            if kw in text:
                counts[kw] += 1
        low = text.lower()
        for kw in ENGLISH_KEYWORDS:
            if kw.lower() in low:
                counts[f"{kw}(英文)"] += 1
        if len(ONCE_PER_TURN.findall(text)) >= 2:
            counts["一回合一次×2"] += 1
        for label, rx in REGEX_KEYWORDS:
            if rx.search(text):
                counts[label] += 1
    return counts


REASON_ORDER = ["EXTRA_PENDING", "STRUCT_MECH:SYNCHRO", "STRUCT_MECH:XYZ",
                "STRUCT_MECH:LINK", "STRUCT_PENDULUM", "STRUCT_FLAG:TOON",
                "STRUCT_FLAG:SPIRIT", "STRUCT_FLAG:UNION", "STRUCT_FLAG:DUAL",
                "STRUCT_KIND:RITUAL", "STRUCT_KIND:EQUIP", "STRUCT_KIND:FIELD",
                "STRUCT_KIND:QUICKPLAY", "STRUCT_KIND:CONTINUOUS",
                "STRUCT_KIND:COUNTER", "EFFECT_MONSTER"]


def reason_sort_key(reason: str):
    if reason in REASON_ORDER:
        return 0, REASON_ORDER.index(reason)
    if reason == "OK":
        return 2, 0
    return 1, 0  # BLACKLIST:* 排在结构排除之后


def fmt_int(n: int) -> str:
    return f"{n:,}"


def render_stats(cards: list, entries: list) -> str:
    reasons = Counter(e["reason"] for e in entries)
    ok = [e for e in entries if e["reason"] == "OK"]
    ok_c0 = [e for e in ok if e["complexity_hint"] == "C0"]
    ok_spell = [e for e in ok if e["card_type"] == "SPELL"]
    ok_trap = [e for e in ok if e["card_type"] == "TRAP"]
    c0_tuner = [e for e in ok_c0 if "TUNER" in e["flags"]]
    normal_total = sum(1 for c in cards if "NORMAL" in (c.get("flags") or []))
    normal_pend = sum(1 for c in cards
                      if "NORMAL" in (c.get("flags") or []) and c.get("lscale") is not None)
    pending_mech = Counter(c["summon_mech"] for c in cards
                           if c.get("summon_mech") in MECH_PENDING)
    kw_counts = keyword_hit_counts(cards)

    excluded = {r: n for r, n in reasons.items() if r != "OK"}
    pending = reasons["EXTRA_PENDING"]
    n_excluded = sum(n for r, n in excluded.items() if r != "EXTRA_PENDING")
    total = len(cards)
    pool_breakdown = (
        f"| 入池合计（reason=OK） | {fmt_int(len(ok))} |\n"
        f"| - 普通怪兽 C0 | {fmt_int(len(ok_c0))} |\n"
        f"| - 通常魔法 C1? | {fmt_int(len(ok_spell))} |\n"
        f"| - 通常陷阱 C1? | {fmt_int(len(ok_trap))} |\n"
        f"| 留待后续 EXTRA_PENDING（融合/仪式，不算失败） | {fmt_int(pending)} |\n"
        f"| 排除合计（其余 reason） | {fmt_int(n_excluded)} |\n"
        f"| **全库合计** | **{fmt_int(total)}** |"
    )

    normal_kind_st = sum(
        1 for c in cards if c["card_type"] in ("SPELL", "TRAP")
        and c.get("spell_kind" if c["card_type"] == "SPELL" else "trap_kind") == "NORMAL")

    reason_rows = "\n".join(
        f"| {r} | {fmt_int(reasons[r])} |" for r in
        sorted(reasons, key=reason_sort_key) if r not in ("OK", "EXTRA_PENDING"))
    kw_rows = "\n".join(
        f"| {kw} | {fmt_int(kw_counts.get(kw, 0))} |" for kw in
        KEYWORDS + [f"{k}(英文)" for k in ENGLISH_KEYWORDS]
        + MONSTER_ONLY_KEYWORDS + ["一回合一次×2"] + [label for label, _ in REGEX_KEYWORDS])

    return f"""# V1 卡池机器初筛统计（WO-003）

数据源：`data/cards_clean.json`（{fmt_int(total)} 张）·
规则：`docs/workorders/WO-003-v1-pool-screening.md` §2 ·
黑名单依据：`docs/effect-system.md` §11 ❌

## 总览

| 类别 | 数量 |
|---|---:|
{pool_breakdown}

## 入池构成

- **C0 普通怪兽 {fmt_int(len(ok_c0))} 张**：全库 NORMAL 怪兽 {normal_total} 张，
  其中灵摆普通怪兽 {normal_pend} 张因 lscale 被结构排除；其余全部入池
  （含普通怪兽·协调 {len(c0_tuner)} 张——TUNER 不在工单结构排除清单内，按规则入池）。
- **C1? 通常魔陷 {fmt_int(len(ok_spell) + len(ok_trap))} 张**（问号 = 待人工定级）：
  通常魔法 {fmt_int(len(ok_spell))} 张 + 通常陷阱 {fmt_int(len(ok_trap))} 张，
  均无黑名单命中、非装备/场地/永续/速攻/反击种类。

## 排除原因分布（互斥，按判定优先级；不含 OK / EXTRA_PENDING）

| reason | 数量 |
|---|---:|
{reason_rows}
| **排除合计** | **{fmt_int(n_excluded)}** |

## EXTRA_PENDING 构成（V1 引擎未建，后续阶段可捞回）

| summon_mech | 数量 |
|---|---:|
| FUSION（融合） | {fmt_int(pending_mech.get("FUSION", 0))} |
| RITUAL（仪式） | {fmt_int(pending_mech.get("RITUAL", 0))} |

## 黑名单逐词命中（基数 = 全部通常魔陷 {fmt_int(normal_kind_st)} 张 = 入池 {fmt_int(len(ok_spell) + len(ok_trap))} + 黑名单排除 {fmt_int(sum(n for r, n in reasons.items() if r.startswith("BLACKLIST")))}）

逐词独立计数，一张卡可命中多个词（与上表互斥计数有重叠），仅作复核。

| 关键词 | 命中卡数 |
|---|---:|
{kw_rows}

## 口径说明

- 输出 `data/v1_pool.json` 为**全库打标**：`reason: "OK"` 即候选池（Phase 4 人工挑选的输入），
  其余 reason 为排除/留待原因，可按 id 对照 `tools/query_card.py` 核对卡面。
- reason 取判定顺序中首个命中；黑名单逐词命中表为独立计数，与排除分布存在重叠。
- 黑名单只作用于通常魔陷的效果文本（`desc`+`pdesc`）；普通怪兽为无效果卡，文本不参与检查，
  故工单括注"仅怪兽文本"的 `Counter` 词不会命中（保留在配置中仅为忠实工单定义）。
- 描述性短语落地正则：除外后再回到 = `除外[^。，；]*回(?:到|来)`；
  每次…可以发动 = `每次[^。？]*可以`；特殊召唤方式不同 = `这个方法|上述方法`；
  一回合一次×2 = `[一1]回合[一1]次` 出现 ≥2 次（"各能使用1次"等变体不计入，
  避免把卡名使用限制误判为多个一回合一次；本库通常魔陷上该主正则 ≥2 次命中 0 张）。
- 补充同义词：多维（超量旧译，0 命中）。已考虑但放弃：投掷硬币、掷骰
  （分别为"硬币"/"骰子"的子串，冗余）。
- 判定顺序：summon_mech → 灵摆 lscale → TOON/SPIRIT/UNION/DUAL → 魔陷种类 →
  黑名单关键词 → 普通怪兽/效果怪兽归类。
- 幂等：输出按 id 排序、无时间戳，连跑两次逐字节一致。
"""


def main() -> int:
    cards = json.loads(CLEAN.read_text(encoding="utf-8"))
    entries = []
    for c in sorted(cards, key=lambda c: c["id"]):
        reason, hint = screen(c)
        entries.append({
            "id": c["id"],
            "name": c["name"],
            "card_type": c["card_type"],
            "flags": c.get("flags") or [],
            "spell_kind": c.get("spell_kind"),
            "trap_kind": c.get("trap_kind"),
            "reason": reason,
            "complexity_hint": hint,
        })
    total = len(cards)
    reasons = Counter(e["reason"] for e in entries)
    assert sum(reasons.values()) == total
    n_c0 = sum(1 for e in entries if e["complexity_hint"] == "C0")
    ok = reasons["OK"]
    pending = reasons["EXTRA_PENDING"]
    POOL.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    STATS.write_text(render_stats(cards, entries), encoding="utf-8")
    print(f"全库 {total} 张：入池 {ok}（C0 {n_c0}，C1? {ok - n_c0}），"
          f"EXTRA_PENDING {pending}，排除 {total - ok - pending}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
