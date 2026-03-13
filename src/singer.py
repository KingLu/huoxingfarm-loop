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


def build_singer_input(civ_num: int, epoch_num: int, perspective: str,
                       farmer_output: str, tokens_used: int,
                       token_budget: int, death: str,
                       acceptance_criteria: str, last_score: int) -> str:
    """构建歌者的完整输入"""
    template = load_singer_prompt()
    death_note = {
        "natural": "自然终结（农夫主动完成作答）",
        "token_exhausted": f"token耗尽（消耗 {tokens_used}/{token_budget}，强制截断）",
    }.get(death, death)

    return template.format(
        n=civ_num,
        epoch=epoch_num,
        perspective=perspective,
        tokens_used=tokens_used,
        token_budget=token_budget,
        death_note=death_note,
        acceptance_criteria=acceptance_criteria,
        last_score=last_score,
        farmer_output=farmer_output,
    )


def call_singer(singer_input: str) -> dict:
    """
    调用歌者（DeepSeek）。
    返回：{
        "raw": str,          # 完整原始输出
        "evaluation": dict,  # 解析后的 JSON 评价
        "narrative": str,    # 文明叙事段落
        "elapsed_sec": float,
    }
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
        "temperature": 0.3,   # 歌者需要稳定和客观
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
    # 提取第一个 ```json ... ``` 块
    json_match = re.search(r"```json\s*([\s\S]*?)```", raw)
    if not json_match:
        # 尝试直接解析整体
        try:
            evaluation = json.loads(raw)
            narrative = ""
            return evaluation, narrative
        except Exception:
            raise ValueError(f"歌者输出中未找到 JSON 块:\n{raw[:500]}")

    evaluation = json.loads(json_match.group(1).strip())

    # 叙事段落：JSON 块之后的文本
    narrative = raw[json_match.end():].strip()

    return evaluation, narrative
