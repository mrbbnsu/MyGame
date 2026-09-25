# WO-008：最小 UI —— 浏览器完整打一局（P3）

> **任务编号 F1 ｜ 执行：建议由 E1 的 worker 继续（上下文最连续），用户可另派。** 依赖：E1 ✅（Adapter v0 已验收，协议见 `adapter/protocol.md`）。
> 目标：玩家在浏览器里**完整打完一局真实规则决斗**（双人热座）。丑没关系，完整和正确是唯一标准——这是通往里程碑 P4 的地基。

## 0. 必读（按序）

1. `E:\Game\adapter\protocol.md` —— 唯一协议依据（new_duel/get_state/respond + pending 结构）
2. `E:\Game\docs\card-display.md` —— 卡面展示三层（L1 原画 + 中文自渲染）
3. `E:\Game\docs\architecture-v2.md` —— UI 只面对 Adapter/服务层，不碰二进制
4. `E:\Game\docs\reports\E1-acceptance.md` —— Adapter 已验证能力边界

## 1. PM 已拍板的决策（直接执行）

| # | 决策 | 理由 |
|---|---|---|
| K1 | 形态 = **本地 HTTP 服务（Node/TS，零 npm 依赖）+ 浏览器纯 JS 前端（ES Modules，无构建步骤）** | 浏览器不能直接跑 TS；协议类型单一来源留在 node 侧；零依赖零构建是项目铁律（Node ≥24 跑 TS 已验证） |
| K2 | 服务职责：静态文件 + `/api/*` 转发 Adapter（服务进程 spawn `python adapter/service.py`，经 `src/adapter/client.ts` 通信）+ `/api/cards` 输出 cards_clean.json 的**精简卡表**（id/name/card_type/flags/race/attribute/level/atk/def/desc，启动时预处理一次缓存） | 14MB 原库不直接喂浏览器 |
| K3 | 布局按任务书 §25：对手（手牌数/怪兽区/魔陷区）在上、我方在下；**场上卡 = 原画缩略 + 中文名 + ATK/DEF + 表示形式**；点击 = 详情浮层（大原画 + 中文效果文本）；无图卡用统一占位图（已知 100268001/003/201/010 无图） | card-display.md 的 L1 策略 |
| K4 | 两套预设卡组从 C1 底稿挑（`data/v1_pool.json` reason=OK）：经典普通怪兽为主 + E1 已验证效果卡（死者苏生/强欲之壶/突进等），各 40 张，存 `data/decks/*.json`；原画用 `python -X utf8 tools/download_art.py --ids ...` 预下载到 `data/art/` | 卡组编辑器是 P7；先让卡组存在 |
| K5 | pending 八类（SELECT_CARD/PLACE/YESNO/OPTION/CHAIN/POSITION/BATTLE/IDLE + SELECT_OTHER 兜底）**全部有可操作 UI**：列表选择 + 取消（cancelable 时） | 最小但完整 |
| K6 | 双人热座：viewer 自动跟随 turn_player，对方回合提示"请交给对方操作"（同屏双人信息隐藏无意义；vs AI 时 viewer 恒为玩家，P5 接入） | v0 简化 |

## 2. 交付物

```
src/ui/server.ts            本地服务（默认 127.0.0.1:8412，零依赖 http）
src/ui/public/index.html    布局骨架
src/ui/public/ui.js         渲染 + 交互（纯 JS ES Module）
src/ui/public/ui.css        样式（清晰 > 好看）
data/decks/classic-dragon.json / classic-warrior.json   两套预设
tests/ui_server.test.ts     /api/* 端点测试（node:test；UI 渲染本身走人工验收）
```

## 3. 验收标准（PM 执行）

1. `npm test` 全绿（含 /api 端点测试：cards 精简表、new_duel/get_state/respond 转发、adapter 进程拉起/回收）
2. **人工验收（PM 开浏览器实际打）**：选预设卡组开局 → 双方从 8000 LP 完整对局到胜负画面；期间出现过的每类 pending 都能操作；非法操作无法提交（列表里没有的选不了）
3. 卡面合规：场上卡显示 原画+中文名+ATK/DEF+表示形式；点击详情有中文效果；盖卡在我方视角显示"盖卡"样式、对方视角不露内容；无图卡显示占位图
4. 对局日志区：最近事件滚动显示（中文卡名，来自精简卡表 join）
5. 红线：`src/ui/public/` 无二进制解析、无卡名硬编码逻辑；前端不直接 spawn 进程（一切经 /api）；服务只监听 127.0.0.1

## 4. 边界（不做）

卡组编辑器（P7）、AI（P5）、动画/音效、联机、观战回放、移动端适配。界面美观度只求"清晰可读"。

## 5. 完成定义（DoD）

验收 1-5 通过 + git 提交（信息：`最小 UI：浏览器完整打一局（F1/WO-008）`）+ 完成说明给 PM（pending 各类型实测截图或描述、协议偏离点、已知限制）。
