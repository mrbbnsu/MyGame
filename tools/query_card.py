#!/usr/bin/env python3
"""按 Card ID（卡片密码）查询 cards_clean.json 中的卡牌信息。

用法：python -X utf8 tools/query_card.py 89631139 [更多ID...]
"""
import json
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "cards_clean.json"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    cards = {str(c["id"]): c for c in json.loads(DB.read_text(encoding="utf-8"))}
    for cid in argv:
        c = cards.get(cid.lstrip("0") or cid)
        if c is None:
            print(f"{cid}: 未找到")
            continue
        print(f"--- {cid} ---")
        print(f"中文名: {c.get('name')}")
        print(f"英文名: {c.get('en_name') or '(无)'}")
        print(f"类型:   {c.get('card_type')} {'/'.join(c.get('flags') or [])}"
              + (f" [{c.get('spell_kind') or c.get('trap_kind')}]" if c.get("spell_kind") or c.get("trap_kind") else ""))
        if c.get("card_type") == "MONSTER":
            print(f"属性/种族: {c.get('attribute')} / {c.get('race')}")
            print(f"Level:  {c.get('level')}   ATK: {c.get('atk')}   DEF: {c.get('def')}")
        print(f"效果:   {(c.get('desc') or '').strip()[:200]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
