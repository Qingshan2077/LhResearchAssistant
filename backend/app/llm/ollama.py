"""Ollama Provider — 本地模型"""

import time
from typing import AsyncIterator
from loguru import logger
from openai import AsyncOpenAI

from app.llm import LLMProvider, LLMConfig, ChatMessage


class OllamaProvider(LLMProvider):
    """本地 Ollama 调用（Ollama 提供 OpenAI 兼容接口）"""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen2.5:7b"

    async def _client(self, config: LLMConfig) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=config.api_key or "ollama",  # Ollama 不需要真实 key
            base_url=config.base_url or self.DEFAULT_BASE_URL,
        )

    async def chat(self, messages: list[ChatMessage], config: LLMConfig) -> str:
        client = await self._client(config)
        resp = await client.chat.completions.create(
            model=config.model or self.DEFAULT_MODEL,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
        return resp.choices[0].message.content or ""

    async def chat_stream(self, messages: list[ChatMessage], config: LLMConfig) -> AsyncIterator[str]:
        client = await self._client(config)
        stream = await client.chat.completions.create(
            model=config.model or self.DEFAULT_MODEL,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def test_connection(self, config: LLMConfig) -> dict:
        start = time.time()
        try:
            client = await self._client(config)
            await client.chat.completions.create(
                model=config.model or self.DEFAULT_MODEL,
                messages=[{"role": "user", "content": "Respond with only: OK"}],
                max_tokens=10,
            )
            latency_ms = int((time.time() - start) * 1000)
            return {"success": True, "latency_ms": latency_ms, "model": config.model or self.DEFAULT_MODEL}
        except Exception as e:
            logger.error("LLM connection test failed: {}", e)
            return {"success": False, "error": str(e), "latency_ms": int((time.time() - start) * 1000)}
