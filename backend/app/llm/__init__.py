"""LLM Provider 抽象层"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    max_tokens: int = 8192
    temperature: float = 0.7


@dataclass
class ChatMessage:
    role: str  # system / user / assistant
    content: str


class LLMProvider(ABC):
    """所有 Provider 必须实现的接口"""

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], config: LLMConfig) -> str:
        """非流式对话"""
        ...

    @abstractmethod
    async def chat_stream(self, messages: list[ChatMessage], config: LLMConfig) -> AsyncIterator[str]:
        """流式对话，逐 token 产出"""
        ...

    @abstractmethod
    async def test_connection(self, config: LLMConfig) -> dict:
        """测试连接，返回 {success, latency_ms, model}"""
        ...
