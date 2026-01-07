"""
Thin wrapper around OpenRouter API.
Uses the standard OpenAI-compatible interface.
"""

import json
import requests
from dataclasses import dataclass
from typing import Generator


@dataclass
class TokenUsage:
    """Token usage statistics from a single API call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class StreamingResponse:
    """Wrapper for streaming that captures both content and usage."""

    def __init__(self, generator: Generator[str, None, TokenUsage]):
        self._generator = generator
        self._usage: TokenUsage | None = None

    def __iter__(self):
        return self

    def __next__(self) -> str:
        try:
            return next(self._generator)
        except StopIteration as e:
            self._usage = e.value
            raise

    @property
    def usage(self) -> TokenUsage:
        """Get token usage. Only available after iteration completes."""
        return self._usage or TokenUsage()


class LLMClient:
    """Handles communication with OpenRouter."""
    
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    def __init__(self, api_key: str, default_model: str):
        self.api_key = api_key
        self.default_model = default_model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> StreamingResponse:
        """
        Stream a chat response, yielding chunks as they arrive.

        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Override default model if needed

        Returns:
            StreamingResponse that yields text chunks and provides usage stats after completion
        """
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
        }
        return StreamingResponse(self._stream_response(payload))
    
    def _stream_response(self, payload: dict) -> Generator[str, None, TokenUsage]:
        """Stream the response chunk by chunk, returning usage stats at the end."""
        response = requests.post(
            self.BASE_URL,
            headers=self.headers,
            json=payload,
            stream=True
        )
        response.raise_for_status()

        usage = TokenUsage()

        for line in response.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        # Yield content chunks
                        if content := chunk["choices"][0]["delta"].get("content"):
                            yield content
                        # Capture usage from final chunk (OpenRouter includes this)
                        if "usage" in chunk:
                            usage = TokenUsage(
                                prompt_tokens=chunk["usage"].get("prompt_tokens", 0),
                                completion_tokens=chunk["usage"].get("completion_tokens", 0),
                                total_tokens=chunk["usage"].get("total_tokens", 0),
                            )
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        return usage