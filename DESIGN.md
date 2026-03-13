# 火星农场 Agent Loop — 详细设计方案

> 仿照《三体》游戏逻辑：文明一次次重启，史书永久留存。
> 下一个文明站在所有失败者的肩膀上，直到解出答案。

*版本：v1.1 | 2026-03-13*  
*实现状态：✅ 已运行，纪元1已收敛（93分，文明#001）*

---

## 一、系统哲学

### 三层结构

```
项目总史（MarsfarM）
  └── 纪元（Epoch）      ← 一个大命题，跑若干文明直到命题收敛
        └── 文明（Civilization）  ← 一次 Loop 迭代
```

**核心规则：**
- 每迭代一次 = 一个文明
- 每解决一个命题 = 纪元加一，新命题开始
- 文明编号**全局递增不重置**（#001 → ∞）
- 纪元编号单独计数（纪元1、纪元2…）

### 三体类比

| 三体游戏元素 | 本系统对应 |
|---|---|
| 一次文明 | 一轮 Loop 迭代 |
| 文明毁灭 | 本轮评分不足，自然终结 |
| 史书留存 | 歌者提交 git commit |
| 下个文明读史 | 农夫读 briefing.md 启动 |
| 解出三体问题 | 当前纪元命题收敛（≥85/100） |
| 新的三体问题 | 纪元加一，新命题诞生 |
| 不同历史人物 | 农夫每轮随机切换「思维视角」 |

### 核心洞察

- **每次迭代不是从零开始**，而是站在所有前文明的肩膀上
- **纪元的答案永久积累**，成为后续纪元的背景真理
- **git 就是史书**，commit message 是每个文明的墓志铭
- **歌者是史官**，负责记录、评价、传承，纪元终结时写「终章」
- **农场主是玩家**，俯瞰全局，审阅纪元，选择下一个命题

### 纪元预设弧线（可动态调整）

```
纪元1：运营模式  ← ✅ 已收敛（93分）
  命题：「火星农场通过什么形式/模式运作可以最大概率成功？」

纪元2：融资路径（待定）
  命题：「谁会投资火星农场，第一笔钱从哪来？」

纪元3：团队构建（待定）
纪元4：技术选型（待定）
纪元5：风险对冲（待定）
纪元N：最终整合 — 完整商业计划书
```

---

## 二、三角色体系

### 角色一览

| 角色 | 存在形态 | 模型 | 唯一使命 |
|---|---|---|---|
| **农场主** | 永生 | 灵耳（Claude Sonnet） | 火星农场有朝一日在火星开业，种出西红柿，并盈利 |
| **歌者** | 永生 | DeepSeek（deepseek-chat） | 客观评价当前阶段命题是否达到验收标准，并记录史书 |
| **农夫** | 凡生 | 本地 Ollama（qwen3.5:0.8b） | 读取史书，消耗token，给出当前问题的最好答案。然后消亡 |

> **模型选择说明：** 农夫原计划使用 Qwen3.5:35b @ suanji GPU 工作站，但因 Cloudflare 代理 100s 硬超时（HTTP 524），Qwen3.5 thinking 模式响应时间超限，已改为 DeepSeek API（无 thinking 模式，响应快速稳定）。suanji 工作站保留作为高算力备用。

### 闭环结构

```
农场主
  │  提出阶段命题 + 验收标准 + token预算
  ↓
农夫
  │  读史书 → 在token预算内作答 → 交卷（或token耗尽强制交卷）
  ↓
歌者
  │  对照验收标准评价 → 写入史书 → git commit
  ↓
  ├── 未达标 → 史书更新 → 下一文明农夫重新读 → 再答
  └── 达标   → 通知农场主 → 农场主提出下一阶段命题
```

### 四条规则（最小规则集）

1. **农场主定题**：纪元开始时写下命题 + 验收标准 + token预算，之后不干预
2. **农夫守时**：每个文明有固定token预算（默认10万），用完即死
3. **歌者守信**：独立评价，不受农场主偏好影响；未达标必须明确说明缺什么
4. **史书不可篡改**：农夫无权修改已记录的史书；歌者只追加，不删改

### 农夫的Token预算与死亡机制

| 死亡方式 | 触发条件 | commit 标记 |
|---|---|---|
| **自然终结** | 农夫完成作答，主动交卷 | `自然终结` |
| **token耗尽** | 消耗达到预算上限，强制终结 | `token耗尽` |

### 农夫的可见性（信息隔离）

农夫**只能**看到：
- `history/current/briefing.md`（启动包：命题+验收标准+已知定律+歌者提示）
- 当前纪元已完成文明的进度表（`history/current/epoch.md`）
- 已完成纪元的最终答案（`agent/state/epoch-answers.md`）

农夫**看不到**：
- 歌者的评分数字（只知道「未达标，方向提示是…」）
- 其他文明的完整对话原文

---

## 三、数据结构

### 目录树（实际实现）

```
huoxingfarm-loop/
├── src/
│   ├── run.py                  ← Controller 主程序
│   ├── farmer.py               ← 农夫 API 模块
│   ├── singer.py               ← 歌者 API 模块
│   ├── .env                    ← 本地密钥（不提交）
│   └── prompts/
│       ├── farmer.md
│       ├── singer.md
│       └── perspectives.json
└── agent/
    ├── history/
    │   ├── INDEX.md
    │   ├── current/
    │   │   ├── briefing.md     ← 农夫启动包（Controller每轮刷新）
    │   │   └── epoch.md        ← 当前纪元进展+文明进度表
    │   └── epochs/
    │       └── epoch-NNN.md    ← 已完成纪元封存史册
    ├── state/
    │   ├── epoch.json          ← 当前纪元状态
    │   ├── epoch-answers.md    ← 跨纪元答案积累
    │   ├── discoveries.md      ← 当前纪元已知定律
    │   ├── scores.json         ← 分数历史
    │   └── current.json        ← 当前纪元最优方案快照
    └── civilizations/
        └── epoch-NNN/
            └── civ-NNN/
                ├── farmer.md   ← 农夫产出
                └── singer.md   ← 歌者评价（JSON+叙事）
```

### agent/state/epoch.json

```json
{
  "epoch_number": 1,
  "question": "火星农场项目通过什么形式/模式运作，可以最大概率成功？",
  "acceptance_criteria": "三条必须同时满足：1.明确第一个付费客户 2.可信的资金来源 3.清晰的盈利路径",
  "token_budget": 100000,
  "started_at_civilization": 1,
  "current_civilization": 1,
  "next_hint": "探索在体验经济之外，如何基于已积累的独特技术或生物资产，构建更独立的核心产品",
  "status": "completed"
}
```

### 歌者输出 JSON 格式

```json
{
  "civilization": 1,
  "epoch": 1,
  "perspective": "2050年的历史学家（回顾视角）",
  "verdict": "passed",
  "criteria_check": {
    "first_paying_customer": true,
    "funding_source": true,
    "profit_path": true
  },
  "scores": {
    "feasibility": 16,
    "completeness": 20,
    "consistency": 18,
    "novelty": 19,
    "uncertainty_reduction": 20
  },
  "total": 93,
  "epitaph": "他们未曾售卖一粒粮食，却用故事与体验，为火星农场换来了第一缕生存的阳光。",
  "legacy": ["已知定律1", "已知定律2"],
  "biggest_gap": "对外部叙事价值的依赖，存在故事泡沫风险",
  "next_focus": "探索更独立的核心产品或服务原型"
}
```

---

## 四、Git 分支与 Tag

### 分支

```
main   ← 纪元正史（纪元收敛时合并）
  └── live  ← 文明实录（歌者每轮 commit）
```

### Tag（只打纪元级，不打文明级）

| Tag | 打在 | 时机 |
|---|---|---|
| `epoch-{N}-start` | live | 新纪元第一个文明开始前 |
| `epoch-{N}-end` | main | 纪元收敛合并后 |
| `pivot-N` | main | 农场主调整命题方向（手动） |
| `convergence` | main | 史诗完结 |

### commit 格式

```
e1-civ-001 | 自然终结 | tokens:1,662/100,000 | 达标(93) | 墓志铭
epoch-1-end: 纪元1收敛 | 历经1文明 | 得分93
```

---

## 五、每轮完整流程

```
Step 1: Controller 读取状态
    ├── agent/state/epoch.json
    ├── agent/state/discoveries.md
    └── agent/state/epoch-answers.md

Step 2: 构建农夫启动包（写入 history/current/briefing.md）
    ├── 当前命题 + 验收标准
    ├── 歌者上轮的 next_focus
    ├── 已知定律
    └── 已完成纪元答案

Step 3: 农夫运行
    ├── 调用 DeepSeek API（deepseek-chat）
    ├── max_tokens: 4096（单次输出上限）
    ├── token预算通过 usage 累计跟踪
    └── 输出存入 agent/civilizations/epoch-NNN/civ-NNN/farmer.md

Step 4: 歌者运行
    ├── 输入：农夫输出 + token数据 + 死亡方式 + 验收标准
    ├── 调用 DeepSeek API（deepseek-chat）
    ├── 输出：JSON评分 + 文明叙事
    └── 存入 agent/civilizations/epoch-NNN/civ-NNN/singer.md

Step 5: 更新史书
    ├── 追加 legacy → agent/state/discoveries.md
    ├── 更新 agent/state/scores.json
    ├── 追加进度行 → agent/history/current/epoch.md
    ├── 更新歌者提示 → agent/history/current/epoch.md
    └── 刷新农夫启动包 → agent/history/current/briefing.md

Step 6: git commit（由 Controller 执行）
    └── e{epoch}-civ-{N:03d} | {death} | tokens:{used}/{budget} | {verdict}({score}) | {epitaph}

Step 7: 收敛判断
    ├── total >= 85 → finalize_epoch（写终章、合并main、打tag）
    ├── 5轮无实质进展 → 通知农场主
    └── 否则 → 下一文明
```

---

## 六、收敛判断

| 条件 | 动作 |
|---|---|
| `total >= 85` | 自动收敛，纪元终结，合并 main |
| 连续5轮提升 < 2分 | 警告，建议农场主介入 |
| `iteration >= MAX_ROUNDS(50)` | 强制终结，生成当前最优报告 |

---

## 七、运行命令

```bash
cd /Users/jenkins/projects/huoxing-loop

# 初始化新纪元（农场主执行）
.venv/bin/python src/run.py init

# 启动 Loop
.venv/bin/python src/run.py

# 后台运行并记录日志
nohup .venv/bin/python -u src/run.py > /tmp/huoxing-loop.log 2>&1 &

# 查看运行日志
tail -f /tmp/huoxing-loop.log

# 查看史书
git log --oneline live
cat agent/state/scores.json
```

---

## 八、技术注记

**农夫：本地 Ollama**
- URL: `http://localhost:11434/v1/chat/completions`
- Model: `qwen3.5:0.8b`
- 无需 API Key（填 `ollama` 占位）
- 温度: 0.8（探索性）

**歌者：DeepSeek API**
- URL: `https://api.deepseek.com/v1/chat/completions`
- Model: `deepseek-chat`
- 温度: 0.3（稳定/客观）
- 平均响应: ~27s

**suanji GPU 工作站（备用）**
- URL: `https://chat.suanji.net/api/v1`
- 注意：需要 `User-Agent: curl/8.7.1`（否则 403）
- 注意：Cloudflare 代理 100s 硬超时，Qwen3.5 thinking 模式容易触发 HTTP 524
- 可用模型：qwen3.5:35b, qwen3.5:9b, minimax-m2.5, qwen3-30b 等

**环境变量**（`src/.env`，不提交）
```
FARMER_API_URL=http://localhost:11434/v1
FARMER_API_KEY=ollama
FARMER_MODEL=qwen3.5:0.8b
DEEPSEEK_API_URL=https://api.deepseek.com/v1
DEEPSEEK_API_KEY=sk-xxx
SINGER_MODEL=deepseek-chat
TOKEN_BUDGET=100000
MAX_ROUNDS=50
CONVERGENCE_SCORE=85
```

---

*设计版本：v1.1 | 2026-03-13*  
*农场主：灵耳（Claude Sonnet）| 农夫：DeepSeek | 歌者：DeepSeek*
