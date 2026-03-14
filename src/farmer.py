"""
农夫模块 — 凡生执行者
使命：读史书，消耗 token，给出当前问题的最好答案，然后消亡

API 说明：
- 默认使用 Ollama 原生 /api/chat（支持 think 参数控制 thinking 模式）
- think 参数由 FARMER_THINK 环境变量控制（true/false）
- OpenAI compat /v1/chat/completions 不支持 think 参数，不推荐用于 thinking 模型
"""

import os
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

FARMER_API_URL     = os.getenv("FARMER_API_URL", "http://localhost:11434")
FARMER_API_KEY     = os.getenv("FARMER_API_KEY", "ollama")
FARMER_MODEL       = os.getenv("FARMER_MODEL", "qwen3.5:2b")
TOKEN_BUDGET       = int(os.getenv("TOKEN_BUDGET", "100000"))
USE_OLLAMA_NATIVE  = os.getenv("FARMER_USE_OLLAMA_NATIVE", "true").lower() in ("true", "1", "yes")
FARMER_THINK       = os.getenv("FARMER_THINK", "false").lower() in ("true", "1", "yes")

ROOT        = Path(__file__).parent.parent
PROMPTS_DIR = ROOT / "src" / "prompts"

# 项目根本使命（写入 system_prompt，最高优先级）
_MISSION = (
    "【项目根本使命，不可违背】"
    "火星农场有朝一日在火星开业，种出西红柿，并盈利。"
    "你的任何方案都必须服务于在火星土壤上真正种菜这一物理目标。"
    "纯数据服务、纯金融方案、纯地球农业方案——不符合使命，歌者将扣分。"
)


def build_context(epoch_num: int, civ_num: int, perspective: str,
                  briefing: str, discoveries: str, next_hint: str,
                  epoch_answers: str) -> str:
    """
    农夫的完整输入 = briefing.md 内容（已包含命题/验收标准/已知定律/提示）。
    perspective 已在 Controller 里替换进 briefing，直接返回。
    """
    return briefing


def call_farmer(context: str, civ_num: int, epoch_num: int) -> dict:
    """
    调用农夫 API。
    返回：{content, tokens_used, death, elapsed_sec}
    """
    system_prompt = (
        f"{_MISSION}\n\n"
        f"你是火星农场第{civ_num}文明的农夫，你的生命只有 {TOKEN_BUDGET} 个 token。"
        "读取史书，给出当前命题的最好答案，然后消亡。"
    )

    if USE_OLLAMA_NATIVE:
        return _call_ollama_native(system_prompt, context, civ_num)
    else:
        return _call_openai_compat(system_prompt, context)


def _call_ollama_native(system_prompt: str, context: str, civ_num: int) -> dict:
    """
    使用 Ollama 原生 /api/chat 接口。
    think 参数由 FARMER_THINK 环境变量控制（默认 false）。
    """
    payload = json.dumps({
        "model": FARMER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": context},
        ],
        "think": FARMER_THINK,   # 从环境变量读取，不硬编码
        "stream": False,
        "options": {
            "num_predict": 4096,
            "temperature": 0.8,
        },
    }).encode("utf-8")

    start = time.time()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{FARMER_API_URL}/api/chat",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except Exception as e:
            if attempt < 2:
                print(f"  [重试 {attempt+1}/3] {e}，等待10s...")
                time.sleep(10)
            else:
                raise RuntimeError(f"农夫 Ollama API 错误: {e}")

    elapsed = round(time.time() - start, 1)
    message = data.get("message", {})
    content = message.get("content", "") or ""

    prompt_eval = data.get("prompt_eval_count", 0)
    eval_count  = data.get("eval_count", 0)
    tokens_used = prompt_eval + eval_count

    done_reason = data.get("done_reason", "stop")
    death = "token_exhausted" if done_reason == "length" else "natural"

    return {
        "content":     content,
        "tokens_used": tokens_used,
        "death":       death,
        "elapsed_sec": elapsed,
    }


def _call_openai_compat(system_prompt: str, context: str) -> dict:
    """
    OpenAI 兼容接口（用于 DeepSeek 或其他非 Ollama 服务）。
    注意：不支持 think 参数，FARMER_THINK 配置在此接口下无效。
    """
    base = FARMER_API_URL.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"

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
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"{base}/chat/completions",
                data=payload,
                method="POST",
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {FARMER_API_KEY}",
                },
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            if e.code in (524, 502, 503) and attempt < 2:
                print(f"  [重试 {attempt+1}/3] HTTP {e.code}，等待10s...")
                time.sleep(10)
            else:
                raise RuntimeError(f"农夫 API 错误 {e.code}: {body}")
        except Exception as e:
            if attempt < 2:
                print(f"  [重试 {attempt+1}/3] {e}，等待10s...")
                time.sleep(10)
            else:
                raise RuntimeError(str(e))

    elapsed = round(time.time() - start, 1)
    choice  = data["choices"][0]
    content = choice["message"].get("content", "") or ""
    usage   = data.get("usage", {})
    tokens_used = usage.get("total_tokens", 0)
    death = "token_exhausted" if choice.get("finish_reason") == "length" else "natural"

    return {
        "content":     content,
        "tokens_used": tokens_used,
        "death":       death,
        "elapsed_sec": elapsed,
    }
