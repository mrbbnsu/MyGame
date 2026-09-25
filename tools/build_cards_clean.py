#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把百鸽 YGOCDB 原始卡库 (data/cards_raw.json) 清洗成游戏用卡片表 (data/cards_clean.json)。

用法:
    python tools/build_cards_clean.py
输出:
    data/cards_clean.json   卡片数组（游戏用）
    docs/db-stats.md        数量统计 + 字段完整度报告
    data/quality_notes.md   魔陷种类位与文本不一致等数据质量记录
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "cards_raw.json"
CLEAN = ROOT / "data" / "cards_clean.json"
STATS = ROOT / "docs" / "db-stats.md"
QUALITY = ROOT / "data" / "quality_notes.md"

# ---- type 位图（本库为 Master Duel 布局，已用已知卡实证，勿按 ygocore 常量臆测）----
T_MONSTER, T_SPELL, T_TRAP = 0x1, 0x2, 0x4
T_NORMAL, T_EFFECT, T_FUSION, T_RITUAL = 0x10, 0x20, 0x40, 0x80
T_SPIRIT, T_UNION, T_DUAL, T_TUNER, T_SYNCHRO = 0x200, 0x400, 0x800, 0x1000, 0x2000
T_QUICKPLAY, T_CONTINUOUS, T_EQUIP, T_FIELD = 0x10000, 0x20000, 0x40000, 0x80000
T_FLIP, T_TOON = 0x200000, 0x400000
T_XYZ, T_PENDULUM, T_LINK = 0x800000, 0x1000000, 0x4000000
T_SUMMON_CONDITION = 0x2000000  # 不能通常召唤的召唤条件卡

RACE = {
    0x1: "战士", 0x2: "魔法师", 0x4: "天使", 0x8: "恶魔", 0x10: "不死",
    0x20: "机械", 0x40: "水", 0x80: "炎", 0x100: "雷", 0x200: "岩石",
    0x400: "鸟兽", 0x800: "植物", 0x1000: "昆虫", 0x2000: "龙", 0x4000: "兽",
    0x8000: "兽战士", 0x10000: "幻神兽", 0x20000: "恐龙", 0x40000: "鱼",
    0x80000: "海龙", 0x100000: "爬虫", 0x200000: "念动力", 0x400000: "幻神",
    0x800000: "幻龙", 0x1000000: "电子界", 0x2000000: "幻妖",
}
ATTRIBUTE = {0x1: "地", 0x2: "水", 0x4: "火", 0x8: "风",
             0x10: "光", 0x20: "暗", 0x40: "神"}

# 召唤机制优先级：一只怪兽同时带多个标志时， summon_mech 取最高优先者
MECH_PRIORITY = ["LINK", "XYZ", "SYNCHRO", "FUSION", "RITUAL"]
MECH_BITS = {
    "LINK": T_LINK, "XYZ": T_XYZ, "SYNCHRO": T_SYNCHRO,
    "FUSION": T_FUSION, "RITUAL": T_RITUAL,
}


def stat_atk(v):
    return "?" if v == -2 else v


def decode_level(level, type_bits):
    """返回 (level, link_number, link_markers, lscale, rscale)"""
    lv = link = markers = lsc = rsc = None
    if type_bits & T_LINK:
        link = level & 0xFF
        markers = (level >> 16) & 0xFFFF
    elif type_bits & T_PENDULUM:
        lv = level & 0xFF
        lsc = (level >> 16) & 0xFF
        rsc = (level >> 24) & 0xFF
    elif level:
        lv = level
    return lv, link, markers, lsc, rsc


def spell_kind(entry):
    """魔法种类：以 text.types 文本为准，data 位仅做交叉校验"""
    types = entry["text"].get("types", "")
    for label, bit in (("仪式", T_RITUAL), ("装备", T_EQUIP), ("场地", T_FIELD),
                       ("速攻", T_QUICKPLAY), ("永续", T_CONTINUOUS)):
        if label in types:
            return {"仪式": "RITUAL", "装备": "EQUIP", "场地": "FIELD",
                    "速攻": "QUICKPLAY", "永续": "CONTINUOUS"}[label], label, bit
    return "NORMAL", "通常", 0


def trap_kind(entry):
    types = entry["text"].get("types", "")
    if "反击" in types:
        return "COUNTER"
    if "永续" in types:
        return "CONTINUOUS"
    return "NORMAL"


def main():
    raw = json.loads(RAW.read_text(encoding="utf-8"))
    entries = list(raw.values())
    usable = [e for e in entries if "data" in e]
    skipped = [e for e in entries if "data" not in e]

    clean, kind_mismatch, pend_no_desc, link_no_markers = [], [], [], []
    stats = Counter()
    missing = Counter()

    for e in usable:
        d, t = e["data"], e.get("text", {})
        tid = d["type"]
        card_type = "MONSTER" if tid & T_MONSTER else ("SPELL" if tid & T_SPELL else "TRAP")
        types_txt = t.get("types", "")

        name = e.get("cn_name") or e.get("sc_name") or e.get("jp_name") or e.get("en_name")
        if not name:
            missing["no_name"] += 1
            continue
        for field, key in (("cn_name", "cn_name"), ("sc_name", "sc_name"),
                           ("md_name", "md_name"), ("en_name", "en_name"),
                           ("desc", "desc")):
            if not e.get(field) and not t.get(field):
                missing[field] += 1

        flags = []
        if tid & T_NORMAL:
            flags.append("NORMAL")
        if tid & T_EFFECT:
            flags.append("EFFECT")
        for flag, bit in (("FUSION", T_FUSION), ("RITUAL", T_RITUAL),
                          ("SYNCHRO", T_SYNCHRO), ("XYZ", T_XYZ), ("LINK", T_LINK),
                          ("PENDULUM", T_PENDULUM), ("FLIP", T_FLIP), ("TOON", T_TOON),
                          ("SPIRIT", T_SPIRIT), ("UNION", T_UNION), ("DUAL", T_DUAL),
                          ("TUNER", T_TUNER)):
            if tid & bit:
                flags.append(flag)

        mech = next((m for m in MECH_PRIORITY if tid & MECH_BITS[m]), None)
        if card_type != "MONSTER":
            mech = None

        lv, link, markers, lsc, rsc = decode_level(d["level"], tid)
        # Link 怪的 def 在本库是占位值（无意义），置空；箭头字段整库缺失，后续用 YGOPRODeck 补
        monster_def = None if tid & T_LINK else stat_atk(d["def"])
        card = {
            "id": e["id"],
            "cid": e["cid"],
            "name": name,
            "cn_name": e.get("cn_name"),
            "sc_name": e.get("sc_name"),
            "md_name": e.get("md_name"),
            "en_name": e.get("en_name"),
            "jp_name": e.get("jp_name"),
            "card_type": card_type,
            "flags": flags,
            "summon_mech": mech,
            "attribute": ATTRIBUTE.get(d["attribute"]) if card_type == "MONSTER" else None,
            "race": RACE.get(d["race"]) if card_type == "MONSTER" else None,
            "level": lv,
            "link": link,
            "link_markers": markers,
            "lscale": lsc,
            "rscale": rsc,
            "atk": stat_atk(d["atk"]) if card_type == "MONSTER" else None,
            "def": monster_def,
            "text_types": types_txt,
            "desc": t.get("desc", ""),
            "pdesc": t.get("pdesc", ""),
            "ot": d["ot"],
            "setcode": d["setcode"],
            "supported": None,      # 预留：效果系统能否表达
            "complexity": None,     # 预留：效果复杂度分级
        }

        if card_type == "SPELL":
            kind, label, bit = spell_kind(e)
            card["spell_kind"] = kind
            if bit and not tid & bit:
                kind_mismatch.append((e["id"], name, "SPELL", label, f"位缺失 0x{bit:X}"))
        elif card_type == "TRAP":
            card["trap_kind"] = trap_kind(e)
            want = {"COUNTER": "反击", "CONTINUOUS": "永续", "NORMAL": ""}[card["trap_kind"]]
            if want and "反击" in types_txt and card["trap_kind"] == "NORMAL":
                kind_mismatch.append((e["id"], name, "TRAP", "反击", "文本含反击但判为通常"))

        if card_type == "MONSTER" and tid & T_PENDULUM and not card["pdesc"]:
            pend_no_desc.append((e["id"], name))
        if card_type == "MONSTER" and tid & T_LINK and not markers:
            link_no_markers.append((e["id"], name))

        stats[card_type] += 1
        if mech:
            stats["mech_" + mech] += 1
        if tid & T_PENDULUM:
            stats["pendulum_total"] += 1
        if tid & T_SUMMON_CONDITION:
            stats["summon_condition"] += 1
        clean.append(card)

    CLEAN.write_text(json.dumps(clean, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- 统计报告 ----
    spells = [c for c in clean if c["card_type"] == "SPELL"]
    traps = [c for c in clean if c["card_type"] == "TRAP"]
    monsters = [c for c in clean if c["card_type"] == "MONSTER"]
    n = len(clean)
    cov = lambda f: sum(1 for c in clean if c.get(f))
    s_kind = Counter(c.get("spell_kind") for c in spells)
    t_kind = Counter(c.get("trap_kind") for c in traps)
    m_flag = Counter(f for c in monsters for f in c["flags"])
    lvl_no = sum(1 for c in monsters if c["level"] is None and not c["link"])
    lines = [
        "# 卡库统计报告\n",
        f"- 原始条目：{len(entries)}（百鸽 YGOCDB）",
        f"- 可用（含数据）：{len(usable)}，输出：{n}",
        f"- 过滤：{len(skipped)} 张 id=0 的动画卡/未收录卡（无类型数据、无中文）\n",
        "## 大类",
        f"| 类型 | 数量 |\n|---|---|\n| 怪兽 | {len(monsters)} |\n| 魔法 | {len(spells)} |\n| 陷阱 | {len(traps)} |\n",
        "## 召唤机制（怪兽，可叠加，故总数 > 怪兽数）",
        "| 机制 | 数量 |\n|---|---|",
    ]
    for m in ("FUSION", "RITUAL", "SYNCHRO", "XYZ", "LINK", "PENDULUM", "FLIP", "TOON",
              "SPIRIT", "UNION", "DUAL", "TUNER", "NORMAL", "EFFECT"):
        if m_flag.get(m):
            lines.append(f"| {m} | {m_flag[m]} |")
    lines += [
        f"\n- 灵摆（含各种召唤法交叉）：{stats['pendulum_total']} 张",
        f"- 召唤条件怪兽（不能通常召唤）：{stats['summon_condition']} 张",
        f"- 无等级非连接怪兽：{lvl_no} 张\n",
        "## 魔法种类",
        "| 种类 | 数量 |\n|---|---|",
    ]
    for k in ("NORMAL", "QUICKPLAY", "CONTINUOUS", "EQUIP", "FIELD", "RITUAL"):
        lines.append(f"| {k} | {s_kind.get(k, 0)} |")
    lines += ["\n## 陷阱种类", "| 种类 | 数量 |\n|---|---|"]
    for k in ("NORMAL", "CONTINUOUS", "COUNTER"):
        lines.append(f"| {k} | {t_kind.get(k, 0)} |")
    lines += [
        "\n## 字段完整度",
        f"- cn_name（YGOPro 中文译名）：{cov('cn_name')}/{n}",
        f"- sc_name（官方简中）：{cov('sc_name')}/{n}（未覆盖的回退 cn_name）",
        f"- md_name（Master Duel 中文）：{cov('md_name')}/{n}",
        f"- en_name：{cov('en_name')}/{n}",
        f"- 效果文本 desc：{sum(1 for c in clean if c['desc'])}/{n}",
        f"- 灵摆卡缺 pdesc：{len(pend_no_desc)} 张",
        f"- Link 箭头：本库不提供（level 仅含连接数），后续用 YGOPRODeck `linkmarkers` 补充",
        f"- 名字/文本均缺失：{dict(missing) or '无'}\n",
        "> 种类不一致与异常记录见 `data/quality_notes.md`。",
    ]
    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text("\n".join(lines), encoding="utf-8")

    q = ["# 数据质量记录\n", "## 魔法种类：text.types 与 type 位不一致"]
    for row in kind_mismatch[:50]:
        q.append(f"- {row}")
    q.append(f"（共 {len(kind_mismatch)} 条，仅列前 50）")
    if pend_no_desc:
        q.append("\n## 灵摆卡缺灵摆效果文本")
        q += [f"- {r}" for r in pend_no_desc[:20]]
    if link_no_markers:
        q.append(f"\n## Link 箭头缺失（系统性：{len(link_no_markers)}/{len(link_no_markers)} 张，本库无此字段）")
        q.append("- 待 YGOPRODeck API 补充 linkmarkers")
    QUALITY.write_text("\n".join(q), encoding="utf-8")

    print(f"输出 {n} 张卡 -> {CLEAN.name}")
    print(f"怪兽 {len(monsters)} / 魔法 {len(spells)} / 陷阱 {len(traps)}")
    print("机制:", {m: m_flag.get(m, 0) for m in ('FUSION', 'RITUAL', 'SYNCHRO', 'XYZ', 'LINK', 'PENDULUM')})
    print("魔法种类:", dict(s_kind))
    print("陷阱种类:", dict(t_kind))
    print(f"种类不一致 {len(kind_mismatch)} 条 -> {QUALITY.name}")

    # ---- 已知卡 sanity check ----
    byid = {c["id"]: c for c in clean}
    be = byid[89631139]
    assert be["race"] == "龙" and be["attribute"] == "光" and be["level"] == 8, be
    dt = next(c for c in clean if c.get("en_name") == "Decode Talker")
    assert dt["link"] == 3 and dt["race"] == "电子界", (dt["link"], dt["race"])
    tg = next(c for c in clean if c.get("en_name") == "Timegazer Magician")
    print("sanity: 青眼=龙/光/8星 OK; 解码语者 Link3/电子界 OK;",
          f"星读之魔术师 level={tg['level']} scales={tg['lscale']}/{tg['rscale']}")


if __name__ == "__main__":
    sys.exit(main())
