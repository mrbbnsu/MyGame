# B1（WO-002 卡图下载器）验收记录 —— ✅ 通过

- 执行：worker B ｜ 提交：`71aa244` ｜ 验收：PM（2026-09-25）

## 验收结果（对照工单第 4 节）

| # | 标准 | 结果 |
|---|---|---|
| 1 | `--sample 20` 退出码 0、新增 ≥20 张 | ✅ 20/20 成功，failed=0 |
| 2 | 抽查 id→卡名与图片一致 | ✅ query_card 核对 3 张一致（65884091 入魔死神塔那托斯 / 56058888 王宫的陷落 / 645087 电子界工具）；开图目视 2 张：89631139 青眼白龙（光/8星/3000-2500）、74677422 真红眼黑龙（暗/7星/2400-2000），卡面数值与库数据吻合 |
| 3 | 全部为合法 JPEG | ✅ 22/22 通过 FFD8 头 + FFD9 尾 + ≥1KB 校验 |
| 4 | 重复运行秒级、downloaded=0 | ✅ PM 复跑：0 下载 20 跳过，elapsed 0.0s |
| 5 | 定向下载青眼/真红眼 | ✅ 文件在且内容正确 |

## 代码与红线检查

- CLI 与工单一致（--ids/--sample/--limit/--force）；固定种子抽样可复现
- 跳过已有（FFD8+≥1KB）、单张重试 2 次（间隔 2s）不中断批次、请求间隔 200ms 且只约束真实请求（合理修正，工单本意即如此）
- 报告格式 `{run_at, requested, downloaded, skipped, failed, elapsed_s}` 覆盖写 ✅
- 只新增 `tools/download_images.py` + `.gitignore` 一行；`data/images/` 不入库；探针临时文件已清理；工作区干净 ✅
- 实测结论（worker 提供，PM 认可）：API `card_images[].image_url` 与 CDN 直链 `images.ygoprodeck.com/images/cards/{id}.jpg` 完全一致，直接构造直链省一次 API 查询 ✅

## 遗留（需用户决策）

- **全库 14281 张跑批未批准**（工单明确禁止擅自跑）。预估：串行+限速约 2~3 小时、磁盘约 2GB。批准后命令：`python -X utf8 tools/download_images.py`（断点续传语义：已存在即跳过）
