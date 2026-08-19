"""LLM provider abstraction.

All LLM interaction is routed through this module so that
business logic never imports provider-specific code.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from ripplegraph.config import Settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Generate text from a system + user prompt pair."""
        ...

    def extract_memories(self, segment_text: str, session_id: str) -> list[dict[str, Any]]:
        """Extract durable memories from a conversation segment."""
        system = (
            "You are a memory extraction engine. Extract durable memories from the "
            "conversation below. For each memory, return a JSON array of objects with:\n"
            "- type: one of FACT, EVENT, DECISION, PREFERENCE, EPISODE_SUMMARY\n"
            "- subject: who/what the memory is about\n"
            "- predicate: the relationship or attribute\n"
            "- object: the value (if applicable, else null)\n"
            "- text: a clear, standalone statement of the memory\n"
            "- importance: float 0.0-1.0 (how durable/important is this?)\n\n"
            "Rules:\n"
            "- Skip greetings, filler, and low-value utterances\n"
            "- Each memory should be self-contained\n"
            "- Return ONLY valid JSON array, no markdown fences"
        )
        user = f"Session: {session_id}\n\nConversation:\n{segment_text}"
        raw = self.generate(system, user)
        return self._parse_json_array(raw)

    def classify_query(self, query: str) -> dict[str, Any]:
        """Classify a query's temporal intent and extract entities."""
        system = (
            "You are a query classifier. Analyze the query and return a JSON object with:\n"
            "- entities: list of key entities mentioned\n"
            "- intent: what the user wants to know (brief)\n"
            "- temporal_mode: one of CURRENT, HISTORICAL, TRANSITION, TIMELINE, NONE\n"
            "- relevant_time: specific time reference if mentioned, else null\n\n"
            "Return ONLY valid JSON, no markdown fences."
        )
        raw = self.generate(system, f"Query: {query}")
        result = self._parse_json_object(raw)
        return result

    def verify_supersession(
        self, old_text: str, new_text: str, subject: str, predicate: str
    ) -> bool:
        """Verify whether a new memory genuinely supersedes an old one."""
        system = (
            "You are a fact-checking engine. Determine if the NEW memory supersedes "
            "the OLD memory for the same subject and predicate.\n"
            "Return ONLY a JSON object: {\"supersedes\": true/false, \"reason\": \"...\"}"
        )
        user = (
            f"Subject: {subject}\nPredicate: {predicate}\n"
            f"OLD: {old_text}\nNEW: {new_text}"
        )
        raw = self.generate(system, user)
        result = self._parse_json_object(raw)
        return result.get("supersedes", False)

    def generate_answer(self, evidence_text: str, query: str) -> str:
        """Generate a final answer from the evidence ledger."""
        system = (
            "Answer exclusively from the supplied memory evidence. "
            "Do not use outside knowledge. Do not introduce claims "
            "unsupported by the evidence. Preserve uncertainty where necessary. "
            "If evidence is conflicting, acknowledge the conflict."
        )
        user = f"Evidence:\n{evidence_text}\n\nQuestion: {query}"
        return self.generate(system, user)

    def _parse_json_array(self, raw: str) -> list[dict[str, Any]]:
        """Parse an LLM response as a JSON array."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
            return [result]
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON array: %s", cleaned[:200])
            return []

    def _parse_json_object(self, raw: str) -> dict[str, Any]:
        """Parse an LLM response as a JSON object."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        try:
            result = json.loads(cleaned)
            if isinstance(result, dict):
                return result
            return {}
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON object: %s", cleaned[:200])
            return {}


class GeminiLLMClient(LLMClient):
    """Google Gemini implementation."""

    def __init__(self, api_key: str) -> None:
        from google import genai
        self._client = genai.Client(api_key=api_key)
        self._model = "gemini-3.6-flash"

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30), reraise=True)
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config={"system_instruction": system_prompt, "temperature": 0.1},
        )
        return response.text or ""


class GroqLLMClient(LLMClient):
    """Groq implementation."""

    def __init__(self, api_key: str) -> None:
        from groq import Groq
        self._client = Groq(api_key=api_key)
        self._model = "llama-3.3-70b-versatile"

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30), reraise=True)
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


class MistralLLMClient(LLMClient):
    """Mistral implementation."""

    def __init__(self, api_key: str) -> None:
        from mistralai import Mistral
        self._client = Mistral(api_key=api_key)
        self._model = "mistral-small-latest"

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30), reraise=True)
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.complete(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


class CerebrasLLMClient(LLMClient):
    """Cerebras implementation."""

    def __init__(self, api_key: str) -> None:
        from cerebras.cloud.sdk import Cerebras
        self._client = Cerebras(api_key=api_key)
        self._model = "llama-3.3-70b"

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30), reraise=True)
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""


def create_llm_client(settings: Settings) -> LLMClient:
    """Factory: create the correct LLM client based on config."""
    provider = settings.llm_provider.lower()
    if provider == "gemini" and settings.google_api_key:
        return GeminiLLMClient(settings.google_api_key)
    elif provider == "groq" and settings.groq_api_key:
        return GroqLLMClient(settings.groq_api_key)
    elif provider == "mistral" and settings.mistral_api_key:
        return MistralLLMClient(settings.mistral_api_key)
    elif provider == "cerebras" and settings.cerebras_api_key:
        return CerebrasLLMClient(settings.cerebras_api_key)
    else:
        # Try fallback order
        if settings.google_api_key:
            return GeminiLLMClient(settings.google_api_key)
        if settings.groq_api_key:
            return GroqLLMClient(settings.groq_api_key)
        if settings.mistral_api_key:
            return MistralLLMClient(settings.mistral_api_key)
        if settings.cerebras_api_key:
            return CerebrasLLMClient(settings.cerebras_api_key)
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            "Set at least one of: GOOGLE_API_KEY, GROQ_API_KEY, MISTRAL_API_KEY, CEREBRAS_API_KEY"
        )
