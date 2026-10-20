import io
import json
import urllib.error
import urllib.request

import pytest

from analyst.config import Settings
from analyst.errors import LLMError
from analyst.llm import GeminiClient, extract_json

OK = {"candidates": [{"content": {"parts": [{"text": '{"ok": 1}'}]}}]}


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def client():
    return GeminiClient(Settings(gemini_api_key="k"), sleep=lambda s: None)


def script(monkeypatch, outcomes):
    calls = []

    def fake(req, timeout=0):
        calls.append(req.full_url)
        out = outcomes.pop(0)
        if out == "503":
            raise urllib.error.HTTPError(req.full_url, 503, "x", {}, io.BytesIO(b"busy"))
        return Resp(json.dumps(out).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    return calls


def test_extract_json_handles_code_fences():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_retries_after_503(monkeypatch):
    calls = script(monkeypatch, ["503", OK])
    assert client().complete_json("s", "u") == {"ok": 1} and len(calls) == 2


def test_falls_back_to_second_model(monkeypatch):
    calls = script(monkeypatch, ["503", "503", "503", OK])
    assert client().complete_json("s", "u") == {"ok": 1} and "flash-lite" in calls[-1]


def test_gives_up_with_clear_message(monkeypatch):
    script(monkeypatch, ["503"] * 6)
    with pytest.raises(LLMError, match="overloaded"):
        client().complete_json("s", "u")
