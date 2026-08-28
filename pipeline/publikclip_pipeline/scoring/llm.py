"""LLM backends: Gemini (BYO key, default) and Ollama (local fallback).

One interface: generate_json(prompt, schema, images) → dict, with disk
caching keyed on (backend, model, prompt, schema) so re-runs never re-spend
— the M2 gate requires cache hits on identical inputs.

Key resolution: PUBLIKCLIP_GEMINI_API_KEY env var, then
PUBLIKCLIP_HOME/secrets.json {"gemini_api_key": "..."} (written by the
app's onboarding). Ollama needs no key — just a running daemon.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from .. import config

# Pinned, and a per-job setting (Settings.gemini_model) overrides it. The
# previous value was the rolling alias "gemini-flash-latest", chosen because
# a pinned gemini-2.5-flash had 404'd for new keys — and then the alias
# itself died: on 2026-08-28 it returned persistent 503s ("high demand")
# while the versioned gemini-3.5/3.6-flash answered the same key fine
# (T-39). Both failure modes are real, so the policy is now: pin a stable
# versioned model, and keep the setting as the user's escape hatch. Do not
# trust ListModels alone when changing the pin — it advertises models that
# generateContent refuses (both the 404 and the 503 above were listed) —
# verify with a real generateContent call.
GEMINI_MODEL = config.DEFAULT_GEMINI_MODEL
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OLLAMA_URL = "http://localhost:11434"
LLM_TIMEOUT = 120.0


class LlmError(Exception):
    """User-actionable LLM failure (bad key, daemon down, model missing).

    `fatal` distinguishes "every remaining candidate will fail the same
    way" (bad key, no daemon, no quota left — abort the whole stage) from
    "this one call didn't pan out even after retries" (a transient outage
    on one candidate — skip it and keep scoring the rest, same as any other
    exception the scoring loop already tolerates). Defaults to True: an
    LlmError site that doesn't say otherwise keeps the prior fail-fast
    behavior.
    """

    def __init__(self, message: str, *, fatal: bool = True):
        super().__init__(message)
        self.fatal = fatal


def gemini_api_key() -> str | None:
    key = os.environ.get("PUBLIKCLIP_GEMINI_API_KEY")
    if key:
        return key
    secrets_path = config.home_dir() / "secrets.json"
    if secrets_path.exists():
        try:
            return json.loads(secrets_path.read_text(encoding="utf-8")).get("gemini_api_key")
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            # UnicodeDecodeError became reachable when the read became
            # explicitly utf-8; an unreadable secrets file must still fall
            # through to "no key", which the caller degrades on.
            return None
    return None


def _cache_dir() -> Path:
    path = config.home_dir() / "llm-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_key(backend: str, model: str, prompt: str, schema: dict, images: list[bytes]) -> str:
    h = hashlib.sha256()
    h.update(backend.encode())
    h.update(model.encode())
    h.update(prompt.encode())
    h.update(json.dumps(schema, sort_keys=True).encode())
    for img in images:
        h.update(hashlib.sha256(img).digest())
    return h.hexdigest()[:32]


def _retry_delay_seconds(error_body: dict) -> float | None:
    """Google's 429 responses attach a RetryInfo detail with an honest
    retryDelay (e.g. "40.17s") whenever waiting and retrying can succeed —
    the per-minute free-tier throttle. A genuine no-quota-left stop omits
    it. Returns None when there's nothing worth retrying for."""
    for d in error_body.get("details") or []:
        raw = d.get("retryDelay")
        if isinstance(raw, str) and raw.endswith("s"):
            try:
                return float(raw[:-1])
            except ValueError:
                continue
    return None


def _redact(text: str, secret: str | None) -> str:
    """A leaked 503 once printed the full request URL - API key included -
    into the UI log: httpx embeds request URLs in its error messages, and
    the key used to be a query parameter. The key now travels in a header
    (never part of the URL), and this is the belt on top: no secret may
    survive into an LlmError message, whatever some layer folds into it."""
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


class GeminiClient:
    backend = "gemini"

    def __init__(self, model: str | None = None):
        self.model = model or GEMINI_MODEL
        key = gemini_api_key()
        if not key:
            raise LlmError(
                "No Gemini API key found. Add one in Settings (or set "
                "PUBLIKCLIP_GEMINI_API_KEY), or switch to Ollama mode."
            )
        self._key = key

    def generate_json(
        self, prompt: str, schema: dict, images: list[bytes] | None = None
    ) -> dict:
        images = images or []
        cache_file = _cache_dir() / f"{_cache_key(self.backend, self.model, prompt, schema, images)}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))

        parts: list[dict[str, Any]] = [{"text": prompt}]
        for img in images:
            import base64

            parts.append(
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img).decode()}}
            )
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "temperature": 0.2,
            },
        }
        last_err: Exception | None = None
        attempts = 5
        for attempt in range(attempts):
            try:
                res = httpx.post(
                    GEMINI_URL.format(model=self.model),
                    # Header, never a query parameter: httpx puts the full
                    # request URL in its error text, which reaches the UI
                    # log - a `?key=` there once leaked a real key on a 503.
                    headers={"x-goog-api-key": self._key},
                    json=body,
                    timeout=LLM_TIMEOUT,
                )
                if res.status_code in (401, 403):
                    raise LlmError("Gemini rejected the API key. Check it in Settings.")
                if res.status_code == 429:
                    # Both a per-minute free-tier throttle and a genuine
                    # "no credits left" stop come back as a bare 429 whose
                    # message text always mentions "plan and billing
                    # details" as boilerplate — keying off that wording
                    # (the original approach) false-positives on the RPM
                    # case, which is the common one and clears in seconds.
                    # Google's structured error instead includes a
                    # RetryInfo detail with an honest retryDelay whenever
                    # retrying can actually help; trust that over wording.
                    try:
                        error_body = res.json()["error"]
                        detail = error_body["message"]
                    except Exception:  # noqa: BLE001
                        error_body, detail = {}, "rate limited"
                    last_err = LlmError(f"Gemini 429: {_redact(detail, self._key)}")
                    retry_delay = _retry_delay_seconds(error_body)
                    if retry_delay is None:
                        raise last_err
                    if attempt < attempts - 1:
                        time.sleep(min(retry_delay, 60.0))
                    continue
                res.raise_for_status()
                payload = res.json()
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(_strip_fences(text))
                cache_file.write_text(json.dumps(data), encoding="utf-8")
                return data
            except LlmError:
                raise
            except (httpx.HTTPError, KeyError, json.JSONDecodeError, IndexError) as err:
                last_err = err
                # 5xx / timeouts / connection blips are transient — the
                # first pass through this code retried instantly 3x with no
                # delay, which is barely different from 1 attempt against a
                # server that's still overloaded milliseconds later. This is
                # deep enough into the pipeline (post-ingest/asr/diarize/
                # events/candidates) that losing the whole job to a brief
                # 503 is a much worse outcome than waiting under a minute.
                if attempt < attempts - 1:
                    time.sleep(min(30, 2 ** attempt))
        raise LlmError(
            _redact(f"Gemini call failed after {attempts} attempts: {last_err}", self._key),
            fatal=False,
        )


class OllamaClient:
    backend = "ollama"

    def __init__(self, model: str | None = None):
        try:
            res = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
            res.raise_for_status()
        except httpx.HTTPError as err:
            raise LlmError(
                "Ollama isn't running. Start it (`ollama serve`) or switch to Gemini mode."
            ) from err
        models = [m["name"] for m in res.json().get("models", [])]
        if not models:
            raise LlmError("Ollama has no models. Pull one, e.g. `ollama pull llama3.1:8b`.")
        self.model = model if model in models else _pick_ollama_model(models)

    def generate_json(
        self, prompt: str, schema: dict, images: list[bytes] | None = None
    ) -> dict:
        if images:
            # Text-only fallback: the caller records visual as signals_missing.
            images = []
        cache_file = _cache_dir() / f"{_cache_key(self.backend, self.model, prompt, schema, [])}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "format": schema,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        try:
            res = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=600.0)
            res.raise_for_status()
            data = json.loads(_strip_fences(res.json()["message"]["content"]))
        except (httpx.HTTPError, KeyError, json.JSONDecodeError) as err:
            raise LlmError(f"Ollama call failed: {err}", fatal=False) from err
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        return data


def _pick_ollama_model(models: list[str]) -> str:
    """Prefer capable general models, and among them the LARGEST — list
    order once handed us qwen2.5:3b while 7b sat right there."""
    import re

    def size_of(name: str) -> float:
        m = re.search(r"(\d+(?:\.\d+)?)b", name.lower())
        return float(m.group(1)) if m else 0.0

    candidates = [
        name
        for prefix in ("llama3.1", "llama3", "qwen2.5", "qwen3", "mistral", "gemma2", "gemma3")
        for name in models
        if name.startswith(prefix)
    ]
    if candidates:
        return max(candidates, key=size_of)
    return models[0]


def make_client(llm_mode: str, gemini_model: str | None = None):
    if llm_mode == "ollama":
        return OllamaClient()
    return GeminiClient(gemini_model)
