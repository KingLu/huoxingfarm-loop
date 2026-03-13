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

## 分支策略

```
main   ← 正史（农场主每10轮审阅后合并）
  └── live  ← 实录（歌者每轮 commit）
```

## Tag 规范

| Tag | 含义 |
|---|---|
| `civ-NNN` | 第N个文明（自动，打在 live） |
| `best-{score}` | 历史最高分（自动，打在 live） |
| `era-N-end` | 第N纪结束，农场主审阅（打在 main） |
| `pivot-N` | 方向调整节点（农场主手动） |
| `convergence` | 最终收敛（分数≥85） |

## 目录结构

```
huoxingfarm-loop/
├── README.md
├── DESIGN.md           ← 完整设计方案
├── run.py              ← Controller 主程序（待实现）
├── .env.example        ← 环境变量模板（不含真实密钥）
├── prompts/
│   ├── farmer.md       ← 农夫 prompt 模板
│   ├── singer.md       ← 歌者 prompt 模板
│   └── perspectives.json ← 10个思维视角
├── state/
│   ├── current.json    ← 当前最优方案
│   ├── discoveries.md  ← 跨文明积累的已知定律
│   └── scores.json     ← 分数历史
└── logs/
    └── civilization-NNN.md  ← 每个文明的完整记录
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
