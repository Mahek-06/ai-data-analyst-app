"""Thin wrapper around the Anthropic API that always returns parsed JSON."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from .config import Settings
from .errors import LLMError


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a model reply (tolerates code fences / prose)."""
    text = re.sub(r"```(?:json)?", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise LLMError("The model did not return JSON.")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"The model returned malformed JSON: {exc}") from exc


class LLMClient:
    """`client` can be injected for tests; otherwise the Anthropic SDK is used."""

    def __init__(self, settings: Settings, client=None) -> None:
        self.settings = settings
        if client is None:
            if not settings.api_key:
                raise LLMError("No API key found. Paste it in the sidebar, or put ANTHROPIC_API_KEY=... in a .env file next to app.py, then restart.")
            from anthropic import Anthropic

            client = Anthropic(api_key=settings.api_key)
        self.client = client

    def complete_json(self, system: str, user: str) -> dict:
        try:
            resp = self.client.messages.create(
                model=self.settings.model,
                max_tokens=2500,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except Exception as exc:  # SDK raises several error types (auth, rate limit, network)
            raise LLMError(f"LLM request failed: {exc}") from exc
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return extract_json(text)


class _Overloaded(Exception):
    """Temporary Google-side error (500/503/504): safe to retry."""


class GeminiClient:
    """Google Gemini via the plain REST API (no extra SDK needed); has a free tier.

    Temporary overloads (HTTP 503) are retried with a short back-off, then the
    fallback model is tried, so a busy moment does not break the app.
    """

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    ATTEMPTS_PER_MODEL = 3
    BACKOFF_SECONDS = (2, 5)

    def __init__(self, settings: Settings, sleep=time.sleep) -> None:
        if not settings.gemini_api_key:
            raise LLMError("No Gemini API key found. Paste it in the sidebar, or put "
                           "GEMINI_API_KEY=... in a .env file next to app.py, then restart.")
        self.settings, self._sleep = settings, sleep
        self.key = settings.gemini_api_key.strip().strip("\"'")

    def complete_json(self, system: str, user: str) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 4096},
        }
        models = [self.settings.gemini_model]
        if self.settings.gemini_fallback_model not in models:
            models.append(self.settings.gemini_fallback_model)
        for model in models:
            for attempt in range(self.ATTEMPTS_PER_MODEL):
                try:
                    return self._parse(self._post(model, body))
                except _Overloaded:
                    if attempt < self.ATTEMPTS_PER_MODEL - 1:
                        self._sleep(self.BACKOFF_SECONDS[min(attempt, len(self.BACKOFF_SECONDS) - 1)])
        raise LLMError("Gemini is overloaded right now (503). Wait a minute and ask again, "
                       "or choose a different model in the sidebar.")

    def _post(self, model: str, body: dict) -> dict:
        req = urllib.request.Request(
            self.URL.format(model=model),
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code in (500, 503, 504):
                raise _Overloaded from exc
            detail = exc.read().decode(errors="replace")[:300]
            hint = ""
            if exc.code == 429:
                hint = (" Free-tier quota reached or the model isn't available on your tier: wait a minute "
                        "or pick another model in the sidebar.")
            if "API_KEY_INVALID" in detail:
                hint = (" Google rejected the key: re-copy it from aistudio.google.com/apikey (no spaces or "
                        "quotes), make sure it is a Gemini key, and that .env has no placeholder text.")
            raise LLMError(f"Gemini request failed ({exc.code}).{hint} {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMError(f"Could not reach Gemini: {exc}") from exc

    @staticmethod
    def _parse(data: dict) -> dict:
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Gemini returned no answer (the request may have been blocked).") from exc
        return extract_json("".join(p.get("text", "") for p in parts if not p.get("thought")))


def make_llm(settings: Settings):
    """Pick the provider chosen in settings."""
    return GeminiClient(settings) if settings.provider == "gemini" else LLMClient(settings)
