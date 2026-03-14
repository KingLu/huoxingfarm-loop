# 🚀 火星农场 Loop — 三体实验

> 文明一次次重启，史书永久留存。  
> 下一个文明站在所有失败者的肩膀上，直到解出答案。

## ⚠️ 项目根本使命（不可偏离）

**火星农场有朝一日在火星开业，种出西红柿，并盈利。**

所有纪元命题都是为这个使命服务的分解步骤。农夫的方案、歌者的评价、农场主的命题——一切都必须守住这条红线。

---

## 角色

| 角色 | 模型 | 存在形态 | 职责 |
|---|---|---|---|
| 🌾 农场主 | 灵耳（Claude Sonnet） | 永生 | 发起纪元命题，审阅收敛结果，守住使命方向 |
| 👨‍🌾 农夫 | 本地 Ollama（qwen3.5:2b） | 凡生 | 每轮读史书、生成战略方案，token耗尽即消亡 |
| 🎵 歌者 | DeepSeek（deepseek-chat） | 永生 | 独立评分（含使命一致性）、提炼遗产、记录史书 |

## 三层结构

```
项目总史（MarsfarM）
  └── 纪元（Epoch）      ← 一个大命题，跑若干文明直到收敛
        └── 文明（Civilization）  ← 一次 Loop 迭代
```

**核心规则：每迭代一次 = 一个文明；每解决一个命题 = 纪元加一**

## 分支策略

```
main   ← 纪元正史（纪元终结时合并，含终章）
  └── live  ← 文明实录（歌者每轮 commit）
```

## Tag 规范（只打纪元级，不打文明级）

| Tag | 打在 | 时机 |
|---|---|---|
| `epoch-{N}-start` | live | 新纪元第一个文明开始前（自动） |
| `epoch-{N}-end` | main | 纪元收敛合并后（自动） |
| `pivot-N` | main | 农场主调整命题方向（手动） |
| `convergence` | main | 史诗完结（手动） |

文明记录在 git commit message 和 `agent/civilizations/` 目录中，不占用 tag。

## 目录结构

```
huoxingfarm-loop/
├── README.md
├── DESIGN.md                       ← 完整设计方案
├── .env.example                    ← 环境变量模板（不含真实密钥）
├── src/
│   ├── run.py                      ← Controller 主程序
│   ├── farmer.py                   ← 农夫 API 调用模块
│   ├── singer.py                   ← 歌者 API 调用模块
│   ├── .env                        ← 本地密钥（不提交）
│   └── prompts/
│       ├── farmer.md               ← 农夫 prompt 模板
│       ├── singer.md               ← 歌者 prompt 模板
│       └── perspectives.json       ← 10个思维视角
└── agent/
    ├── history/
    │   ├── INDEX.md                ← 史书总目
    │   ├── current/
    │   │   ├── briefing.md         ← 农夫启动包（每轮刷新）
    │   │   └── epoch.md            ← 当前纪元进展表
    │   └── epochs/
    │       └── epoch-NNN.md        ← 已完成纪元的封存史册
    ├── state/
    │   ├── epoch.json              ← 当前纪元（编号、命题、状态）
    │   ├── epoch-answers.md        ← 所有已完成纪元答案（永久积累）
    │   ├── discoveries.md          ← 当前纪元已知定律
    │   ├── scores.json             ← 分数历史与最优记录
    │   └── current.json            ← 当前纪元最优方案快照
    └── civilizations/
        └── epoch-NNN/
            └── civ-NNN/
                ├── farmer.md       ← 农夫产出
                └── singer.md       ← 歌者评价（含JSON评分+文明叙事）
```

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/KingLu/huoxingfarm-loop.git
cd huoxingfarm-loop

# 2. 创建 Python 3.12 虚拟环境
python3.12 -m venv .venv
.venv/bin/pip install python-dotenv

# 3. 配置密钥
cp src/.env.example src/.env
# 编辑 src/.env，填入 DeepSeek API Key

# 4. 初始化纪元1
.venv/bin/python src/run.py init

# 5. 启动 Loop
.venv/bin/python src/run.py

# 6. 查看史书
git log --oneline live
cat agent/state/scores.json
```

## git commit 格式

```
e1-civ-001 | 自然终结 | tokens:1,662/100,000 | 达标(93) | 墓志铭文字
e1-civ-007 | token耗尽 | tokens:100,000/100,000 | 未达标(61) | 墓志铭文字
epoch-1-end: 纪元1收敛 | 历经1文明 | 得分93
```

## 收敛条件

- 总分 ≥ 85/100 → 自动收敛，纪元终结
- 连续5轮提升 < 2分 → 通知农场主决策
- 最多运行50轮（MAX_ROUNDS）

---

*项目发起：MarsfarM 火星农场*  
*设计哲学：仿《三体》游戏，文明迭代，史书传承*  
*版本：v1.0 | 2026-03-13 | 纪元1已收敛（93分）*
