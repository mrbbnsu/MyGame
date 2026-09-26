# 运行手册（RUNBOOK）

> 常用命令 + 待跑清单。PM 维护，2026-09-25。

## 常用命令

```bash
# 测试（全部：引擎 fallback + Adapter 集成 + UI 端点）
npm test

# Adapter 自测（43 项，含信息隐藏/确定性）
python -X utf8 adapter/selftest.py

# 最小 UI（F1）：启动后浏览器打开 http://127.0.0.1:8412
node src/ui/server.ts

# D1 探针复跑（ocgcore 集成验证，vendor/ 就绪时）
python -X utf8 spike/ocg/miniduel.py       # P2 最小对局
python -X utf8 spike/ocg/p3_scripts_duel.py  # P3 真实效果卡
python -X utf8 spike/ocg/p4_id_alignment.py  # P4 ID 三方对齐

# 数据工具
python tools/update_db.py                  # 卡库更新
python -X utf8 tools/query_card.py 89631139
python -X utf8 tools/download_images.py --sample 20   # 英文实体图（L3）
python -X utf8 tools/download_art.py --sample 20      # 原画（L1）
python -X utf8 tools/screen_v1_pool.py                # 卡池初筛（幂等）
```

## 待跑清单（按需执行）

| # | 事项 | 命令/条件 | 状态 |
|---|---|---|---|
| 1 | `data/art/` 全库 14281 张原画跑批 | `python -X utf8 tools/download_art.py`（约 1 小时 / ~2GB，断点续传） | ⏸ 待用户批准（建议 P7 卡组编辑器前） |
| 2 | `data/images/` 全库英文实体图跑批 | `python -X utf8 tools/download_images.py` | ⏸ 待用户批准（低优先级，L3 兜底层） |
| 3 | F1 终局横幅人工目验 | 启动 UI 服务后打一局到胜负，看"玩家 X 获胜！"横幅（自动化取证因测试环境未留截图，见 F1-acceptance.md 已知限制 2） | ⏸ 用户随手可验 |
| 4 | cdb 定期刷新 | EDOPro 发行版更新后重取 `vendor/edopro` 的 cards.cdb（D1-report 摩擦点 6） | ⏸ 按需 |
| 5 | 下一工单 G1（AI V0） | 等 PM 开单（设计输入已备：D2-acceptance.md 三条） | 📋 待开单 |
