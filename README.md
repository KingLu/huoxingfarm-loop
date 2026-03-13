# 🚀 火星农场 Loop — 三体实验

> 文明一次次重启，史书永久留存。  
> 下一个文明站在所有失败者的肩膀上，直到解出答案。

**核心问题：** 火星农场项目通过什么形式/模式运作，可以最大概率成功？

---

## 角色

| 角色 | 模型 | 职责 |
|---|---|---|
| 🌾 农场主 | 灵耳（Claude） | 发起任务，每10轮审阅，掌舵方向 |
| 👨‍🌾 农夫 | Qwen3.5:35b（GPU工作站） | 每轮生成策略迭代 |
| 🎵 歌者 | Qwen3.5:35b（GPU工作站） | 评分、记录史书、git commit |
| 🔍 情报员 | intel（Gemini） | 按需召唤，补充现实数据 |

## 三层结构

```
项目总史（MarsfarM）
  └── 纪元（Epoch）      ← 一个大命题，跑若干文明直到命题收敛
        └── 文明（Civilization）  ← 一次 Loop 迭代
```

**核心规则：每迭代一次 = 一个文明；每解决一个命题 = 纪元加一**

## 分支策略

```
main   ← 纪元正史（纪元终结时合并，含终章）
  └── live  ← 文明实录（歌者每轮 commit）
```

## Tag 规范

| Tag | 打在 | 时机 |
|---|---|---|
| `e{N}-civ-{NNN}` | live | 每个文明结束（自动） |
| `e{N}-best-{score}` | live | 当前纪元新高分（自动） |
| `epoch-{N}-start` | live | 新纪元开始（自动） |
| `epoch-{N}-end` | main | 纪元收敛后合并（自动） |
| `pivot-N` | main | 农场主调整方向（手动） |
| `convergence` | main | 史诗完结 |

## 目录结构

```
huoxingfarm-loop/
├── README.md
├── DESIGN.md               ← 完整设计方案
├── run.py                  ← Controller 主程序（待实现）
├── .env.example            ← 环境变量模板（不含真实密钥）
├── prompts/
│   ├── farmer.md           ← 农夫 prompt 模板
│   ├── singer.md           ← 歌者 prompt 模板
│   └── perspectives.json   ← 10个思维视角
├── state/
│   ├── epoch.json          ← 当前纪元（编号、命题、进度）
│   ├── epoch-answers.md    ← 所有已完成纪元最终答案（永久积累）
│   ├── current.json        ← 当前纪元最优方案
│   ├── discoveries.md      ← 当前纪元已知定律
│   └── scores.json         ← 当前纪元分数历史
└── logs/
    └── civilization-NNN.md ← 文明编号全局唯一，跨纪元连续
```

## 快速开始

```bash
# 1. 复制并填写环境变量
cp .env.example .env
# 编辑 .env，填入 GPU 工作站 API 地址和密钥

# 2. 运行 Loop
python3 run.py --rounds 20

# 3. 查看史书
git log --oneline live

# 4. 查看当前最优方案
cat state/current.json
```

## 收敛条件

- 总分 ≥ 85/100 → 自动收敛
- 连续5轮提升 < 2分 → 通知农场主决策
- 最多运行50轮

---

*项目发起：MarsfarM 火星农场*  
*设计哲学：仿《三体》游戏，文明迭代，史书传承*
