# Phase 0 报告：项目骨架（2026-09-25）

## 已完成

- 目录结构：`src/core`（状态模型）、`src/engine`（规则引擎）、`tests/`、`docs/`、`data/`、`tools/`
- Git 仓库初始化（含 .gitignore）
- 配置：`package.json`（零 npm 依赖）、`tsconfig.json`、规则配置 `src/core/config.ts`（Classic/Original 双模式参数）
- 日志系统：`src/core/log.ts`（debug/info/warn/error 分级，默认静默）
- 测试框架：node:test（Node 24 原生跑 TS），`npm test`
- 游戏状态数据模型：`CardDef` / `CardInstance` / `ZoneRef` / `PlayerState` / `GameState`，纯 JSON 可克隆（AI 搜索前提）
- 任务树：`docs/TASKS.md`（Phase 0～8 + 依赖 + 验收 + 横切任务）

## 技术栈决策

引擎/AI/UI 用 **TypeScript（Node ≥24 原生执行，零依赖）**；数据管道保留 Python。
理由：`docs/effect-system.md` 契约已指向 JS 工具链；UI（任务书 §25）最终需要浏览器/前端技术，同一语言避免引擎移植；node:test 免安装，适配离线环境。

## 未完成（按计划顺延）

- UI 目录（Phase 7 前建）
- Effect/Deck/AI/modes 目录（对应 Phase 4+ 建立时创建）

## 已知问题

- `node --test <目录>` 在当前版本把目录参数当模块加载（报 MODULE_NOT_FOUND），已改用无参数递归发现，无实际影响。

## 测试情况

`npm test`：3/3 通过（规则默认值、RNG 可复现、状态可结构化克隆）。

## 下一阶段

Phase 1 收尾验证（Card ID 查询验收）→ Phase 3 最小 Rule Engine。
