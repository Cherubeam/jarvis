"""
Thin wrapper around OpenRouter API.
Uses the standard OpenAI-compatible interface.
"""

import json
import requests
from typing import Generator


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
    
    def chat(
        self, 
        messages: list[dict], 
        model: str | None = None,
        stream: bool = True
    ) -> Generator[str, None, None] | str:
        """
        Send messages to the LLM and get a response.
        
        Args:
            messages: List of {"role": "...", "content": "..."} dicts
            model: Override default model if needed
            stream: If True, yields chunks as they arrive
        
        Returns:
            Generator of text chunks if streaming, else complete response
        """
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": stream,
        }
        
        if stream:
            return self._stream_response(payload)
        else:
            return self._get_response(payload)
    
    def _stream_response(self, payload: dict) -> Generator[str, None, None]:
        """Stream the response chunk by chunk."""
        response = requests.post(
            self.BASE_URL,
            headers=self.headers,
            json=payload,
            stream=True
        )
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if content := chunk["choices"][0]["delta"].get("content"):
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    
    def _get_response(self, payload: dict) -> str:
        """Get complete response at once."""
        payload["stream"] = False
        response = requests.post(
            self.BASE_URL,
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]