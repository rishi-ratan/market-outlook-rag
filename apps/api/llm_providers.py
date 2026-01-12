"""
LLM Provider abstraction for supporting multiple LLM backends.
"""
import os
from abc import ABC, abstractmethod
from typing import Optional, Generator
from openai import OpenAI


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a response from the LLM."""
        pass

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        """Generate a streaming response from the LLM. Default implementation falls back to non-streaming."""
        # Default: fall back to non-streaming and yield the full response
        response = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        yield response

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the name of this provider."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider using OpenAI API."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        self.client = OpenAI(api_key=self.api_key)
        self.model_name = model_name

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] OpenAI API error: {e}")
            raise

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        """Generate a streaming response from OpenAI."""
        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[ERROR] OpenAI streaming error: {e}")
            raise

    def get_provider_name(self) -> str:
        return f"OpenAI-{self.model_name}"


class TogetherAIProvider(LLMProvider):
    """Together AI provider using their OpenAI-compatible API."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "Qwen/Qwen2.5-72B-Instruct"):
        self.api_key = api_key or os.getenv("TOGETHER_API_KEY")
        if not self.api_key:
            raise ValueError("TOGETHER_API_KEY is required for Together AI provider")

        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.together.xyz/v1",
        )
        self.model_name = model_name

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] Together AI API error: {e}")
            raise

    def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> Generator[str, None, None]:
        """Generate a streaming response from Together AI."""
        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            print(f"[ERROR] Together AI streaming error: {e}")
            raise

    def get_provider_name(self) -> str:
        return f"TogetherAI-{self.model_name.split('/')[-1]}"


# Provider cache
_provider_cache = {}


def get_provider(provider_name: str = "openai") -> LLMProvider:
    """Get an LLM provider instance by name."""
    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    if provider_name == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        provider = OpenAIProvider(model_name=model)
    elif provider_name == "together" or provider_name == "qwen":
        model = os.getenv("TOGETHER_MODEL", "Qwen/Qwen2.5-72B-Instruct")
        provider = TogetherAIProvider(model_name=model)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")

    _provider_cache[provider_name] = provider
    return provider
