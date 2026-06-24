import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .paths import PROJECT_ROOT


@dataclass
class LLMSettings:
    provider: str
    model: str
    base_url: str
    api_key: Optional[str]
    timeout_seconds: int


def load_local_env(path: Optional[Path] = None) -> None:
    """Load simple KEY=VALUE pairs from .env without overriding shell variables."""
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_llm_settings(provider_override: Optional[str] = None) -> LLMSettings:
    load_local_env()

    provider = provider_override or os.getenv("LLM_PROVIDER")
    if not provider:
        provider = "deepseek" if os.getenv("DEEPSEEK_API_KEY") else "mock"
    provider = provider.lower()

    if provider == "deepseek":
        return LLMSettings(
            provider="deepseek",
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            timeout_seconds=int(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        )

    if provider == "mock":
        return LLMSettings(
            provider="mock",
            model="local-rules",
            base_url="",
            api_key=None,
            timeout_seconds=0,
        )

    raise ValueError("Unsupported LLM provider: {}".format(provider))
