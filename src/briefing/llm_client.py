"""
Multi-provider LLM client for briefing synthesis.
Supports: Groq (primary), Google Gemini (fallback), OpenRouter (backup), Cloudflare Workers AI (backup).
"""
import json
import os
from typing import Any, Dict, List, Optional, Literal

import httpx
from pydantic import BaseModel

from src.config import settings


class LLMMessage(BaseModel):
    """LLM message format."""
    role: str  # system, user, assistant
    content: str


class LLMResponse(BaseModel):
    """LLM response format."""
    content: str
    model: str
    usage: Dict[str, int] = {}
    provider: str = ""


class BaseLLMClient:
    """Base class for LLM clients."""

    def __init__(self, name: str):
        self.name = name
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def chat_completion(
        self,
        messages: List[LLMMessage],
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Make a chat completion request. Override in subclasses."""
        raise NotImplementedError

    async def synthesize_briefing(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Synthesize briefing using LLM."""
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        response = await self.chat_completion(
            messages=messages,
            response_format=response_format,
            temperature=0.3,
        )

        return response.content

    async def structure_briefing(
        self,
        briefing_data: Dict[str, Any],
        template: str,
    ) -> Dict[str, Any]:
        """Structure briefing data into sections using LLM."""
        system_prompt = """You are a senior financial analyst and macroeconomic researcher creating a morning intelligence briefing.
Your task is to synthesize raw market data, news, and economic indicators into a structured, professional briefing.
Follow the template structure exactly. Be concise, factual, and actionable.
Distinguish verified facts from interpretations. Flag missing or unreliable data.
Use professional financial terminology appropriate for a mortgage analyst.
Include specific numbers, timestamps, and sources where relevant."""

        user_prompt = f"""Raw briefing data:
{json.dumps(briefing_data, indent=2, default=str)}

Template structure:
{template}

Generate the briefing following the template exactly. Return as JSON with section keys matching the template."""

        response = await self.chat_completion(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_response": response.content}

    async def translate_briefing(
        self,
        briefing: Dict[str, Any],
        target_language: str,
    ) -> Dict[str, Any]:
        """Translate briefing to target language."""
        system_prompt = f"""You are a professional financial translator. Translate the briefing to {target_language}.
Preserve all numbers, symbols, currency codes, percentages, and technical terms.
Keep the structure identical. Only translate natural language text."""

        user_prompt = f"Translate this briefing to {target_language}:\n{json.dumps(briefing, ensure_ascii=False, default=str)}"

        response = await self.chat_completion(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return briefing


class GroqClient(BaseLLMClient):
    """Groq API client - fast inference, generous free tier."""

    def __init__(self):
        super().__init__("groq")
        self.api_key = settings.groq_api_key
        self.model = settings.groq_model
        self.fallback_model = settings.groq_fallback_model
        self.base_url = settings.groq_base_url

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(120.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat_completion(
        self,
        messages: List[LLMMessage],
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Make a chat completion request to Groq."""
        payload = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "max_tokens": max_tokens or 8000,
            "temperature": temperature if temperature is not None else 0.3,
        }

        if response_format:
            payload["response_format"] = response_format

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data.get("model", self.model),
                usage=data.get("usage", {}),
                provider="groq",
            )

        except httpx.HTTPStatusError as e:
            # Try fallback model on rate limit or model error
            if e.response.status_code in (429, 500) and self.model != self.fallback_model:
                return await self._try_fallback(messages, response_format, max_tokens, temperature)
            raise Exception(f"Groq API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Groq request failed: {e}")

    async def _try_fallback(
        self,
        messages: List[LLMMessage],
        response_format: Optional[Dict],
        max_tokens: Optional[int],
        temperature: Optional[float],
    ) -> LLMResponse:
        """Try with fallback model."""
        original_model = self.model
        self.model = self.fallback_model
        try:
            return await self.chat_completion(messages, response_format, max_tokens, temperature)
        finally:
            self.model = original_model


class GeminiClient(BaseLLMClient):
    """Google Gemini API client - good fallback."""

    def __init__(self):
        super().__init__("gemini")
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.base_url = settings.gemini_base_url

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=f"{self.base_url}/models/{self.model}",
                timeout=httpx.Timeout(120.0),
                headers={
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat_completion(
        self,
        messages: List[LLMMessage],
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Make a chat completion request to Gemini."""
        # Convert messages to Gemini format
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                contents.append({
                    "role": "user" if msg.role == "user" else "model",
                    "parts": [{"text": msg.content}],
                })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens or 8000,
                "temperature": temperature if temperature is not None else 0.3,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        if response_format and response_format.get("type") == "json_object":
            payload["generationConfig"]["responseMimeType"] = "application/json"

        params = {"key": self.api_key}

        try:
            response = await self.client.post(":generateContent", params=params, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract content from Gemini response
            candidates = data.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                text = "".join(p.get("text", "") for p in parts)

                return LLMResponse(
                    content=text,
                    model=self.model,
                    usage=data.get("usageMetadata", {}),
                    provider="gemini",
                )

            raise Exception("No content in Gemini response")

        except httpx.HTTPStatusError as e:
            raise Exception(f"Gemini API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Gemini request failed: {e}")


class OpenRouterClient(BaseLLMClient):
    """OpenRouter API client - backup with many models."""

    def __init__(self):
        super().__init__("openrouter")
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.base_url = settings.openrouter_base_url
        self.max_tokens = settings.openrouter_max_tokens
        self.temperature = settings.openrouter_temperature

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(120.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/user/morning-intelligence",
                    "X-Title": "Morning Intelligence Assistant",
                },
            )
        return self._client

    async def chat_completion(
        self,
        messages: List[LLMMessage],
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Make a chat completion request to OpenRouter."""
        payload = {
            "model": self.model,
            "messages": [m.model_dump() for m in messages],
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
        }

        if response_format:
            payload["response_format"] = response_format

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

            return LLMResponse(
                content=data["choices"][0]["message"]["content"],
                model=data.get("model", self.model),
                usage=data.get("usage", {}),
                provider="openrouter",
            )

        except httpx.HTTPStatusError as e:
            raise Exception(f"OpenRouter API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"OpenRouter request failed: {e}")


class CloudflareClient(BaseLLMClient):
    """Cloudflare Workers AI client - backup."""

    def __init__(self):
        super().__init__("cloudflare")
        self.account_id = settings.cloudflare_account_id
        self.api_token = settings.cloudflare_api_token
        self.model = settings.cloudflare_model
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run"

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(120.0),
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def chat_completion(
        self,
        messages: List[LLMMessage],
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Make a chat completion request to Cloudflare Workers AI."""
        # Cloudflare uses a simpler format
        prompt_parts = []
        for msg in messages:
            if msg.role == "system":
                prompt_parts.append(f"System: {msg.content}")
            elif msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                prompt_parts.append(f"Assistant: {msg.content}")

        prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"

        payload = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens or 8000,
            "temperature": temperature if temperature is not None else 0.3,
        }

        if response_format and response_format.get("type") == "json_object":
            payload["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.post(f"{self.base_url}/{self.model}", json=payload)
            response.raise_for_status()
            data = response.json()

            # Cloudflare returns result in 'result' field
            result = data.get("result", {})
            content = result.get("response", "") or result.get("text", "")

            return LLMResponse(
                content=content,
                model=self.model,
                usage={},
                provider="cloudflare",
            )

        except httpx.HTTPStatusError as e:
            raise Exception(f"Cloudflare API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Cloudflare request failed: {e}")


class MultiLLMClient:
    """Multi-provider LLM client with automatic fallback."""

    def __init__(self):
        self.providers: Dict[str, BaseLLMClient] = {
            "groq": GroqClient(),
            "gemini": GeminiClient(),
            "openrouter": OpenRouterClient(),
            "cloudflare": CloudflareClient(),
        }

        # Determine order from settings
        primary = settings.llm_primary
        fallback = settings.llm_fallback

        self.provider_order = [primary, fallback]
        # Add remaining as backups
        for p in ["groq", "gemini", "openrouter", "cloudflare"]:
            if p not in self.provider_order:
                self.provider_order.append(p)

    async def close(self):
        """Close all clients."""
        for provider in self.providers.values():
            await provider.close()

    def _get_client(self, provider_name: str) -> Optional[BaseLLMClient]:
        """Get client if configured."""
        client = self.providers.get(provider_name)
        if client and hasattr(client, 'api_key') and client.api_key:
            return client
        if client and hasattr(client, 'account_id') and client.account_id:
            return client
        return None

    async def chat_completion(
        self,
        messages: List[LLMMessage],
        response_format: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Try providers in order until one succeeds."""
        last_error = None

        for provider_name in self.provider_order:
            client = self._get_client(provider_name)
            if not client:
                continue

            try:
                response = await client.chat_completion(
                    messages=messages,
                    response_format=response_format,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response
            except Exception as e:
                last_error = e
                # Log and continue to next provider
                continue

        raise Exception(f"All LLM providers failed. Last error: {last_error}")

    async def synthesize_briefing(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Synthesize briefing using first available provider."""
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ]

        response = await self.chat_completion(
            messages=messages,
            response_format=response_format,
            temperature=0.3,
        )

        return response.content

    async def structure_briefing(
        self,
        briefing_data: Dict[str, Any],
        template: str,
    ) -> Dict[str, Any]:
        """Structure briefing data into sections using LLM."""
        system_prompt = """You are a senior financial analyst and macroeconomic researcher creating a morning intelligence briefing.
Your task is to synthesize raw market data, news, and economic indicators into a structured, professional briefing.
Follow the template structure exactly. Be concise, factual, and actionable.
Distinguish verified facts from interpretations. Flag missing or unreliable data.
Use professional financial terminology appropriate for a mortgage analyst.
Include specific numbers, timestamps, and sources where relevant."""

        user_prompt = f"""Raw briefing data:
{json.dumps(briefing_data, indent=2, default=str)}

Template structure:
{template}

Generate the briefing following the template exactly. Return as JSON with section keys matching the template."""

        response = await self.chat_completion(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"raw_response": response.content}

    async def translate_briefing(
        self,
        briefing: Dict[str, Any],
        target_language: str,
    ) -> Dict[str, Any]:
        """Translate briefing to target language."""
        system_prompt = f"""You are a professional financial translator. Translate the briefing to {target_language}.
Preserve all numbers, symbols, currency codes, percentages, and technical terms.
Keep the structure identical. Only translate natural language text."""

        user_prompt = f"Translate this briefing to {target_language}:\n{json.dumps(briefing, ensure_ascii=False, default=str)}"

        response = await self.chat_completion(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt),
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return briefing


# Global instance
llm_client = MultiLLMClient()