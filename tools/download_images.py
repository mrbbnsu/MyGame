#!/usr/bin/env python3
"""Phase 2 卡图下载器（WO-002）：从 YGOPRODeck 图片 CDN 拉取卡图到本地缓存。

用法：
  python -X utf8 tools/download_images.py --sample 20            # 固定种子随机抽 20 张（可复现）
  python -X utf8 tools/download_images.py --ids 89631139,74677422 # 定向下载
  python -X utf8 tools/download_images.py [--limit 500]          # 全库（可配上限，跑批需 PM 批准）

行为：
  - 图片存 data/images/{卡片密码}.jpg，与 cards_clean.json 的 id 一一对应
  - 已有合法 JPEG（≥1KB 且文件头 FFD8）跳过；--force 强制重下
  - 单张失败重试 2 次（间隔 2s），仍失败记入报告 failed，不中断批次
  - 请求间隔 ≥ 200ms；每次运行覆盖写 data/images/_download_report.json
"""
import argparse
import json
import random
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cards_clean.json"
IMG_DIR = ROOT / "data" / "images"
REPORT = IMG_DIR / "_download_report.json"

CDN_URL = "https://images.ygoprodeck.com/images/cards/{id}.jpg"
SAMPLE_SEED = 20260925   # 固定种子：同参数重复运行抽样一致，保证幂等跳过
REQUEST_GAP_S = 0.2      # 礼貌限速：请求间隔下限
RETRY_WAIT_S = 2.0
RETRIES = 2
HTTP_TIMEOUT = 30
UA = "ClassicDuel/0.1 (local card image cache for offline game client)"


def is_jpeg(path: Path) -> bool:
    try:
        if path.stat().st_size < 1024:
            return False
        with path.open("rb") as f:
            return f.read(2) == b"\xff\xd8"
    except OSError:
        return False


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return r.read()


def download_one(cid: str, force: bool) -> tuple[str, int | None]:
    """下载单张。返回 (结果, 字节数)：结果为 "downloaded"/"skipped"/失败原因字符串。"""
    path = IMG_DIR / f"{cid}.jpg"
    if not force and is_jpeg(path):
        return "skipped", None
    url = CDN_URL.format(id=cid)
    reason = ""
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(RETRY_WAIT_S)
        try:
            body = fetch(url)
            if len(body) >= 1024 and body[:2] == b"\xff\xd8":
                path.write_bytes(body)
                return "downloaded", len(body)
            reason = f"响应不是合法 JPEG（{len(body)} 字节，文件头 {body[:2].hex().upper()}）"
        except Exception as e:  # 网络/HTTP 错误都算单张失败，重试后进报告
            reason = f"{type(e).__name__}: {e}"
    return reason, None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="YGOPRODeck 卡图本地缓存下载器（WO-002）")
    ap.add_argument("--ids", help="逗号分隔的卡片密码，如 89631139,74677422")
    ap.add_argument("--sample", type=int, metavar="N", help="固定种子随机抽 N 张")
    ap.add_argument("--limit", type=int, metavar="N", help="全库模式的上限（默认无上限）")
    ap.add_argument("--force", action="store_true", help="忽略本地已有文件强制重下")
    args = ap.parse_args(argv)

    if not DB.exists():
        print(f"错误：找不到 {DB}", file=sys.stderr)
        return 2
    cards = json.loads(DB.read_text(encoding="utf-8"))
    known = {str(c["id"]) for c in cards}

    if args.ids:
        selected, unknown = [], []
        for w in (s.strip() for s in args.ids.split(",")):
            if not w:
                continue
            norm = w.lstrip("0") or w  # 与 query_card.py 同款前导零归一化
            (selected if norm in known else unknown).append(norm)
    elif args.sample is not None:
        n = max(0, min(args.sample, len(cards)))
        selected = [str(c["id"]) for c in random.Random(SAMPLE_SEED).sample(cards, n)]
        unknown = []
    else:
        selected = [str(c["id"]) for c in cards]
        if args.limit is not None:
            selected = selected[:max(0, args.limit)]
        unknown = []

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    downloaded = skipped = 0
    failed: list[dict] = [
        {"id": u, "url": CDN_URL.format(id=u), "reason": "id 不在 cards_clean.json"} for u in unknown
    ]
    total = len(selected)
    for i, cid in enumerate(selected, 1):
        result, size = download_one(cid, args.force)
        if result == "downloaded":
            downloaded += 1
            print(f"[{i}/{total}] {cid} 下载成功 ({size // 1024}KB)")
        elif result == "skipped":
            skipped += 1
        else:
            failed.append({"id": cid, "url": CDN_URL.format(id=cid), "reason": result})
            print(f"[{i}/{total}] {cid} 失败：{result}")
        if result != "skipped" and i < total:
            time.sleep(REQUEST_GAP_S)  # 限速只约束真实 HTTP 请求；重试等待(2s)已超过间隔

    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "requested": total + len(unknown),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "elapsed_s": round(time.monotonic() - t0, 2),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"完成：请求 {report['requested']} 张，下载 {downloaded}，跳过 {skipped}，"
          f"失败 {len(failed)}（耗时 {report['elapsed_s']}s）")
    print(f"报告：{REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
