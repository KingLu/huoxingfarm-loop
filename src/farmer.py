"""
农夫模块 — 凡生执行者
当前配置：DeepSeek（快速模式，无 Cloudflare 超时问题）
使命：读史书，消耗 token，给出当前问题的最好答案，然后消亡
"""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

FARMER_API_URL = os.getenv("FARMER_API_URL", "http://localhost:11434/v1")
FARMER_API_KEY = os.getenv("FARMER_API_KEY", "ollama")
FARMER_MODEL   = os.getenv("FARMER_MODEL", "qwen3.5:0.8b")
TOKEN_BUDGET   = int(os.getenv("TOKEN_BUDGET", "100000"))

ROOT = Path(__file__).parent.parent
PROMPTS_DIR = ROOT / "src" / "prompts"


def load_farmer_prompt() -> str:
    return (PROMPTS_DIR / "farmer.md").read_text(encoding="utf-8")


def build_context(epoch_num: int, civ_num: int, perspective: str,
                  briefing: str, discoveries: str, next_hint: str,
                  epoch_answers: str) -> str:
    """
    农夫的完整输入 = briefing.md 的内容（已由 Controller 生成，含命题/验收标准/已知定律/提示）
    perspective 已在 Controller 里替换进 briefing，此处直接返回。
    """
    return briefing


def call_farmer(context: str, civ_num: int, epoch_num: int) -> dict:
    """
    调用农夫 API。
    返回：{content, tokens_used, death, elapsed_sec}
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
        "max_tokens": 4096,
        "temperature": 0.8,
        "stream": False,
    }).encode("utf-8")

    start = time.time()
    last_err = None

    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{FARMER_API_URL}/chat/completions",
                data=payload,
                method="POST",
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {FARMER_API_KEY}",
                    "User-Agent":    "curl/8.7.1",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            last_err = f"农夫 API 错误 {e.code}: {body}"
            if e.code in (524, 502, 503) and attempt < 2:
                print(f"  [重试 {attempt+1}/3] HTTP {e.code}，等待10s...")
                time.sleep(10)
            else:
                raise RuntimeError(last_err)
        except Exception as e:
            last_err = str(e)
            if attempt < 2:
                print(f"  [重试 {attempt+1}/3] {e}，等待10s...")
                time.sleep(10)
            else:
                raise RuntimeError(last_err)

    elapsed = round(time.time() - start, 1)
    choice  = data["choices"][0]
    message = choice["message"]
    content = message.get("content", "") or ""

    # qwen3.5 thinking 模式：实际输出在 reasoning 字段，content 为空
    if not content.strip():
        content = message.get("reasoning", "") or ""

    usage   = data.get("usage", {})
    tokens_used = usage.get("total_tokens",
                  usage.get("completion_tokens", 0) + usage.get("prompt_tokens", 0))

    death = "token_exhausted" if choice.get("finish_reason") == "length" else "natural"

    return {
        "content":     content,
        "tokens_used": tokens_used,
        "death":       death,
        "elapsed_sec": elapsed,
    }
