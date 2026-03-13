# 目录结构设计

## 三域隔离

```
huoxingfarm-loop/
│
├── [人类域] 项目资料
│   ├── README.md            ← 项目介绍
│   ├── DESIGN.md            ← 系统设计文档
│   ├── STRUCTURE.md         ← 本文件
│   └── project/
│       ├── milestones.md    ← 里程碑规划（人类维护）
│       └── reports/         ← 从智能体产出提炼的人类可读报告
│
├── [代码域] 智能体运行引擎
│   └── src/
│       ├── run.py           ← Controller 主程序
│       ├── farmer.py        ← 农夫调用逻辑
│       ├── singer.py        ← 歌者调用逻辑
│       ├── .env.example     ← 环境变量模板
│       └── prompts/         ← 角色提示词（人类维护，代码读取）
│           ├── farmer.md
│           ├── singer.md
│           └── perspectives.json
│
└── [智能体域] 进化目录（智能体的世界）
    └── agent/
        │
        ├── history/         ← 史书（农夫的阅读区）
        │   ├── INDEX.md     ← 总目：使命+纪元一览+导航（全角色可见）
        │   ├── epochs/      ← 纪元史书（全角色可见，纪元完结后封存）
        │   │   ├── epoch-001.md
        │   │   ├── epoch-002.md
        │   │   └── ...
        │   └── current/     ← 当前纪元区（农夫主要读取区）
        │       ├── briefing.md  ← 农夫启动包（Controller每轮生成）
        │       └── epoch.md     ← 当前纪元进展+验收标准+文明进度表
        │
        ├── civilizations/   ← 文明记录（按纪元隔离）
        │   ├── epoch-001/   ← 纪元1所有文明
        │   │   ├── civ-001/
        │   │   │   ├── farmer.md  ← 农夫产出
        │   │   │   └── singer.md  ← 歌者评价
        │   │   ├── civ-002/
        │   │   │   ├── farmer.md
        │   │   │   └── singer.md
        │   │   └── ...
        │   ├── epoch-002/   ← 纪元2所有文明
        │   └── ...
        │
        └── state/           ← 运行状态（Controller读写）
            ├── epoch.json       ← 当前纪元配置（命题/验收标准/token预算）
            ├── epoch-answers.md ← 所有已完成纪元答案（永久积累）
            ├── discoveries.md   ← 当前纪元已知定律
            └── scores.json      ← 分数历史
```

---

## 可见性规则

### 农夫（最小可见性）

农夫每次文明开始，**只能看到**：

| 文件 | 说明 |
|---|---|
| `agent/history/current/briefing.md` | **主入口**，Controller每轮生成，包含启动所需全部信息 |
| `agent/history/current/epoch.md` | 当前纪元进展（命题/验收标准/文明进度摘要） |
| `agent/history/INDEX.md` | 史书总目 |
| `agent/history/epochs/epoch-NNN.md` | 所有已完成纪元的终章答案 |
| `agent/civilizations/epoch-{当前}/` | **当前纪元**的文明记录（不能看其他纪元的文明细节） |
| `agent/state/epoch-answers.md` | 跨纪元答案录 |
| `agent/state/discoveries.md` | 当前纪元已知定律 |

农夫**看不到**：
- 其他纪元的 `civilizations/epoch-N/` 文明细节
- `agent/state/scores.json`（评分数字对农夫隐藏）
- 代码目录 `src/`

### 农场主 & 歌者（完全可见性）

可看 `agent/` 下所有内容，包括所有纪元所有文明的完整记录。

---

## 隔离实现方式

**不依赖文件系统权限**（复杂且脆弱），而是：

- Controller 在构建农夫启动包时，**只传入允许可见的文件内容**
- `briefing.md` 是经过过滤的摘要，不是原始文件路径的直接引用
- 农夫看不到目录结构，只看到 Controller 传给它的文本

```python
# Controller构建农夫的context（伪代码）
farmer_context = {
    "briefing": read("agent/history/current/briefing.md"),
    "epoch_progress": read("agent/history/current/epoch.md"),
    "epoch_answers": read("agent/state/epoch-answers.md"),
    "discoveries": read("agent/state/discoveries.md"),
    # 当前纪元文明摘要（只给摘要，不给全文）
    "recent_civilizations": summarize_current_epoch_civs(N=10),
}
# 歌者 和 农场主 可以获取完整context
```

---

## 智能体域与人类域的职责边界

| 操作 | 由谁做 | 写入哪里 |
|---|---|---|
| 更新 briefing.md | Controller（代码） | agent/history/current/ |
| 写 farmer.md | 农夫（Qwen API） | agent/civilizations/epoch-N/civ-N/ |
| 写 singer.md | 歌者（Qwen API） | agent/civilizations/epoch-N/civ-N/ |
| 写纪元史册 | 歌者（Qwen API） | agent/history/epochs/ |
| 写里程碑/报告 | 人类（农场主） | project/ |
| 修改提示词 | 人类（农场主） | src/prompts/ |
| 修改代码 | 人类（农场主） | src/ |
