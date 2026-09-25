# 卡牌对战游戏

游戏王风味 1v1 卡牌游戏。当前阶段：**Phase 0/1 已完成（骨架 + 中文卡库数据层），Phase 2/3 以工单形式待分发**。

## 工作流（PM / Worker 分工）

- **PM**：维护 `docs/TASKS.md` 任务树，制定工单（做什么 / 边界 / 交付物 / 验收标准），完工后按工单逐条验收；**PM 不亲手改代码**
- **Worker A/B/C**：用户已在外部会话派发，任务编号 A1（规则引擎，🔴）/ B1（卡图，🟡）/ C1（卡池初筛，🟢），执行中
- **秘书 Worker**（`docs/workorders/SECRETARY.md`）：PM 直接控制的子代理，只做跨任务小改动与验收后小修（≤50 行/列表式），改完 PM 复查 diff 并代为提交

## 目录

```
docs/
  TASKS.md           任务树（Phase 0~8、依赖、验收、工单索引）★项目入口
  v1-rules.md        V1 对战规则（冻结版）
  effect-system.md   效果系统规范（引擎契约，加卡的判定依据）
  db-stats.md        卡库统计报告（每次更新卡库后重新生成）
  workorders/        工单（WO-xxx，PM 制定，用户分发，完成后 PM 验收）
  reports/           阶段报告
src/
  core/              状态模型（config/log/rng/card/zones/state，Phase 0 已定型）
  engine/            规则引擎（Phase 3，工单 WO-001）
tests/               node:test 测试（npm test）
data/
  cards_raw.json     百鸽 YGOCDB 原始整库（14325 条）
  cards_clean.json   游戏用清洗版（14281 张，含召唤机制/种类/中文字段）
  cards.zip(.md5)    原始下载包及其校验值
  .cards_md5         当前卡库版本基线
  quality_notes.md   数据质量记录
tools/
  update_db.py            启动时检查卡库更新（MD5 未变不下载）
  build_cards_clean.py    清洗脚本（raw -> clean + 统计报告）
  query_card.py           按 Card ID 查询卡牌信息
```

## 数据源

- **中文卡名 / 效果文本 / 基础数据**：[百鸽 YGOCDB](https://ygocdb.com/api)（`/api/v0/cards.zip`，整库下载，MD5 校验仅在有更新时重新下载）
- **后续补充**：[YGOPRODeck API](https://db.ygoprodeck.com/api/v7/cardinfo.php)（英文库，用于 Link 箭头 `linkmarkers`、系列/卡组分类、禁限表、卡图下载——卡图必须本地存储，禁止热链）
- **统一主键：卡片密码 `id`**（YGOCDB 的 `id` = YGOPRODeck 的 `id` = 卡图文件名）

## cards_clean.json 字段

`id` 密码主键 / `name` 显示名（cn_name 回退链） / `card_type` MONSTER|SPELL|TRAP / `flags`（NORMAL、EFFECT、FUSION…TUNER 等，可叠加）/ `summon_mech`（FUSION|SYNCHRO|XYZ|LINK|RITUAL，额外卡组用）/ `attribute` `race` 中文 / `level` `link` `lscale` `rscale` / `atk` `def`（`"?"` = 原文问号）/ `desc` `pdesc`（灵摆效果） / `spell_kind` `trap_kind` / `setcode` `ot` 原始值 / `supported` `complexity` 预留 null。

> 注意：本库 type 位是 **Master Duel 布局**（如 LINK=0x4000000、PENDULUM=0x1000000），与标准 ygocore 常量不同；魔法/陷阱种类以 `text.types` 文本为准。清洗脚本里已固化，勿按旧常量改动。

## 常用命令

```bash
npm test                             # TS 测试（node:test，Node ≥ 24）
python tools/update_db.py            # 检查并更新卡库（--force 强制）
python tools/build_cards_clean.py    # 重新清洗 + 生成统计报告
python tools/query_card.py 89631139  # 按 Card ID 查卡
```

## 路线图

- [x] 下载整库、清洗、统计（Phase 1）
- [x] 项目骨架：TS 零依赖 + 状态模型 + 测试框架（Phase 0）
- [ ] 最小规则引擎（Phase 3，WO-001 已定义待分发）
- [ ] 卡图本地化下载（Phase 2，WO-002 可并行）
- [ ] V1 卡池初筛（WO-003 可并行）
- [ ] Effect Engine V1 → 魔法陷阱 → AI（Phase 4~6，依次开单）
