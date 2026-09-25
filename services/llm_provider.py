"""
services/llm_provider.py
LLM provider abstraction supporting multiple backends.
Uses the OpenAI Python client with configurable base URLs.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Optional, Protocol, Type, TypeVar

from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from config.settings import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProviderProtocol(Protocol):
    """Protocol interface that all LLM provider implementations must satisfy."""

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Type[T],
        *,
        temperature: float,
        max_tokens: int,
    ) -> T:
        ...


# ── Mock provider ─────────────────────────────────────────────────────────────

class MockLLMProvider:
    """
    Offline mock provider for tests and demonstrations.
    Returns plausible structured output without API calls.
    """

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Type[T],
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> T:
        """Generate a mock response matching the response_model schema."""
        logger.info("MockLLMProvider: generating structured mock response")
        schema = response_model.model_json_schema()
        mock_data = self._build_mock_data(schema, response_model)
        return response_model.model_validate(mock_data)

    def _build_mock_data(self, schema: dict, model: Type[BaseModel]) -> dict:
        """Build minimal valid mock data matching a Pydantic model."""
        from models.question import GeneratedQuestion
        from models.valuation import ValuationPoint

        if model.__name__ == "GeneratedQuestion":
            return {
                "question_text": (
                    "Explain the key components of a Generative Adversarial Network "
                    "(GAN) and describe how the generator and discriminator interact "
                    "during the training process. [MOCK QUESTION — NOT FOR REAL USE]"
                ),
                "unit_number": 1,
                "chapter_number": 1,
                "chapter_name": "Introduction to Generative AI",
                "bloom_level": "L2",
                "marks": 10,
                "question_type": "descriptive",
                "difficulty": "medium",
                "model_answer": (
                    "A Generative Adversarial Network consists of two neural networks: "
                    "the generator G and the discriminator D. The generator creates "
                    "synthetic samples while the discriminator attempts to distinguish "
                    "real samples from generated ones. Training is an adversarial game "
                    "where G minimizes and D maximizes a value function. [MOCK ANSWER]"
                ),
                "valuation_points": [
                    {"criterion": "Definition of GAN architecture", "marks": 2},
                    {"criterion": "Role of generator network", "marks": 2},
                    {"criterion": "Role of discriminator network", "marks": 2},
                    {"criterion": "Adversarial training mechanism", "marks": 2},
                    {"criterion": "Convergence and Nash equilibrium", "marks": 2},
                ],
                "bloom_justification": (
                    "This question requires understanding (L2) the components and "
                    "interaction mechanism of GAN architecture, not mere recall."
                ),
                "syllabus_grounding": [
                    "GAN fundamentals",
                    "Generator-Discriminator architecture",
                    "Adversarial training",
                ],
                "source": "AI_GENERATED",
                "approval_status": "PENDING",
            }

        # Valuation scheme fallback (matches ValuationDraft inside valuation_agent)
        props = schema.get("properties", {})
        if "expected_answer" in props and "valuation_points" in props:
            return {
                "expected_answer": "[MOCK MODEL ANSWER — Replace with faculty-approved answer]",
                "key_points": [
                    "Key concept 1 explanation",
                    "Key concept 2 with examples",
                    "Application to course context",
                ],
                "valuation_points": [
                    {"criterion": "Conceptual accuracy", "marks": 3},
                    {"criterion": "Technical depth and terminology", "marks": 3},
                    {"criterion": "Illustration with examples", "marks": 2},
                    {"criterion": "Clarity and structure", "marks": 2},
                ],
                "alternative_answers": [],
            }

        # Generic schema-driven fallback
        return self._build_generic_mock(schema)

    def _build_generic_mock(self, schema: dict) -> dict:
        """Build minimal mock data from JSON schema."""
        mock: dict = {}
        props = schema.get("properties", {})
        required = schema.get("required", list(props.keys()))
        for field_name in required:
            field_schema = props.get(field_name, {})
            field_type = field_schema.get("type", "string")
            if field_type == "string":
                mock[field_name] = f"[MOCK {field_name}]"
            elif field_type == "integer":
                mock[field_name] = 1
            elif field_type == "number":
                mock[field_name] = 1.0
            elif field_type == "boolean":
                mock[field_name] = True
            elif field_type == "array":
                mock[field_name] = []
            elif field_type == "object":
                mock[field_name] = {}
        return mock



# ── OpenAI-compatible provider ────────────────────────────────────────────────

class OpenAICompatibleProvider:
    """
    Provider using the OpenAI Python client with a configurable base URL.
    Supports Groq, OpenRouter, NVIDIA NIM, and any OpenAI-compatible API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 120,
        max_retries: int = 3,
        log_prompt_content: bool = False,
    ):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package required") from exc

        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )
        self._model = model
        self._max_retries = max_retries
        self._log_prompts = log_prompt_content

    def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Type[T],
        *,
        temperature: float = 0.4,
        max_tokens: int = 4096,
    ) -> T:
        request_id = str(uuid.uuid4())[:8]
        logger.info(f"[{request_id}] LLM request model={self._model}")
        if self._log_prompts:
            logger.debug(f"[{request_id}] Messages: {messages}")

        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system_suffix = (
            f"\n\nYou MUST respond ONLY with valid JSON that matches this schema:\n"
            f"```json\n{schema_json}\n```\n"
            f"Do not include any text outside the JSON object."
        )

        augmented_messages = list(messages)
        # Augment last system message or add one
        if augmented_messages and augmented_messages[0]["role"] == "system":
            augmented_messages[0] = {
                "role": "system",
                "content": augmented_messages[0]["content"] + system_suffix,
            }
        else:
            augmented_messages.insert(0, {
                "role": "system",
                "content": "You are a precise JSON generation assistant." + system_suffix,
            })

        last_error: Optional[Exception] = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=augmented_messages,  # type: ignore
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response from LLM")

                logger.info(
                    f"[{request_id}] Tokens used: "
                    f"prompt={response.usage.prompt_tokens if response.usage else '?'} "
                    f"completion={response.usage.completion_tokens if response.usage else '?'}"
                )

                extracted_str = self._extract_json(content)
                try:
                    raw = json.loads(extracted_str)
                except Exception as json_err:
                    json_err.raw_response = content
                    raise json_err

                try:
                    validated = response_model.model_validate(raw)
                    return validated
                except Exception as val_err:
                    val_err.raw_response = content
                    val_err.raw_json = raw
                    raise val_err

            except Exception as exc:
                last_error = exc
                raw_resp = getattr(exc, "raw_response", content if "content" in locals() else "N/A")
                logger.warning(
                    f"[{request_id}] Attempt {attempt + 1}/{self._max_retries} failed: {exc}\n"
                    f"Raw content:\n{raw_resp}"
                )
                if attempt < self._max_retries - 1:
                    wait_secs = 2 ** attempt
                    time.sleep(wait_secs)
                    # Add validation error feedback
                    augmented_messages.append({
                        "role": "user",
                        "content": (
                            f"Your previous response was invalid: {exc}. "
                            f"Please try again with a valid JSON response matching the schema."
                        ),
                    })

        err = RuntimeError(
            f"LLM failed after {self._max_retries} attempts: {last_error}"
        )
        if hasattr(last_error, "raw_response"):
            err.raw_response = getattr(last_error, "raw_response")
        if hasattr(last_error, "raw_json"):
            err.raw_json = getattr(last_error, "raw_json")
        err.__cause__ = last_error
        raise err

    @staticmethod
    def _extract_json(content: str) -> str:
        """
        Strip markdown code fences from LLM output.
        Handles patterns like:
          ```json\n{...}\n```
          ```\n{...}\n```
        Returns the raw JSON string.
        """
        content = content.strip()
        # Match ```json ... ``` or ``` ... ```
        import re
        fence_match = re.search(
            r"```(?:json)?\s*\n?([\s\S]*?)\n?```", content, re.IGNORECASE
        )
        if fence_match:
            return fence_match.group(1).strip()
        # Try to find first { or [ and last } or ]
        start = min(
            (content.find("{") if "{" in content else len(content)),
            (content.find("[") if "[" in content else len(content)),
        )
        end = max(
            (content.rfind("}") + 1 if "}" in content else 0),
            (content.rfind("]") + 1 if "]" in content else 0),
        )
        if start < end:
            return content[start:end]
        return content


# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm_provider() -> LLMProviderProtocol:
    """
    Factory function returning the configured LLM provider.
    Uses dependency injection pattern: call this once and pass the result.
    """
    settings = get_settings()

    if settings.is_mock_mode:
        logger.info("Using MockLLMProvider (mock mode active)")
        return MockLLMProvider()

    api_key = settings.resolved_llm_api_key
    if not api_key:
        raise RuntimeError(
            "No LLM API key found. Set LLM_API_KEY or GROQ_API_KEY in .env, "
            "or set USE_MOCK_LLM=true for offline mode."
        )

    return OpenAICompatibleProvider(
        api_key=api_key,
        base_url=settings.resolved_llm_base_url,
        model=settings.resolved_llm_model,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        log_prompt_content=settings.log_prompt_content,
    )


# Alias for protocol compliance
LLMProvider = LLMProviderProtocol
