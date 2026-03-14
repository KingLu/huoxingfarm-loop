#!/usr/bin/env python3
"""
火星农场 Agent Loop — Controller 主程序
三角色：农场主（灵耳）| 农夫（qwen3.5:35b）| 歌者（deepseek-chat）
"""

import os
import json
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(Path(__file__).parent / ".env")

# 把 src/ 加入路径
sys.path.insert(0, str(Path(__file__).parent))
from farmer import build_context, call_farmer
from singer import build_singer_input, call_singer

# ─── 路径 ────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent
AGENT_DIR = ROOT / "agent"
HISTORY   = AGENT_DIR / "history"
CIV_DIR   = AGENT_DIR / "civilizations"
STATE_DIR = AGENT_DIR / "state"

TOKEN_BUDGET       = int(os.getenv("TOKEN_BUDGET", "100000"))
MAX_ROUNDS         = int(os.getenv("MAX_ROUNDS", "50"))
CONVERGENCE_SCORE  = int(os.getenv("CONVERGENCE_SCORE", "85"))
FARMER_MODEL       = os.getenv("FARMER_MODEL", "qwen3.5:0.8b")
FARMER_THINK       = os.getenv("FARMER_THINK", "false").lower() in ("true", "1", "yes")
SINGER_MODEL_NAME  = os.getenv("SINGER_MODEL", "deepseek-chat")


# ─── 工具函数 ────────────────────────────────────────────

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""

def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def git(cmd: str, cwd=ROOT):
    result = subprocess.run(
        f"git {cmd}", shell=True, cwd=cwd,
        capture_output=True, text=True
    )
    return result.stdout.strip()

VERBOSE = os.getenv("VERBOSE", "true").lower() in ("true", "1", "yes")

def log(msg: str, level: str = "info"):
    """
    level: info | detail | section
    detail 只在 VERBOSE=true 时打印
    section 打印分隔线
    """
    ts = datetime.now().strftime("%H:%M:%S")
    if level == "section":
        print(f"\n[{ts}] {'─' * 50}")
        print(f"[{ts}] {msg}")
        print(f"[{ts}] {'─' * 50}")
    elif level == "detail":
        if VERBOSE:
            print(f"[{ts}]   ↳ {msg}")
    else:
        print(f"[{ts}] {msg}")


# ─── 状态管理 ────────────────────────────────────────────

def load_epoch() -> dict:
    data = load_json(STATE_DIR / "epoch.json")
    if not data:
        raise RuntimeError("state/epoch.json 不存在，请先初始化纪元（运行 init_epoch）")
    return data

def load_scores() -> list:
    data = load_json(STATE_DIR / "scores.json")
    return data.get("scores", [])

def save_scores(scores: list, best: dict):
    save_json(STATE_DIR / "scores.json", {"scores": scores, "best": best})

def get_last_score(scores: list) -> int:
    return scores[-1]["total"] if scores else 0

def get_best_score(scores: list) -> int:
    return max((s["total"] for s in scores), default=0)

def load_perspectives() -> list:
    data = json.loads((ROOT / "src" / "prompts" / "perspectives.json").read_text())
    return data if isinstance(data, list) else data.get("perspectives", [])


# ─── 史书更新 ────────────────────────────────────────────

def update_epoch_progress(civ_num: int, epoch_num: int, tokens_used: int,
                           token_budget: int, death: str,
                           verdict: str, score: int, epitaph: str,
                           next_hint: str = "",
                           farmer_model: str = "",
                           elapsed_sec: float = 0):
    """追加一行到 history/current/epoch.md 的文明进度表，并更新歌者提示"""
    path = HISTORY / "current" / "epoch.md"
    content = read(path)

    # ── ① 追加文明进度行（含模型、时长）──
    death_symbol = "🔋" if death == "token_exhausted" else "✅"
    verdict_symbol = "✅达标" if verdict == "passed" else "❌未达标"

    # 人类可读时长
    if elapsed_sec < 60:
        elapsed_human = f"{int(elapsed_sec)}秒"
    elif elapsed_sec < 3600:
        m, s = divmod(int(elapsed_sec), 60)
        elapsed_human = f"{m}分{s}秒"
    else:
        elapsed_human = f"{int(elapsed_sec//3600)}小时{int((elapsed_sec%3600)//60)}分"

    row = (f"| 文明#{civ_num:03d} | {farmer_model or '?'} | {elapsed_human} "
           f"| {tokens_used:,}/{token_budget:,} "
           f"| {death_symbol}{death} | {verdict_symbol}({score}) | {epitaph} |\n")
    if "_等待第一个文明_" in content:
        # 7列表格（模型|时长|token|死亡|达标|墓志铭）
        content = content.replace("| _等待第一个文明_ | | | | | | |\n", row)
    else:
        lines = content.splitlines(keepends=True)
        insert_at = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].startswith("|"):
                insert_at = i + 1
                break
        lines.insert(insert_at, row)
        content = "".join(lines)

    # ── ③ 更新"歌者的上一条提示"段落（fix: 之前写死了初始文字）──
    if next_hint:
        import re
        content = re.sub(
            r"(## 歌者的上一条提示\n\n_（.*?）_\n\n>).*?(\n\n)",
            rf"\1 {next_hint}\2",
            content,
            flags=re.DOTALL,
        )
        # 如果是第一次（还是旧的初始文字格式）
        content = re.sub(
            r"(## 歌者的上一条提示\n\n_（.*?）_\n\n>)[^\n]+",
            rf"\1 {next_hint}",
            content,
        )

    write(path, content)


def update_briefing(epoch: dict, next_hint: str, discoveries: str,
                    epoch_answers: str, civ_num: int):
    """刷新 history/current/briefing.md，供下一个文明读取"""
    perspective_placeholder = "{perspective}"  # Controller 启动时替换

    # 读取失败教训
    failure_lessons = read(STATE_DIR / "failure-lessons.md")
    # 只取条目部分（去掉文件头说明）
    lessons_section = ""
    if "## 纪元" in failure_lessons:
        lessons_section = failure_lessons[failure_lessons.index("## 纪元"):]

    content = f"""# 农夫启动包 — 文明 #{civ_num:03d}

> 此文件由 Controller 在每个文明开始前自动生成。农夫只需读这一个文件。

---

## ⚠️ 项目根本使命（不可违背）

**火星农场有朝一日在火星开业，种出西红柿，并盈利。**

这是所有纪元命题的终极锚点。无论本纪元命题如何具体，你的方案**必须服务于这个根本使命**：
- 你提出的任何商业模式，最终都要落实到**在火星土壤上真正种菜**
- 你的第一个付费客户，必须是为**火星农业本身**而付钱，而不是为数据、概念、卫星服务等衍生物
- 纯数据服务、纯金融方案、纯地球农业方案——**不符合使命，歌者将扣分**

---

## 你的文明使命

读取史书，消耗 token，给出当前命题的最好答案。然后消亡。

**你的 token 预算：{TOKEN_BUDGET:,}**（超出则强制终结）

---

## 当前命题（纪元 {epoch['epoch_number']}）

> {epoch['question']}

**验收标准（歌者将对照此标准评价）：**

{epoch['acceptance_criteria']}

---

## 已知定律（前文明用生命换来的真理）

{discoveries or "暂无。你是本纪元第一个文明，请自由探索。"}

---

## 歌者给你的方向提示

{next_hint or "第一个文明尚未开始。你是开天辟地者，没有前人提示。"}

---

## 已确认纪元答案（农场主认可，可继承方向）

{epoch_answers or "暂无。这是第一个纪元。"}

---

## ⛔ 失败教训（农场主否决案例，禁止效仿）

{lessons_section or "暂无失败教训。"}

---

## 你的本文明视角

**{perspective_placeholder}**

---

## 输出格式

```markdown
## 第{civ_num}文明战略方案
**视角：** {perspective_placeholder}

### 核心模式
（一句话概括——必须说明如何在火星实际种植农作物）

### 为什么这种模式能成功
（3-5个论点，有具体支撑）

### 火星种植实现路径
（第一批作物何时、在哪、如何种下？用什么技术克服低重力/辐射/大气等挑战？）

### 第一个付费客户
（具体是谁，为火星农业本身付钱，愿意付多少，为什么）

### 资金来源
（谁出钱，为什么，大概规模）

### 10年后的盈利路径
（如何独立可持续盈利）

### 最大风险及应对
（1-3个 + 缓解方案）

### 对已知定律的继承与修正
（吸收了什么，推翻了什么，理由）
```
"""
    write(HISTORY / "current" / "briefing.md", content)


def append_discoveries(legacy: list, civ_num: int):
    """将本文明的遗产追加到 state/discoveries.md"""
    path = STATE_DIR / "discoveries.md"
    content = read(path)
    new_entries = "\n".join(f"- [文明#{civ_num:03d}] {item}" for item in legacy)
    content += f"\n\n### 文明#{civ_num:03d} 贡献\n{new_entries}\n"
    write(path, content)


# ─── Git 操作 ────────────────────────────────────────────

def git_commit_civilization(civ_num: int, epoch_num: int, death: str,
                             tokens_used: int, token_budget: int,
                             verdict: str, score: int, epitaph: str,
                             farmer_model: str = "", elapsed_sec: float = 0):
    git("add -A")
    death_label = "token耗尽" if death == "token_exhausted" else "自然终结"
    verdict_label = f"{'达标' if verdict == 'passed' else '未达标'}({score})"
    if elapsed_sec < 60:
        elapsed_human = f"{int(elapsed_sec)}s"
    else:
        elapsed_human = f"{int(elapsed_sec//60)}m{int(elapsed_sec%60)}s"
    model_short = farmer_model.split("/")[-1] if farmer_model else "?"
    msg = (f"e{epoch_num}-civ-{civ_num:03d} | {death_label} | "
           f"{elapsed_human} | {model_short} | "
           f"tokens:{tokens_used:,}/{token_budget:,} | "
           f"{verdict_label} | {epitaph}")
    git(f'commit -m "{msg}"')
    log(f"📜 git commit: {msg}")


def git_tag_epoch_start(epoch_num: int):
    tag = f"epoch-{epoch_num}-start"
    git(f"tag {tag}")
    git(f"push origin live --tags")
    log(f"🏷  tag: {tag}")


def git_tag_epoch_end(epoch_num: int):
    """纪元达标：合并到 main，打 tag"""
    git("checkout main")
    git(f'merge live --no-ff -m "epoch-{epoch_num}-end: 纪元{epoch_num}收敛"')
    git(f"tag epoch-{epoch_num}-end")
    git("checkout live")
    git("push origin main live --tags")
    log(f"🏷  epoch-{epoch_num}-end 已合并到 main")


# ─── 单文明完整流程 ───────────────────────────────────────

def run_civilization(civ_num: int, epoch: dict,
                     perspective: str, scores: list) -> dict:
    """
    运行一个完整文明。返回评价结果 dict。
    """
    epoch_num = epoch["epoch_number"]
    civ_dir = CIV_DIR / f"epoch-{epoch_num:03d}" / f"civ-{civ_num:03d}"
    civ_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: 读取史书 ──
    briefing     = read(HISTORY / "current" / "briefing.md")
    discoveries  = read(STATE_DIR / "discoveries.md")
    epoch_answers = read(STATE_DIR / "epoch-answers.md")
    next_hint    = epoch.get("next_hint", "")
    last_score   = get_last_score(scores)

    # 把 perspective 替换进 briefing
    briefing = briefing.replace("{perspective}", perspective)

    # ── Step 2: 构建农夫 context ──
    context = build_context(
        epoch_num=epoch_num,
        civ_num=civ_num,
        perspective=perspective,
        briefing=briefing,
        discoveries=discoveries,
        next_hint=next_hint,
        epoch_answers=epoch_answers,
    )

    # ── Step 3: 农夫运行 ──
    log(f"🌱 文明#{civ_num:03d} 诞生 | 纪元{epoch_num} | 视角：{perspective}")
    log(f"农夫配置 → 模型:{FARMER_MODEL} | think:{FARMER_THINK} | token预算:{TOKEN_BUDGET:,}", "detail")
    log(f"史书长度 → briefing:{len(briefing)}字符 | 已知定律:{len(discoveries)}字符", "detail")

    t_farmer_start = datetime.now()
    farmer_result = call_farmer(context, civ_num, epoch_num)
    t_farmer_end = datetime.now()

    elapsed_human = farmer_result['elapsed_sec']
    log(f"💀 文明#{civ_num:03d} 消亡 | {farmer_result['death']} | "
        f"tokens:{farmer_result['tokens_used']:,} | 耗时:{elapsed_human}s")
    log(f"农夫产出长度：{len(farmer_result['content'])} 字符", "detail")

    # 农夫史书（含模型信息区块）
    farmer_meta = (
        f"# 文明#{civ_num:03d} — 农夫产出\n\n"
        f"## 运行元数据\n\n"
        f"| 字段 | 值 |\n"
        f"|---|---|\n"
        f"| 模型 | `{FARMER_MODEL}` |\n"
        f"| Think模式 | `{FARMER_THINK}` |\n"
        f"| 视角 | {perspective} |\n"
        f"| 死亡方式 | {farmer_result['death']} |\n"
        f"| Token消耗 | {farmer_result['tokens_used']:,} / {TOKEN_BUDGET:,} |\n"
        f"| 运行时长 | {elapsed_human}s |\n"
        f"| 开始时间 | {t_farmer_start.strftime('%H:%M:%S')} |\n"
        f"| 结束时间 | {t_farmer_end.strftime('%H:%M:%S')} |\n\n"
        f"---\n\n"
        f"## 农夫输出\n\n"
        f"{farmer_result['content']}"
    )
    write(civ_dir / "farmer.md", farmer_meta)

    # ── Step 4: 歌者评价 ──
    log(f"🎵 歌者开始评价文明#{civ_num:03d}...")
    log(f"歌者配置 → 模型:{SINGER_MODEL_NAME}", "detail")
    singer_input = build_singer_input(
        civ_num=civ_num,
        epoch_num=epoch_num,
        perspective=perspective,
        farmer_output=farmer_result["content"],
        tokens_used=farmer_result["tokens_used"],
        token_budget=TOKEN_BUDGET,
        death=farmer_result["death"],
        acceptance_criteria=epoch.get("acceptance_criteria", ""),
        last_score=last_score,
        farmer_model=FARMER_MODEL,
        farmer_elapsed_sec=farmer_result["elapsed_sec"],
    )
    t_singer_start = datetime.now()
    singer_result = call_singer(singer_input)
    t_singer_end = datetime.now()

    evaluation = singer_result["evaluation"]
    total = evaluation.get("total", 0)
    log(f"🎵 歌者评价完成 | 得分:{total}/100 | 耗时:{singer_result['elapsed_sec']}s")
    sc = evaluation.get('scores', {})
    log(f"评分明细 → 使命:{sc.get('mission_alignment','?')} "
        f"可行性:{sc.get('feasibility','?')} "
        f"完整性:{sc.get('completeness','?')} "
        f"一致性:{sc.get('consistency','?')} "
        f"新颖性:{sc.get('novelty','?')} "
        f"不确定性:{sc.get('uncertainty_reduction','?')}", "detail")
    log(f"使命检查 → {evaluation.get('mission_check','?')} | {evaluation.get('mission_note','')}", "detail")

    # 歌者史书（含模型信息区块）
    singer_meta = (
        f"# 文明#{civ_num:03d} — 歌者评价\n\n"
        f"## 运行元数据\n\n"
        f"| 字段 | 值 |\n"
        f"|---|---|\n"
        f"| 歌者模型 | `{SINGER_MODEL_NAME}` |\n"
        f"| 农夫模型 | `{FARMER_MODEL}` |\n"
        f"| 农夫Think模式 | `{FARMER_THINK}` |\n"
        f"| 评价耗时 | {singer_result['elapsed_sec']}s |\n"
        f"| 开始时间 | {t_singer_start.strftime('%H:%M:%S')} |\n"
        f"| 结束时间 | {t_singer_end.strftime('%H:%M:%S')} |\n\n"
        f"---\n\n"
        f"## 歌者评价\n\n"
        f"{singer_result['raw']}"
    )
    write(civ_dir / "singer.md", singer_meta)

    # ── Step 5: 更新状态 ──
    epitaph = evaluation.get("epitaph", "")
    legacy  = evaluation.get("legacy", [])
    verdict = "passed" if evaluation.get("verdict") == "passed" else "not_passed"

    # 根据验收标准判断是否达标（歌者可能在 JSON 里给 verdict，也可能靠分数判断）
    if "verdict" not in evaluation:
        verdict = "passed" if total >= CONVERGENCE_SCORE else "not_passed"

    scores.append({
        "n":            civ_num,
        "epoch":        epoch_num,
        "total":        total,
        "delta":        total - last_score,
        "perspective":  perspective,
        "farmer_model": FARMER_MODEL,
        "elapsed_sec":  farmer_result["elapsed_sec"],
        "death":        farmer_result["death"],
        "tokens_used":  farmer_result["tokens_used"],
        "verdict":      verdict,
    })
    best = max(scores, key=lambda s: s["total"])
    save_scores(scores, best)

    if legacy:
        append_discoveries(legacy, civ_num)

    # ── Step 6: 更新史书 ──
    next_hint_new = evaluation.get("next_focus", "")   # 先取值再用

    update_epoch_progress(
        civ_num, epoch_num,
        farmer_result["tokens_used"], TOKEN_BUDGET,
        farmer_result["death"], verdict, total, epitaph,
        next_hint=next_hint_new,
        farmer_model=FARMER_MODEL,
        elapsed_sec=farmer_result["elapsed_sec"],
    )
    update_briefing(epoch, next_hint_new,
                    read(STATE_DIR / "discoveries.md"),
                    read(STATE_DIR / "epoch-answers.md"),
                    civ_num + 1)

    # 更新 epoch.json 的 next_hint
    epoch["next_hint"] = next_hint_new
    epoch["current_civilization"] = civ_num
    save_json(STATE_DIR / "epoch.json", epoch)

    # ── Step 7: git commit ──
    git_commit_civilization(
        civ_num, epoch_num,
        farmer_result["death"], farmer_result["tokens_used"], TOKEN_BUDGET,
        verdict, total, epitaph,
        farmer_model=FARMER_MODEL,
        elapsed_sec=farmer_result["elapsed_sec"],
    )
    git("push origin live")

    return {
        "civ_num":  civ_num,
        "total":    total,
        "verdict":  verdict,
        "epitaph":  epitaph,
        "next_hint": next_hint_new,
    }


# ─── 纪元收敛处理 ────────────────────────────────────────

def finalize_epoch(epoch: dict, scores: list, winning_civ: int):
    """纪元达标：写终章，更新 epoch-answers.md，打 tag"""
    epoch_num = epoch["epoch_number"]
    best = max(scores, key=lambda s: s["total"])
    civ_count = len(scores)

    log(f"🎉 纪元{epoch_num}收敛！历经{civ_count}个文明，最终得分{best['total']}")

    # 写纪元史册
    epoch_file = HISTORY / "epochs" / f"epoch-{epoch_num:03d}.md"
    epoch_content = f"""# 纪元{epoch_num} 史册（已封存）

**命题：** {epoch['question']}

**开始文明：** #{(epoch['started_at_civilization'] or 1):03d}
**终结文明：** #{winning_civ:03d}
**历经文明数：** {civ_count}
**最终得分：** {best['total']}/100

---

## 终章

（由歌者在收敛时撰写）

本纪元历经 {civ_count} 个文明的探索，最终在第 {winning_civ} 文明达到验收标准。
得分 {best['total']}/100，视角：{best['perspective']}。

---

## 文明进度表

（详见 agent/civilizations/epoch-{epoch_num:03d}/）

---

## 最终答案摘要

（见 state/epoch-answers.md）
"""
    write(epoch_file, epoch_content)

    # 追加到 epoch-answers.md
    answers_path = STATE_DIR / "epoch-answers.md"
    answers = read(answers_path)
    answers += f"""
## 纪元{epoch_num}：{epoch['question'][:30]}...（终结于文明#{winning_civ:03d}，得分{best['total']}）
**命题：** {epoch['question']}
**答案摘要：** 见 agent/history/epochs/epoch-{epoch_num:03d}.md

"""
    write(answers_path, answers)

    # 更新 history/INDEX.md —— 删除所有本纪元旧行，追加已完成行
    index_path = HISTORY / "INDEX.md"
    lines = read(index_path).splitlines(keepends=True)
    # 过滤掉所有含 "纪元{epoch_num}" 的表格行（可能有多行：进行中 + 已完成）
    cleaned = [l for l in lines if f"| 纪元{epoch_num} |" not in l]
    # 在最后一个表格行后插入已完成行
    q_short = epoch['question'][:20]
    new_row = f"| 纪元{epoch_num} | {q_short}... | ✅ 已完成 | {civ_count} | 得分{best['total']} |\n"
    insert_at = len(cleaned)
    for i in range(len(cleaned) - 1, -1, -1):
        if cleaned[i].startswith("|"):
            insert_at = i + 1
            break
    cleaned.insert(insert_at, new_row)
    write(index_path, "".join(cleaned))

    # ② 更新 epoch.json status → completed
    epoch["status"] = "completed"
    save_json(STATE_DIR / "epoch.json", epoch)

    git("add -A")
    score = best["total"]
    git(f'commit -m "epoch-{epoch_num}-end: 纪元{epoch_num}收敛 | 历经{civ_count}文明 | 得分{score}"')
    git_tag_epoch_end(epoch_num)


# ─── 主循环 ──────────────────────────────────────────────

def main():
    log("=" * 60)
    log("🚀 火星农场 Agent Loop 启动")
    log("=" * 60)
    log(f"🤖 角色配置")
    log(f"   农夫  → 模型:{FARMER_MODEL} | think:{FARMER_THINK} | API:Ollama原生/api/chat", "detail")
    log(f"   歌者  → 模型:{SINGER_MODEL_NAME} | API:DeepSeek", "detail")
    log(f"   农场主→ 模型:Claude Sonnet (灵耳)", "detail")
    log(f"⚙️  Loop参数 → token预算:{TOKEN_BUDGET:,} | 收敛线:{CONVERGENCE_SCORE} | 最大轮数:{MAX_ROUNDS}")

    epoch      = load_epoch()
    scores     = load_scores()
    perspectives = load_perspectives()

    epoch_num  = epoch["epoch_number"]
    start_civ  = epoch.get("current_civilization", 0) + 1

    log(f"📖 纪元{epoch_num} | 命题：{epoch['question'][:40]}...")
    log(f"📊 已完成文明数：{len(scores)} | 当前最高分：{get_best_score(scores)}")

    # 纪元第一个文明，打 start tag
    if start_civ == epoch.get("started_at_civilization", 1):
        git_tag_epoch_start(epoch_num)

    for round_i in range(MAX_ROUNDS):
        civ_num = start_civ + round_i
        perspective = random.choice(perspectives)

        try:
            result = run_civilization(civ_num, epoch, perspective, scores)
        except Exception as e:
            log(f"❌ 文明#{civ_num:03d} 运行异常：{e}")
            import traceback; traceback.print_exc()
            break

        log(f"📊 文明#{civ_num:03d} 完成 | 得分:{result['total']} | {result['verdict']} | {result['epitaph'][:40]}")

        # 收敛判断
        if result["verdict"] == "passed":
            finalize_epoch(epoch, scores, civ_num)
            log("✅ 纪元收敛，等待农场主设定下一纪元命题")
            break

        # 连续5轮无进展提示
        if len(scores) >= 5:
            recent = [s["total"] for s in scores[-5:]]
            if max(recent) - min(recent) < 2:
                log("⚠️  连续5个文明分数无实质进展，建议农场主介入调整命题")

        log("-" * 50)

    log("🏁 Loop 结束")


# ─── 纪元初始化工具 ──────────────────────────────────────

def init_epoch(epoch_num: int, question: str,
               acceptance_criteria: str, token_budget: int = 100000):
    """农场主调用：初始化新纪元"""
    data = {
        "epoch_number": epoch_num,
        "question": question,
        "acceptance_criteria": acceptance_criteria,
        "token_budget": token_budget,
        "started_at_civilization": 1,
        "current_civilization": 0,
        "next_hint": "",
        "status": "running",
    }
    save_json(STATE_DIR / "epoch.json", data)

    # 初始化 discoveries.md
    write(STATE_DIR / "discoveries.md",
          f"# 纪元{epoch_num} 已知定律\n\n_随文明积累更新_\n")

    # 初始化 briefing.md
    update_briefing(data, "", "", "", 1)

    # 初始化 epoch.md（含新表头：模型、时长、token、死亡、达标、墓志铭）
    epoch_md = HISTORY / "current" / "epoch.md"
    write(epoch_md, f"""# 纪元{epoch_num} 进行中

## 当前命题

> {question}

## 验收标准

{acceptance_criteria}

## Token预算

每个文明：**{token_budget:,} tokens**

## 文明进度

| 文明# | 模型 | 运行时长 | Token消耗 | 死亡方式 | 达标 | 墓志铭 |
|---|---|---|---|---|---|---|
| _等待第一个文明_ | | | | | | |

## 歌者的上一条提示

_（上一文明结束后，歌者留给下一文明的方向）_

> 你是本纪元第一个文明，自由探索。
""")

    # 更新 INDEX.md
    index_path = HISTORY / "INDEX.md"
    index = read(index_path)
    row = f"| 纪元{epoch_num} | {question} | 🔄 进行中 | - | - |"
    index += f"\n{row}\n"
    write(index_path, index)

    log(f"✅ 纪元{epoch_num} 初始化完成")
    log(f"   命题：{question}")


def reject_epoch(epoch_num: int, reason: str, lesson: str = ""):
    """
    农场主调用：否决已收敛的纪元（歌者通过但农场主不认可）。
    将该纪元答案移入 failure-lessons.md，并标记为 owner_rejected。
    之后需重新 init_epoch 重跑。
    """
    # 读取纪元信息
    epoch = load_epoch()
    if epoch["epoch_number"] != epoch_num:
        raise ValueError(f"当前纪元是 {epoch['epoch_number']}，不是 {epoch_num}")
    if epoch.get("status") not in ("completed",):
        raise ValueError(f"纪元 {epoch_num} 状态为 {epoch.get('status')}，只能否决已完成的纪元")

    # 标记否决
    epoch["owner_verdict"] = "rejected"
    epoch["owner_reject_reason"] = reason
    save_json(STATE_DIR / "epoch.json", epoch)

    # 追加到 failure-lessons.md
    lessons_path = STATE_DIR / "failure-lessons.md"
    lessons = read(lessons_path)
    answers_path = STATE_DIR / "epoch-answers.md"
    answers = read(answers_path)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    # 从 epoch-answers.md 里找到这个纪元的答案摘要
    entry = f"""
## 纪元{epoch_num}：{epoch['question'][:40]}...
**歌者评分：** （见 agent/civilizations/epoch-{epoch_num:03d}/）
**农场主判定：** ❌ 否决
**否决时间：** {today}
**否决原因：** {reason}
"""
    if lesson:
        entry += f"**教训：**\n{lesson}\n"
    entry += "\n---\n"

    write(lessons_path, lessons + entry)

    # 在 epoch-answers.md 里加否决标注
    write(answers_path, answers.replace(
        f"## 纪元{epoch_num}：",
        f"## ~~纪元{epoch_num}~~（农场主已否决）：",
    ))

    log(f"⚠️  纪元{epoch_num} 已被农场主否决，原因：{reason}")
    log(f"   失败教训已记入 state/failure-lessons.md")
    log(f"   请重新 init_epoch 发起新纪元")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "init":
        # 使用示例：python run.py init
        init_epoch(
            epoch_num=1,
            question="火星农场项目通过什么形式/模式运作，可以最大概率成功？",
            acceptance_criteria="""以下三条必须同时满足：
1. 明确第一个付费客户（具体机构或群体，非泛指）
2. 可信的资金来源（谁出钱，为什么出，大概规模）
3. 清晰的盈利路径（10年后如何独立盈利，不依赖补贴）""",
        )
    else:
        main()
