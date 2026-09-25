# WO-004：卡面资源体系 V2（原画下载 + 简中实体图可得率）

> **任务编号 B2 ｜ 执行：worker B。** 依赖：B1 ✅。
> 背景决策：`docs/card-display.md` —— 核心展示改为"原画 + 游戏渲染中文卡面"，实体卡图降级为详情页资源。
> 本工单自包含；只做数据侧，不做游戏内渲染。

## 0. 必读（按序）

1. `E:\Game\docs\card-display.md` —— 卡面体系决策（L1/L2/L3 三层）
2. `E:\Game\docs\workorders\WO-002-card-images.md` —— B1 工单（跳过/重试/限速/报告等工程习惯沿用）
3. `E:\Game\tools\download_images.py` —— B1 实现（CLI 风格、报告格式保持一致）

## 1. 第一步：探针（禁止按假设写批量逻辑）

1. **原画（L1）**：验证百鸽 CDN 原画的确切 URL 形态与格式。已知线索：简中卡图目录 `/ygoimg/sc/{cardid}.webp`、`!art` 参数可取 256×256 中间插画——两者都只是**待验证假设**，用 89631139、74677422 等已知 id 实测（注意 `!art` 可能是路径后缀也可能是查询参数，把实测可用的形态记下来）。同时确认返回是 webp 还是其他格式
2. **简中实体图（L2）**：同一目录无 `!art` 时返回完整卡图？日文/英文目录是否存在（`/ygoimg/jp/`、`/ygoimg/en/` 之类）？只探测记录，不批量下载
3. **零请求统计路径**：先检查 `data/cards_raw.json` 是否自带"各语言是否发行/图片路径"类字段（百鸽发行数据区分日/英/简中是否发行）。若自带 → L2 可得率直接统计，零网络请求
4. 探针结论（确切 URL、返回格式、字段名）必须写进完成说明

## 2. 交付物

```
tools/download_art.py          L1 原画下载器（--ids/--sample/--limit/--force；跳过已有、单张重试 2 次、请求间隔 ≥200ms、固定种子抽样；报告 data/art/_report.json 同 B1 格式）
data/art/{id}.webp             原画缓存（--sample 20 级别样本量）
data/sc_coverage.json          L2 可得率：{method: "db_field"|"probe_sample", denominator, sc_available, sample_ids?: [...], checked_at}
data/sc_coverage.md            统计小结（数字口径必须与 json 一致）
```

## 3. 红线

- 只新增/改动 `tools/download_art.py`、`data/art/`、`data/sc_coverage.{json,md}`；不动 src/、不动 B1 的 `tools/download_images.py` 与 `data/images/`
- L2/L3 **不批量下载**；L1 只做样本量（全库任何跑批都需 PM 批准）
- 联网命令非沙箱执行；Python 一律 `python -X utf8`；标准库优先
- 不做游戏内渲染（那是 Phase 7 UI 工单的事）

## 4. 验收标准（PM 执行）

1. 探针结论完整：原画确切 URL 形态 + 实测格式 + `!art` 行为；日/英目录探测结果；cards_raw.json 字段结论
2. `--sample 20` 原画成功、格式合法（RIFF/WEBP 或 JPEG 文件头、≥1KB）、文件落在 `data/art/`
3. 抽 3 张开图核对：原画 = **无卡框的中间插画**（如 89631139 应为白龙本体、没有卡名/属性条），PM 会开图
4. 幂等重跑：秒级、downloaded=0
5. `sc_coverage` 统计自洽：method 口径明确（db_field 零请求 / probe_sample 注明抽样数），数字与 md 一致

## 5. 完成定义（DoD）

验收 1-5 自测通过 + git 提交（信息：`卡面资源 V2：原画下载 + 简中可得率（B2/WO-004）`，`data/art/` 加入 .gitignore）+ 完成说明（探针确切结论、可得率口径与数字、failed 与补充决定）。
