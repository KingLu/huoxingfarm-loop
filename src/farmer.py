"""
农夫模块 — 凡生执行者
模型：qwen3.5:35b @ suanji GPU 工作站
使命：读史书，消耗 token，给出当前问题的最好答案，然后消亡
"""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

SUANJI_API_URL = os.getenv("SUANJI_API_URL", "https://chat.suanji.net/api/v1")
SUANJI_API_KEY = os.getenv("SUANJI_API_KEY", "")
FARMER_MODEL   = os.getenv("FARMER_MODEL", "qwen3.5:35b")
TOKEN_BUDGET   = int(os.getenv("TOKEN_BUDGET", "100000"))

ROOT = Path(__file__).parent.parent
PROMPTS_DIR = ROOT / "src" / "prompts"


def load_farmer_prompt() -> str:
    return (PROMPTS_DIR / "farmer.md").read_text(encoding="utf-8")


def build_context(epoch_num: int, civ_num: int, perspective: str,
                  briefing: str, discoveries: str, next_hint: str,
                  epoch_answers: str) -> str:
    """构建农夫的完整输入 context（农夫能看到的全部信息）"""
    template = load_farmer_prompt()
    return template.format(
        n=civ_num,
        perspective=perspective,
        briefing=briefing,
        discoveries=discoveries or "（暂无，你是本纪元第一个文明）",
        singer_gap=next_hint or "（暂无，你是本纪元第一个文明，请自由探索）",
        epoch_answers=epoch_answers or "（暂无，这是第一个纪元）",
        git_log_summary="（见 briefing.md 中的文明进度表）",
        current_best="（见 briefing.md）",
    )


def call_farmer(context: str, civ_num: int, epoch_num: int) -> dict:
    """
    调用农夫 API，带 token 计数器。
    返回：{
        "content": str,         # 农夫输出
        "tokens_used": int,     # 消耗的 token 数
        "death": str,           # "natural" | "token_exhausted"
        "elapsed_sec": float,
    }
    注意：suanji 要求 User-Agent: curl/8.7.1
    """
    system_prompt = (
        f"你是火星农场第{civ_num}文明的农夫，你的生命只有 {TOKEN_BUDGET} 个 token。"
        "读取史书，给出当前命题的最好答案，然后消亡。"
    )

    payload = json.dumps({
        "model": FARMER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": context},
        ],
        "max_tokens": TOKEN_BUDGET,
        "temperature": 0.8,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{SUANJI_API_URL}/chat/completions",
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SUANJI_API_KEY}",
            "User-Agent": "curl/8.7.1",   # suanji 必须这个 UA
        },
    )

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        raise RuntimeError(f"农夫 API 错误 {e.code}: {body}")

    elapsed = time.time() - start
    choice  = data["choices"][0]
    content = choice["message"]["content"]
    usage   = data.get("usage", {})
    tokens_used = usage.get("completion_tokens", 0) + usage.get("prompt_tokens", 0)

    # 判断死亡方式
    finish_reason = choice.get("finish_reason", "stop")
    death = "token_exhausted" if finish_reason == "length" else "natural"

    return {
        "content":     content,
        "tokens_used": tokens_used,
        "death":       death,
        "elapsed_sec": round(elapsed, 1),
    }
