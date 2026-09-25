# WO-002：Phase 2 卡图下载器（Python）

> 优先级：🟡 可与 WO-001 并行（Phase 7 前必须完成）
> 依赖：Phase 1 已完成（`data/cards_clean.json`，14281 张，主键 = 卡片密码 id）
> 本工单自包含；只改 `tools/` 与 `data/images/`，不碰引擎代码。

## 0. 背景与约束

- 卡图必须**本地存储，禁止热链**（游戏运行时不做任何在线加载）
- 文件名 = `{卡片密码}.jpg`，与 `data/clean` 的 `id` 一一对应
- 目标目录 `data/images/`（加入下载器自动创建）
- **网络注意（本机环境实测）**：bash 里的联网命令必须以非沙箱方式执行；DNS 解析失败 ≠ 域名错误，先换执行方式再怀疑数据源。若 API 整体不可达，停下汇报，不要瞎换源
- 图片源：YGOPRODeck（`https://db.ygoprodeck.com/api/v7/cardinfo.php`）。**先小样本验证真实响应结构，禁止假设字段名**；图片 CDN 直链大概率是 `https://images.ygoprodeck.com/images/cards/{id}.jpg`，同样先用 5 张验证再写批量逻辑

## 1. 交付物

```
tools/download_images.py    下载器（仅标准库 or requests，若 requests 不可用就用 urllib）
data/images/*.jpg           卡图缓存（本工单只要求样本量，见验收）
data/images/_download_report.json   运行报告（见下）
```

## 2. 功能要求

`python -X utf8 tools/download_images.py [--ids id1,id2,...] [--sample N] [--limit N] [--force]`

1. **选卡**：`--ids` 指定；否则 `--sample N` 从 cards_clean.json 随机抽 N 张（固定随机种子，可复现）；两者都缺省时 = 全库（配合 `--limit` 控制上限，默认无上限）
2. **跳过已有**：目标文件已存在且是合法 JPEG（≥1KB 且文件头 FFD8）则跳过；`--force` 强制重下
3. **失败处理**：单张失败重试 2 次（间隔 2s），仍失败记入报告的 `failed` 数组（含 id、URL、原因），不让单张失败中断批次
4. **礼貌限速**：请求间隔 ≥ 200ms
5. **运行报告** `_download_report.json`：`{run_at, requested, downloaded, skipped, failed:[...], elapsed_s}`，每次运行覆盖写
6. **不重复下载**：重复运行同参数，第二次应全部 skipped、秒级完成

## 3. 明确不做

不做并发池（串行+限速够用）、不做 UI、不做格式转换、不改 cards_clean.json、不下载全库 14281 张（验收只要求样本；全库跑批等 PM 另行批准）。

## 4. 验收标准（PM 执行）

1. `python -X utf8 tools/download_images.py --sample 20`：退出码 0，`data/images/` 新增 ≥ 20 张（failed 允许 ≤2 且有原因记录）
2. 抽 5 张人工核对：文件名 id → `tools/query_card.py <id>` 的卡名与图片内容一致（PM 会开图看）
3. 所有文件为合法 JPEG（文件头 FFD8、非 HTML 错误页）
4. 再跑一次同命令：秒级完成、`downloaded=0 skipped=20`
5. `--ids 89631139,74677422` 定向下载青眼白龙与真红眼黑龙成功

## 5. 完成定义（DoD）

验收 1-5 全过 + git 提交（`Phase 2: 卡图下载器（WO-002）`，`data/images/` 样本图不入库，.gitignore 加 `data/images/`）+ 完成说明（实际 API 字段结构记录、failed 原因）。
