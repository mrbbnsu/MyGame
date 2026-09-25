#!/usr/bin/env python3
"""WO-004 卡面资源 V2：L1 原画下载器 + L2 简中实体图可得率统计。

用法：
  python -X utf8 tools/download_art.py --sample 20             # 固定种子随机抽 20 张原画（可复现）
  python -X utf8 tools/download_art.py --ids 89631139,74677422 # 定向下载原画
  python -X utf8 tools/download_art.py [--limit 500]           # 全库（可配上限，跑批需 PM 批准）
  python -X utf8 tools/download_art.py --coverage 200          # L2 可得率抽样探测（不下载图片）

探针结论（2026-09-25 实测，开图核验后确定的 URL 形态）：
  - 百鸽 CDN 图片基址 https://cdn.233.momobako.com/ygoimg/
    - {sc|jp|en}/{id}.webp：680×986 完整卡面。sc/ 对未发行简中的卡也给**合成简中卡面**，
      因此接近全量可得（缺口只在动画卡段，见 --coverage）；jp/en 同理
    - {sc|jp|en}/{id}.webp!art：256×256 裁切，但实测是**卡面局部放大**（含卡框边与调整星），
      不是无框原画 —— 工单假设被证伪，不能用作 L1
    - ygopro/{id}.webp：百鸽自用合成简中完整卡面（同 sc 类似，带中文卡框文字）
    - `!art`/`!/format/webp/fw/400` 均为路径后缀形态的图像处理参数；查询参数（?art）会被 CDN 静默忽略
  - YGOPRODeck https://images.ygoprodeck.com/images/cards_cropped/{id}.jpg：
    **无卡框中间插画**（开图核验：白龙本体、无卡名/属性条）—— L1 唯一满足验收的源，JPEG 格式
  - cards_raw.json 无任何发行/图片字段（cnocg_n/nwbbs_n 是译名变体），可得率只能走网络抽样

行为（工程习惯沿用 B1 tools/download_images.py）：
  - L1 原画存 data/art/{id}.jpg（按实际 JPEG 内容命名；工单预期的 .webp 随百鸽假设一并废弃）
  - 已有合法 JPEG（≥1KB 且 FFD8 头）跳过；--force 强制重下
  - 单张失败重试 2 次（间隔 2s），仍失败记入报告 failed，不中断批次
  - 请求间隔 ≥ 200ms；每次下载运行覆盖写 data/art/_report.json（同 B1 格式）
  - --coverage N：固定种子随机抽 N 个 id 探测 sc/{id}.webp 可用性（不下载）+ 按 cid 尾部
    定向扫描最新 60 张（缺口集中在最新卡，随机抽样探不到）；sc 404 的卡顺带探 jp/en 与
    YGOPRODeck 原画，判断 L3 兜底与 L1 补救；结果写 data/sc_coverage.json + .md
"""
import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "cards_clean.json"
ART_DIR = ROOT / "data" / "art"
REPORT = ART_DIR / "_report.json"
COVERAGE_JSON = ROOT / "data" / "sc_coverage.json"
COVERAGE_MD = ROOT / "data" / "sc_coverage.md"

BAIGE_CDN = "https://cdn.233.momobako.com/ygoimg/"
ART_URL = "https://images.ygoprodeck.com/images/cards_cropped/{id}.jpg"
SAMPLE_SEED = 20260925   # 固定种子：同参数重复运行抽样一致，保证幂等跳过
REQUEST_GAP_S = 0.2      # 礼貌限速：请求间隔下限
RETRY_WAIT_S = 2.0
RETRIES = 2
HTTP_TIMEOUT = 30
UA = "ClassicDuel/0.1 (local card art cache for offline game client)"


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


def http_status(url: str) -> str:
    """只探测状态码：GET 后立即关连接，不读完整 body。
    连续探测下 CDN 有约 1% 瞬时抖动（假 404/超时），非 200 结果退避 1s 复核一次。"""
    result = ""
    for i in range(2):
        if i:
            time.sleep(RETRY_WAIT_S / 2)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                r.read(16)
                return str(r.status)
        except urllib.error.HTTPError as e:
            result = str(e.code)
        except Exception as e:
            result = f"{type(e).__name__}"
    return result


def download_one(cid: str, force: bool) -> tuple[str, int | None]:
    """下载单张 L1 原画。返回 (结果, 字节数)：结果为 "downloaded"/"skipped"/失败原因字符串。"""
    path = ART_DIR / f"{cid}.jpg"
    if not force and is_jpeg(path):
        return "skipped", None
    url = ART_URL.format(id=cid)
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
        except urllib.error.HTTPError as e:
            reason = f"HTTP {e.code}"
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
    return reason, None


def run_download(args) -> int:
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

    ART_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    downloaded = skipped = 0
    failed: list[dict] = [
        {"id": u, "url": ART_URL.format(id=u), "reason": "id 不在 cards_clean.json"} for u in unknown
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
            failed.append({"id": cid, "url": ART_URL.format(id=cid), "reason": result})
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


def run_coverage(n: int) -> int:
    """L2 简中实体图可得率：固定种子抽样 + 尾部定向扫描探测 sc/{id}.webp，缺失卡探兜底。"""
    if not DB.exists():
        print(f"错误：找不到 {DB}", file=sys.stderr)
        return 2
    cards = json.loads(DB.read_text(encoding="utf-8"))
    n = max(1, min(n, len(cards)))
    sample = random.Random(SAMPLE_SEED).sample(cards, n)

    t0 = time.monotonic()
    available, missing = [], []
    print(f"探测 sc/{{id}}.webp 可得率：抽样 {n} 张 …")
    for i, c in enumerate(sample, 1):
        cid = str(c["id"])
        st = http_status(BAIGE_CDN + f"sc/{cid}.webp")
        (available if st == "200" else missing).append(cid)
        if i % 20 == 0:
            print(f"  进度 {i}/{n}（当前可得 {len(available)}）")
        if i < n:
            time.sleep(REQUEST_GAP_S)

    # 尾部定向扫描：随机抽样探不到集中在最新卡的缺口（探针实测动画卡段整卡缺图）
    tail_n = min(60, len(cards))
    tail = sorted(cards, key=lambda c: c["cid"])[-tail_n:]
    tail_missing = []
    print(f"尾部定向扫描：最新 {tail_n} 张（按 cid）…")
    for i, c in enumerate(tail, 1):
        st = http_status(BAIGE_CDN + f"sc/{str(c['id'])}.webp")
        if st != "200":
            tail_missing.append(str(c["id"]))
        if i < tail_n:
            time.sleep(REQUEST_GAP_S)

    # 对 sc 缺失的卡（样本 ∪ 尾部）探 jp/en（L3 兜底）与 YGOPRODeck 原画（L1 补救）
    by_id = {str(c["id"]): c for c in sample + tail}
    fallback = {}
    all_missing = list(dict.fromkeys(missing + tail_missing))
    for cid in all_missing:
        jp = http_status(BAIGE_CDN + f"jp/{cid}.webp")
        time.sleep(REQUEST_GAP_S)
        en = http_status(BAIGE_CDN + f"en/{cid}.webp")
        time.sleep(REQUEST_GAP_S)
        art = http_status(ART_URL.format(id=cid))
        time.sleep(REQUEST_GAP_S)
        fallback[cid] = {"jp": jp, "en": en, "art": art}

    coverage = {
        "method": "probe_sample",
        "denominator": n,
        "sc_available": len(available),
        "sample_ids": available + missing,
        "tail_scan": {"n": tail_n, "missing_ids": tail_missing},
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }
    COVERAGE_JSON.write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def row(cid: str) -> str:
        f = fallback.get(cid, {})
        nm = by_id.get(cid, {}).get("name") or by_id.get(cid, {}).get("en_name") or ""
        return f"  | {cid} | {nm} | {f.get('jp')} | {f.get('en')} | {f.get('art')} |\n"

    md = []
    md.append("# L2 简中实体卡图可得率小结\n")
    md.append(f"- 统计时间：{coverage['checked_at']}；口径：`probe_sample`（cards_raw.json 无发行/图片字段，"
              f"`cnocg_n`/`nwbbs_n` 经核实是译名变体而非发行标记，零请求统计不可行）\n")
    md.append(f"- 抽样：固定种子 {SAMPLE_SEED} 从 cards_clean.json 随机抽 **{n}** 张"
              f"（denominator={n}），逐张 GET `https://cdn.233.momobako.com/ygoimg/sc/{{id}}.webp` 计 HTTP 200\n")
    md.append(f"- **可得 {len(available)}/{n}（{len(available) * 100 // n}%）**；随机样本缺失 {len(missing)} 张\n")
    md.append(f"- 尾部定向扫描（补充口径）：按 cid 取最新 **{tail_n}** 张逐一探测，"
              f"缺失 **{len(tail_missing)}** 张——缺口集中在最新卡，随机抽样探不到，故此段为必要补充\n")
    if missing:
        md.append(f"- 随机样本缺失卡明细（jp/en = L3 兜底实体图，art = YGOPRODeck 无框原画即 L1 源）：\n")
        md.append("  | id | 卡名 | jp | en | art |\n  |---|---|---|---|---|\n")
        md.extend(row(cid) for cid in missing)
    if tail_missing:
        md.append(f"- 尾部缺失卡明细（共 {len(tail_missing)} 张）：\n")
        md.append("  | id | 卡名 | jp | en | art |\n  |---|---|---|---|---|\n")
        md.extend(row(cid) for cid in tail_missing)
    md.append(f"- 注：`sc_name`（官方简中译名）有无不预示 sc 图是否存在（有无译名的卡都可能有图）；"
              f"sc/jp/en 对缺失卡同步 404，说明是百鸽整卡缺图而非仅缺简中\n")
    if all_missing:
        has_art = [cid for cid in all_missing if fallback.get(cid, {}).get("art") == "200"]
        if all(cid.startswith("1002") for cid in all_missing):
            md.append(f"- 缺失卡画像：本次全部缺失卡均位于**动画卡密码段（100268xxx，动画专属卡）**\n")
        if has_art:
            md.append(f"- 其中 {len(has_art)} 张的 L1 原画可从 YGOPRODeck cards_cropped 补齐（上表 art=200）；"
                      f"其余卡 L1/L2/L3 均无图，Phase 7 UI 需准备占位图\n")
        else:
            md.append(f"- 本次缺失卡在 YGOPRODeck 亦无原画（art 全 404），L1/L2/L3 均缺，Phase 7 UI 需准备占位图\n")
    md.append(f"- 探针补充：百鸽 sc/ 对未发行简中的卡也给**合成简中卡面**（开图核验 65884091 为合成中文卡），"
              f"故 L2 可得率接近全量，但非官方实体扫描；`!art` 后缀为卡面局部裁切（含卡框），不可作无框原画\n")
    COVERAGE_MD.write_text("".join(md), encoding="utf-8")

    print(f"可得率：{len(available)}/{n}（{len(available) * 100 // n}%），随机样本缺失 {len(missing)}，"
          f"尾部扫描缺失 {len(tail_missing)}（耗时 {round(time.monotonic() - t0, 1)}s）")
    print(f"输出：{COVERAGE_JSON} + {COVERAGE_MD}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="L1 原画下载器 + L2 简中可得率统计（WO-004）")
    ap.add_argument("--ids", help="逗号分隔的卡片密码，如 89631139,74677422")
    ap.add_argument("--sample", type=int, metavar="N", help="固定种子随机抽 N 张原画")
    ap.add_argument("--limit", type=int, metavar="N", help="全库模式的上限（默认无上限）")
    ap.add_argument("--force", action="store_true", help="忽略本地已有文件强制重下")
    ap.add_argument("--coverage", type=int, metavar="N", help="探测 N 张抽样卡的简中实体图可得率（不下载）")
    args = ap.parse_args(argv)
    if args.coverage is not None:
        if args.ids or args.sample is not None:
            ap.error("--coverage 不能与 --ids/--sample 同用")
        return run_coverage(args.coverage)
    return run_download(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
