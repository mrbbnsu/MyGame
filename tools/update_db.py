#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查并更新百鸽 YGOCDB 卡库。游戏启动时调用；MD5 未变则不下载。

流程（官方建议）:
    1. GET https://ygocdb.com/api/v0/cards.zip.md5
    2. 与本地 data/.cards_md5 对比，一致则退出
    3. 下载 cards.zip，校验【解压后 cards.json 的 MD5】（官方 MD5 针对内层文件，不是 zip 本身）
    4. 覆盖 data/cards_raw.json，记录新 MD5，并重新执行清洗

用法:
    python tools/update_db.py [--force]
"""
import hashlib
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MD5_FILE = DATA / ".cards_md5"
MD5_URL = "https://ygocdb.com/api/v0/cards.zip.md5"
ZIP_URL = "https://ygocdb.com/api/v0/cards.zip"


def remote_md5():
    with urllib.request.urlopen(MD5_URL, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    force = "--force" in sys.argv
    local = MD5_FILE.read_text(encoding="utf-8").strip() if MD5_FILE.exists() else None
    remote = remote_md5()
    if not force and local == remote:
        print(f"卡库已是最新（md5={remote[:12]}…）")
        return 0

    print(f"检测到更新：{local} -> {remote}，开始下载…")
    with urllib.request.urlopen(ZIP_URL, timeout=300) as resp:
        blob = resp.read()
    inner = zipfile.ZipFile(io.BytesIO(blob)).read("cards.json")
    digest = hashlib.md5(inner).hexdigest()
    if digest != remote:
        print(f"MD5 校验失败：期望 {remote}，实际 {digest}，放弃写入")
        return 1

    DATA.mkdir(exist_ok=True)
    (DATA / "cards_raw.json").write_bytes(inner)
    MD5_FILE.write_text(remote, encoding="utf-8")
    print(f"已更新 data/cards_raw.json（{len(inner)/1e6:.1f} MB）")
    print("重新清洗…")
    import build_cards_clean  # 同目录
    return build_cards_clean.main() or 0


if __name__ == "__main__":
    sys.exit(main())
