import json
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import LLMSettings


class LLMError(RuntimeError):
    pass


class DeepSeekChatModel:
    def __init__(self, settings: LLMSettings):
        if not settings.api_key:
            raise LLMError("DEEPSEEK_API_KEY is required when provider is deepseek.")
        self.settings = settings

    @property
    def display_name(self) -> str:
        return "{}:{}".format(self.settings.provider, self.settings.model)

    def complete(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        endpoint = "{}/chat/completions".format(self.settings.base_url.rstrip("/"))
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.settings.api_key),
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMError("DeepSeek API returned HTTP {}: {}".format(exc.code, body)) from exc
        except URLError as exc:
            raise LLMError("DeepSeek API request failed: {}".format(exc.reason)) from exc
        except TimeoutError as exc:
            raise LLMError("DeepSeek API request timed out.") from exc

        data = json.loads(response_body)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected DeepSeek response: {}".format(response_body)) from exc

        if not content:
            raise LLMError("DeepSeek returned an empty response.")
        return content.strip()


def create_chat_model(settings: LLMSettings) -> Optional[DeepSeekChatModel]:
    if settings.provider == "mock":
        return None
    if settings.provider == "deepseek":
        return DeepSeekChatModel(settings)
    raise ValueError("Unsupported LLM provider: {}".format(settings.provider))
