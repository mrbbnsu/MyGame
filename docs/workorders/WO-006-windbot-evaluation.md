# WO-006：WindBot 技术调查

> **任务编号 D2 ｜ 执行：worker D（D1 之后）或单独 worker（用户指派）。** 依赖：无硬依赖，建议在 D1 的 P1 笔记之后做（可参考其环境）。
> 性质：**纯调查，不写采用代码**。产出一份评估报告。

## 0. 背景

`docs/architecture-v2.md` 的 AI V0 需要一个"通过 Adapter 获取合法选择并做决策"的起点。Project Ignis 维护的 WindBot 是现成的 YGOPro 系 AI，需要评估其复用价值。

## 1. 调查问题（逐条回答，附证据：代码路径/文件名）

1. 它如何与 duel engine 通讯（协议、进程模型）
2. 它如何获取合法动作
3. 它如何选择动作（决策结构）
4. 是否可以作为我们的 AI V0（直接用 / 包一层用）
5. 通信层是否可以复用（与我们 Adapter 的关系）
6. Deck Executor（每卡组专用脚本）与通用逻辑分别占多少（量化：文件数/行数级即可）
7. 使用任意自定义卡组时，限制在哪里（无 Deck Executor 时 AI 表现如何）

## 2. 交付物

`docs/reports/WINDBOT_EVALUATION.md`：七问逐条回答 + 对我们 AI V0 的建议 + 最终结论（四选一）：

```text
USE            直接采用
PARTIAL_USE    复用通信层或部分逻辑
REFERENCE_ONLY 只作设计参考
NOT_SUITABLE   不适合
```

## 3. 红线

- 只读调查：clone 到 `vendor/`（gitignore，版本记入 VERSIONS.md），不集成、不改其源码、不写采用性代码
- 结论必须基于当前版本实际代码，不凭印象
- 联网非沙箱执行

## 4. 验收标准（PM 执行）

1. 七问全部有答案且附代码证据（文件路径）
2. 第 6 问有量化数据
3. 结论四选一明确，且与我们架构（Adapter 原则）不矛盾；若建议 USE/PARTIAL_USE，说明与 Adapter 的边界怎么划

## 5. 完成定义（DoD）

验收通过 + git 提交（信息：`WindBot 技术调查（D2/WO-006）`）+ 完成说明给 PM。
