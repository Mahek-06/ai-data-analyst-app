"""Central configuration, read from environment variables (and a local .env file)."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    """Minimal .env reader (no extra dependency); real environment variables win."""
    for name in (".env", ".env.txt"):  # .env.txt: Windows Notepad often adds .txt
        path = ROOT / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if not os.environ.get(key.strip()):
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


@dataclass(frozen=True)
class Settings:
    provider: str = "gemini"      # "gemini" or "anthropic"
    api_key: str = ""             # Anthropic key
    model: str = "claude-sonnet-5-5"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    history_turns: int = 6        # past Q&A turns sent to the LLM for context
    preview_rows: int = 30        # result rows sent to the LLM for narration
    max_sql_retries: int = 1      # self-repair attempts for failing SQL
    max_result_rows: int = 5000   # hard cap on rows returned to the UI


def get_settings(api_key: str = "", provider: str = "", model: str = "") -> Settings:
    """Explicit arguments (from the UI) win over environment variables / .env."""
    _load_env_file()
    provider = provider or os.getenv("LLM_PROVIDER", "gemini")
    gem = provider == "gemini"
    return Settings(
        provider=provider,
        api_key=(not gem and api_key) or os.getenv("ANTHROPIC_API_KEY", ""),
        model=(not gem and model) or os.getenv("ANALYST_MODEL", "claude-sonnet-5-5"),
        gemini_api_key=(gem and api_key) or os.getenv("GEMINI_API_KEY", ""),
        gemini_model=(gem and model) or os.getenv("GEMINI_MODEL", "gemini-3.5-flash"),
        gemini_fallback_model=os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite"),
    )
