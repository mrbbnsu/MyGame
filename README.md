# 卡牌对战游戏

游戏王风味 1v1 卡牌游戏。当前阶段：卡库数据层已就绪，规则与效果系统已定义，下一步做卡池筛选（supported / complexity 标记）和引擎实现。

## 目录

```
docs/
  v1-rules.md        V1 对战规则（冻结版）
  effect-system.md   效果系统规范（引擎契约，加卡的判定依据）
  db-stats.md        卡库统计报告（每次更新卡库后重新生成）
data/
  cards_raw.json     百鸽 YGOCDB 原始整库（14325 条）
  cards_clean.json   游戏用清洗版（14281 张，含召唤机制/种类/中文字段）
  cards.zip(.md5)    原始下载包及其校验值
  .cards_md5         当前卡库版本基线
  quality_notes.md   数据质量记录
tools/
  update_db.py            启动时检查卡库更新（MD5 未变不下载）
  build_cards_clean.py    清洗脚本（raw -> clean + 统计报告）
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
python tools/update_db.py            # 检查并更新卡库（--force 强制）
python tools/build_cards_clean.py    # 重新清洗 + 生成统计报告
```

## 路线图

- [x] 下载整库、清洗、统计
- [ ] 从 14281 张筛 V1 卡池：按 `docs/effect-system.md` 的枚举给每张卡标 `supported` / `complexity`
- [ ] 用 YGOPRODeck 补 Link 箭头、系列分类、禁限表
- [ ] 卡图本地化下载（`id.jpg`，禁止热链）
- [ ] 引擎实现（以 `docs/v1-rules.md` + `docs/effect-system.md` 为契约）
