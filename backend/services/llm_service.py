import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(BACKEND_ROOT / ".env", override=True)


class LLMServiceError(RuntimeError):
    pass


def get_llm_provider() -> str:
    return os.getenv("LLM_PROVIDER", "mock").strip().lower()


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    timeout = _float_env("LLM_TIMEOUT_SECONDS", 20)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            response_text = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise LLMServiceError(f"LLM HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise LLMServiceError(f"LLM connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LLMServiceError("LLM request timed out") from exc

    try:
        return json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise LLMServiceError("LLM returned invalid JSON") from exc


def _generate_mock(prompt: str) -> str:
    return (
        "[mock fallback] 当前 LLM_PROVIDER=mock，未调用真实大模型。"
        f"收到 prompt 长度：{len(prompt)}。"
    )


def _generate_with_ollama(prompt: str) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": _float_env("LLM_TEMPERATURE", 0.4),
            "num_predict": _int_env("LLM_MAX_TOKENS", 700),
        },
    }
    data = _post_json(f"{base_url}/api/generate", payload)
    text = str(data.get("response", "")).strip()
    if not text:
        raise LLMServiceError("Ollama returned an empty response")
    return text


def _generate_with_qwen(prompt: str) -> str:
    api_key = os.getenv("QWEN_API_KEY", "").strip()
    if not api_key:
        raise LLMServiceError("QWEN_API_KEY is not configured")

    base_url = os.getenv(
        "QWEN_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).rstrip("/")
    model = os.getenv("QWEN_MODEL", "qwen-plus")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个安全、克制、温和的大学生情绪陪伴助手。"
                    "你不是医生，不做医学诊断，不提供药物建议，不承诺治疗效果。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": _float_env("LLM_TEMPERATURE", 0.4),
        "max_tokens": _int_env("LLM_MAX_TOKENS", 700),
    }
    data = _post_json(
        f"{base_url}/chat/completions",
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )

    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMServiceError("Qwen returned an unexpected response shape") from exc

    if not text:
        raise LLMServiceError("Qwen returned an empty response")
    return text


def generate_text(prompt: str) -> str:
    provider = get_llm_provider()

    if provider == "mock":
        return _generate_mock(prompt)
    if provider == "ollama":
        return _generate_with_ollama(prompt)
    if provider == "qwen":
        return _generate_with_qwen(prompt)

    raise LLMServiceError(
        f"Unsupported LLM_PROVIDER={provider}. Use mock, ollama, or qwen."
    )
