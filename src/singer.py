"""
歌者模块 — 永生史官
模型：DeepSeek（deepseek-chat）
使命：客观评价阶段命题是否达到验收标准，并记录史书
"""

import os
import json
import time
import re
import urllib.request
import urllib.error
from pathlib import Path

DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
SINGER_MODEL     = os.getenv("SINGER_MODEL", "deepseek-chat")

ROOT = Path(__file__).parent.parent
PROMPTS_DIR = ROOT / "src" / "prompts"


def load_singer_prompt() -> str:
    return (PROMPTS_DIR / "singer.md").read_text(encoding="utf-8")


def _human_duration(seconds: float) -> str:
    """把秒数转为人类可读时长"""
    if seconds < 60:
        return f"{int(seconds)}秒"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}分{s}秒"
    else:
        h, r = divmod(int(seconds), 3600)
        m = r // 60
        return f"{h}小时{m}分"


def build_singer_input(civ_num: int, epoch_num: int, perspective: str,
                       farmer_output: str, tokens_used: int,
                       token_budget: int, death: str,
                       acceptance_criteria: str, last_score: int,
                       farmer_model: str = "", farmer_elapsed_sec: float = 0) -> str:
    """构建歌者的完整输入"""
    template = load_singer_prompt()
    death_note = {
        "natural": "自然终结（农夫主动完成作答）",
        "token_exhausted": f"token耗尽（消耗 {tokens_used}/{token_budget}，强制截断）",
    }.get(death, death)

    elapsed_human = _human_duration(farmer_elapsed_sec)

    # 把 markdown 代码块里的 { } 转义，避免被 .format() 误解析
    def escape_code_blocks(m):
        return m.group(0).replace("{", "{{").replace("}", "}}")
    safe_template = re.sub(r"```[\s\S]*?```", escape_code_blocks, template)

    return safe_template.format(
        n=civ_num,
        epoch=epoch_num,
        perspective=perspective,
        tokens_used=tokens_used,
        token_budget=token_budget,
        death_note=death_note,
        acceptance_criteria=acceptance_criteria,
        last_score=last_score,
        farmer_output=farmer_output,
        farmer_model=farmer_model or "未知",
        farmer_elapsed=elapsed_human,
    )


def call_singer(singer_input: str) -> dict:
    """
    调用歌者（DeepSeek）。
    返回：{raw, evaluation, narrative, elapsed_sec}
    """
    system_prompt = (
        "你是火星农场史诗的歌者，永生的史官。"
        "你不参与战略制定，你只负责观察、评价、记录。"
        "你的评价必须客观公正，绝不因为农夫努力就手软，也不因为答案创新就盲目赞扬。"
        "验收标准是唯一标尺。"
    )

    payload = json.dumps({
        "model": SINGER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": singer_input},
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{DEEPSEEK_API_URL}/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        },
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"歌者 API 错误 {e.code}: {body}")

    elapsed = time.time() - start
    raw = data["choices"][0]["message"]["content"]
    evaluation, narrative = parse_singer_output(raw)

    return {
        "raw":         raw,
        "evaluation":  evaluation,
        "narrative":   narrative,
        "elapsed_sec": round(elapsed, 1),
    }


def parse_singer_output(raw: str) -> tuple[dict, str]:
    """从歌者输出中解析 JSON 评价块 和 文明叙事"""
    json_match = re.search(r"```json\s*([\s\S]*?)```", raw)
    if not json_match:
        try:
            return json.loads(raw), ""
        except Exception:
            raise ValueError(f"歌者输出中未找到 JSON 块:\n{raw[:500]}")

    evaluation = json.loads(json_match.group(1).strip())
    narrative = raw[json_match.end():].strip()

    # 若歌者返回6维度（含 mission_alignment），自动折算总分
    scores = evaluation.get("scores", {})
    if "mission_alignment" in scores and "total" not in evaluation:
        raw_total = sum(scores.values())
        evaluation["raw_total"] = raw_total
        evaluation["total"] = round(raw_total / 120 * 100)
    elif "raw_total" in evaluation and evaluation.get("total", 0) == 0:
        evaluation["total"] = round(evaluation["raw_total"] / 120 * 100)

    return evaluation, narrative
