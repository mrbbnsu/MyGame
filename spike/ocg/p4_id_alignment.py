#!/usr/bin/env python3
"""WO-005 P4 探针：三源 ID 对齐验证。

三方：
  A. data/cards_clean.json（YGOCDB 中文库，主键 id）
  B. vendor/edopro/ProjectIgnis/expansions/cards.cdb（datas 表，id）
  C. vendor/repos/CardScripts official/unofficial 的 c{id}.lua 文件名
抽样：固定种子随机 50 张做三方明细；另附全集统计。
"""
import json
import os
import random
import sqlite3

ROOT = "E:/Game"
CLEAN = f"{ROOT}/data/cards_clean.json"
CDB = f"{ROOT}/vendor/edopro/ProjectIgnis/expansions/cards.cdb"
SCRIPTS = f"{ROOT}/vendor/repos/CardScripts"
OUT = f"{ROOT}/spike/ocg/out/p4_id_alignment.json"

TYPE_MONSTER, TYPE_SPELL, TYPE_TRAP = 0x1, 0x2, 0x4


def load_all():
    clean = json.load(open(CLEAN, encoding="utf-8"))
    con = sqlite3.connect(CDB)
    cdb = {r[0]: r[1] for r in con.execute("select id,type from datas")}
    scripts = {"official": set(), "unofficial": set(), "pre-errata": set()}
    for d in scripts:
        p = os.path.join(SCRIPTS, d)
        if os.path.isdir(p):
            scripts[d] = {f[1:-4] for f in os.listdir(p)
                          if f.startswith("c") and f.endswith(".lua")}
    return clean, cdb, scripts


def classify(card, cdb, scripts):
    cid = str(card["id"])
    key = int(cid)
    r = {"id": cid, "name": card["name"], "card_type": card["card_type"],
         "in_cdb": False, "cdb_type_match": None,
         "official_script": cid in scripts["official"],
         "unofficial_script": cid in scripts["unofficial"],
         "no_script_expected": False, "issue": None}
    if key in cdb:
        r["in_cdb"] = True
        t = cdb[key]
        base = t & (TYPE_MONSTER | TYPE_SPELL | TYPE_TRAP)
        expect = {"MONSTER": TYPE_MONSTER, "SPELL": TYPE_SPELL,
                  "TRAP": TYPE_TRAP}[card["card_type"]]
        r["cdb_type_match"] = (base == expect)
    # 无效果怪兽本来就没有脚本
    flags = card.get("flags") or []
    if card["card_type"] == "MONSTER" and "NORMAL" in flags and "EFFECT" not in flags:
        r["no_script_expected"] = True
    return r


def main():
    clean, cdb, scripts = load_all()
    ids_clean = {int(c["id"]) for c in clean}
    ids_official = scripts["official"]
    ids_unofficial = scripts["unofficial"] | scripts["pre-errata"]

    # 全集统计
    stats = {
        "cards_clean": len(ids_clean),
        "cdb_datas": len(cdb),
        "scripts_official": len(ids_official),
        "scripts_unofficial_plus_preerrata": len(ids_unofficial),
        "clean_in_cdb": len(ids_clean & set(cdb)),
        "clean_with_official_script": len(ids_clean & ids_official),
        "clean_with_unofficial_script": len(ids_clean & ids_unofficial),
        "cdb_not_in_clean": len(set(cdb) - ids_clean),
    }
    stats["clean_in_cdb_pct"] = round(
        stats["clean_in_cdb"] / stats["cards_clean"] * 100, 2)

    # 随机抽样 50
    rng = random.Random(20260925)
    sample = rng.sample(list(clean), 50)
    rows = [classify(c, cdb, scripts) for c in sample]
    for r in rows:
        if not r["in_cdb"]:
            r["issue"] = "不在 cdb"
        elif r["cdb_type_match"] is False:
            r["issue"] = "cdb 主类型不匹配"
        elif not (r["official_script"] or r["unofficial_script"]
                  or r["no_script_expected"]):
            r["issue"] = "无脚本且非通常怪兽"

    mismatches = [r for r in rows if r["issue"]]
    no_script = [r for r in rows if r["no_script_expected"]]

    result = {
        "probe": "WO-005 P4 三源 ID 对齐",
        "seed": 20260925,
        "sample_size": 50,
        "stats": stats,
        "sample_ok": 50 - len(mismatches),
        "sample_mismatch": len(mismatches),
        "mismatch_detail": mismatches,
        "normal_monsters_without_script": len(no_script),
        "sample": rows,
    }
    # C1 经典卡池底稿（reason==OK，2599 张）子集对齐——项目实际要用的域
    pool = [c for c in json.load(open(f"{ROOT}/data/v1_pool.json", encoding="utf-8"))
            if c["reason"] == "OK"]
    pool_rows = [classify(c, cdb, scripts) for c in pool]
    pool_bad = [r for r in pool_rows if r["issue"]]
    pool_no_script_ok = [r for r in pool_rows
                         if r["no_script_expected"] and not r["issue"]]
    pool_stats = {
        "pool_size": len(pool_rows),
        "in_cdb": sum(1 for r in pool_rows if r["in_cdb"]),
        "with_official_script": sum(1 for r in pool_rows if r["official_script"]),
        "normal_monster_no_script": len(pool_no_script_ok),
        "issues": len(pool_bad),
        "issue_detail": pool_bad[:20],
    }
    pool_stats["playable_pct"] = round(
        (pool_stats["with_official_script"] + pool_stats["normal_monster_no_script"])
        / pool_stats["pool_size"] * 100, 2)
    result["pool_check"] = pool_stats

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    print(f"P4 三源对齐：抽样 {50} 张，问题 {len(mismatches)} 张")
    print(f"全集：clean {stats['cards_clean']} / cdb {stats['cdb_datas']} "
          f"/ official脚本 {stats['scripts_official']}")
    print(f"clean→cdb 命中率：{stats['clean_in_cdb_pct']}%")
    for r in mismatches:
        print(f"  MISMATCH {r['id']} {r['name']} {r['issue']} "
              f"official={r['official_script']} unofficial={r['unofficial_script']} "
              f"no_script_expected={r['no_script_expected']}")
    print(f"C1 经典池 {pool_stats['pool_size']} 张：cdb 命中 {pool_stats['in_cdb']}，"
          f"official 脚本 {pool_stats['with_official_script']}，通常怪无脚本 "
          f"{pool_stats['normal_monster_no_script']}，问题 {pool_stats['issues']}"
          f" → 可玩率 {pool_stats['playable_pct']}%")
    for r in pool_stats["issue_detail"]:
        print(f"  POOL-ISSUE {r['id']} {r['name']} {r['issue']}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    main()
