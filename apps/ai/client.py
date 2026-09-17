"""Single entry point for every LLM call (DESIGN.md §8).

All calls go through an OpenAI-compatible API, are validated with pydantic,
logged to AICallLog and fall back to deterministic mocks when AI_MOCK is on
or the capability has no model configured.
"""

import base64
import json
import logging
import mimetypes
import re
import time
from pathlib import Path

from django.conf import settings
from pydantic import BaseModel, ValidationError

from . import mock
from .models import AICallLog, PromptTemplate

logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).parent / "prompts"


class AIError(Exception):
    pass


def get_prompt(code: str) -> tuple[str, int | None]:
    tpl = PromptTemplate.objects.filter(code=code, is_active=True).order_by("-version").first()
    if tpl:
        return tpl.content, tpl.version
    return (PROMPT_DIR / f"{code}.txt").read_text(encoding="utf-8"), None


def render(template: str, variables: dict) -> str:
    for key, value in variables.items():
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, default=str)
        template = template.replace("{{" + key + "}}", value)
    return template


def is_mock(capability: str = "chat") -> bool:
    if settings.AI_MOCK:
        return True
    if capability == "vision":
        return not settings.VISION_MODEL
    if capability == "embedding":
        return not settings.EMBEDDING_MODEL
    return False


def _client(base_url: str, api_key: str):
    from openai import OpenAI

    return OpenAI(base_url=base_url, api_key=api_key, timeout=settings.AI_TIMEOUT, max_retries=2)


def _log(**kwargs) -> None:
    try:
        AICallLog.objects.create(**kwargs)
    except Exception:  # logging must never break the business flow
        logger.exception("failed to write AICallLog")


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def _chat(messages, *, model, base_url, api_key, json_mode):
    kwargs = {"model": model, "messages": messages, "temperature": 0.2}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    client = _client(base_url, api_key)
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:
        # Some compatible providers reject response_format; retry once without it.
        if json_mode and "response_format" in str(exc):
            kwargs.pop("response_format")
            resp = client.chat.completions.create(**kwargs)
        else:
            raise
    usage = resp.usage
    return resp.choices[0].message.content or "", (usage.prompt_tokens if usage else 0), (usage.completion_tokens if usage else 0)


def _run_json(task, prompt_code, schema, messages, *, capability, mock_fn, model, base_url, api_key, log_request):
    template_version = get_prompt(prompt_code)[1]
    started = time.monotonic()
    if is_mock(capability):
        data = mock_fn()
        result = schema.model_validate(data)
        _log(task=task, model="mock", prompt_code=prompt_code, prompt_version=template_version, request=log_request,
             response=json.dumps(data, ensure_ascii=False), latency_ms=int((time.monotonic() - started) * 1000), is_mock=True)
        return result

    tokens_in = tokens_out = 0
    last_error = content = ""
    for _ in range(2):
        try:
            content, ti, to = _chat(messages, model=model, base_url=base_url, api_key=api_key, json_mode=True)
            tokens_in += ti
            tokens_out += to
            result = schema.model_validate(_extract_json(content))
            _log(task=task, model=model, prompt_code=prompt_code, prompt_version=template_version, request=log_request,
                 response=content, tokens_in=tokens_in, tokens_out=tokens_out,
                 latency_ms=int((time.monotonic() - started) * 1000))
            return result
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)[:1000]
            # Feed the validation error back once so the model can correct itself.
            messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"Your JSON was invalid: {last_error}. Return ONLY valid JSON matching the requested structure."},
            ]
        except Exception as exc:
            last_error = str(exc)[:1000]
            break
    _log(task=task, model=model, prompt_code=prompt_code, prompt_version=template_version, request=log_request,
         tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=int((time.monotonic() - started) * 1000),
         success=False, error=last_error)
    raise AIError(last_error)


def chat_json(task: str, prompt_code: str, variables: dict, schema: type[BaseModel]) -> BaseModel:
    prompt = render(get_prompt(prompt_code)[0], variables)
    messages = [{"role": "user", "content": prompt}]
    return _run_json(
        task, prompt_code, schema, messages,
        capability="chat", mock_fn=lambda: mock.chat_json(prompt_code, variables),
        model=settings.LLM_MODEL, base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY,
        log_request={"prompt": prompt},
    )


def vision_json(task: str, prompt_code: str, image_path: str, schema: type[BaseModel]) -> BaseModel:
    prompt = get_prompt(prompt_code)[0]
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    messages = [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ]}]
    return _run_json(
        task, prompt_code, schema, messages,
        capability="vision", mock_fn=lambda: mock.vision_json(prompt_code, image_path),
        model=settings.VISION_MODEL, base_url=settings.VISION_BASE_URL, api_key=settings.VISION_API_KEY,
        log_request={"prompt": prompt, "image": Path(image_path).name},
    )


def chat_text(task: str, prompt_code: str, variables: dict) -> str:
    template, version = get_prompt(prompt_code)
    prompt = render(template, variables)
    started = time.monotonic()
    if is_mock("chat"):
        text = mock.chat_text(prompt_code, variables)
        _log(task=task, model="mock", prompt_code=prompt_code, prompt_version=version, request={"prompt": prompt},
             response=text, latency_ms=int((time.monotonic() - started) * 1000), is_mock=True)
        return text
    try:
        text, ti, to = _chat([{"role": "user", "content": prompt}], model=settings.LLM_MODEL,
                             base_url=settings.LLM_BASE_URL, api_key=settings.LLM_API_KEY, json_mode=False)
    except Exception as exc:
        _log(task=task, model=settings.LLM_MODEL, prompt_code=prompt_code, prompt_version=version, request={"prompt": prompt},
             latency_ms=int((time.monotonic() - started) * 1000), success=False, error=str(exc)[:1000])
        raise AIError(str(exc)) from exc
    _log(task=task, model=settings.LLM_MODEL, prompt_code=prompt_code, prompt_version=version, request={"prompt": prompt},
         response=text, tokens_in=ti, tokens_out=to, latency_ms=int((time.monotonic() - started) * 1000))
    return text


def embed(texts: list[str], task: str = "embedding") -> list[list[float]]:
    dim = settings.EMBEDDING_DIM
    started = time.monotonic()
    if is_mock("embedding"):
        vectors = [mock.embed(t, dim) for t in texts]
        _log(task=task, model="mock-hashing", request={"count": len(texts), "sample": texts[0][:200] if texts else ""},
             latency_ms=int((time.monotonic() - started) * 1000), is_mock=True)
        return vectors
    client = _client(settings.EMBEDDING_BASE_URL, settings.EMBEDDING_API_KEY)
    vectors: list[list[float]] = []
    try:
        for i in range(0, len(texts), 10):  # several providers cap batch size at 10
            chunk = texts[i : i + 10]
            try:
                resp = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=chunk, dimensions=dim)
            except Exception as exc:
                if "dimension" not in str(exc).lower():
                    raise
                resp = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=chunk)
            vectors += [d.embedding for d in resp.data]
        if vectors and len(vectors[0]) != dim:
            raise AIError(f"embedding model returned {len(vectors[0])} dims, expected {dim}")
    except Exception as exc:
        _log(task=task, model=settings.EMBEDDING_MODEL, request={"count": len(texts)}, success=False, error=str(exc)[:1000],
             latency_ms=int((time.monotonic() - started) * 1000))
        raise AIError(str(exc)) from exc
    _log(task=task, model=settings.EMBEDDING_MODEL, request={"count": len(texts), "sample": texts[0][:200] if texts else ""},
         latency_ms=int((time.monotonic() - started) * 1000))
    return vectors
