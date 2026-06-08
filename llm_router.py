"""
Unified LLM Provider Router: Free Tier (Groq/HF) + Paid Tier (OpenAI/Anthropic)
Automatically rotates providers based on availability and rate limits.
Integrates with cost_tracker for token accounting.
"""

import os
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Import cost tracker (will be lazy-loaded to avoid circular imports)
cost_tracker = None


class LLMTier(Enum):
    FREE = "free"
    PAID = "paid"


@dataclass
class ProviderConfig:
    name: str
    tier: LLMTier
    api_key_env: str
    model_id: str
    supports_vision: bool
    max_tokens: int
    rate_limit: Optional[int] = None  # requests per minute


class UnifiedLLMRouter:
    """Routes requests to best available LLM across free and paid tiers."""

    FREE_PROVIDERS = [
        ProviderConfig(
            name="Groq (Llama 3.3 70B)",
            tier=LLMTier.FREE,
            api_key_env="GROQ_API_KEY",
            model_id="llama-3.3-70b-versatile",
            supports_vision=True,  # Via vision endpoint
            max_tokens=8192,
            rate_limit=None,  # Unlimited fair use
        ),
        ProviderConfig(
            name="HuggingFace Inference",
            tier=LLMTier.FREE,
            api_key_env="HUGGINGFACE_API_KEY",
            model_id="HuggingFaceH4/zephyr-7b-beta",
            supports_vision=False,
            max_tokens=2048,
            rate_limit=30,  # 30 req/min
        ),
    ]

    PAID_PROVIDERS = [
        ProviderConfig(
            name="OpenAI GPT-4V",
            tier=LLMTier.PAID,
            api_key_env="OPENAI_API_KEY",
            model_id="gpt-4-vision-preview",
            supports_vision=True,
            max_tokens=4096,
            rate_limit=500,
        ),
        ProviderConfig(
            name="Anthropic Claude 3.5",
            tier=LLMTier.PAID,
            api_key_env="ANTHROPIC_API_KEY",
            model_id="claude-3-5-sonnet-20241022",
            supports_vision=True,
            max_tokens=4096,
            rate_limit=10000,
        ),
        ProviderConfig(
            name="Together AI",
            tier=LLMTier.PAID,
            api_key_env="TOGETHER_API_KEY",
            model_id="meta-llama/Llama-2-70b-chat-hf",
            supports_vision=False,
            max_tokens=2048,
            rate_limit=100,
        ),
    ]

    def __init__(self, prefer_tier: LLMTier = LLMTier.FREE):
        self.prefer_tier = prefer_tier
        self.available_providers = self._validate_keys()
        self.current_idx = 0
        self.provider_stats = {}
        self.current_task_id = None  # Track current task for cost recording

        logger.info(f"LLM Router initialized with {len(self.available_providers)} providers")
        for p in self.available_providers:
            logger.info(f"  ✅ {p.name} (Vision: {p.supports_vision})")

    def _get_cost_tracker(self):
        """Lazy-load cost tracker to avoid circular imports."""
        global cost_tracker
        if cost_tracker is None:
            try:
                from cost_tracker import cost_tracker as ct
                cost_tracker = ct
            except ImportError:
                logger.debug("Cost tracker not available")
        return cost_tracker

    def _validate_keys(self) -> list:
        """Check which providers have API keys configured."""
        available = []

        # Prefer tier first
        if self.prefer_tier == LLMTier.FREE:
            providers = self.FREE_PROVIDERS + self.PAID_PROVIDERS
        else:
            providers = self.PAID_PROVIDERS + self.FREE_PROVIDERS

        for provider in providers:
            if os.getenv(provider.api_key_env):
                available.append(provider)
                logger.debug(f"✅ {provider.name}: API key found")
            else:
                logger.debug(f"⚠️  {provider.name}: No API key")

        return available

    def refresh_providers(self):
        """Refresh available providers by re-validating API keys."""
        self.available_providers = self._validate_keys()
        logger.info(f"🔄 Providers refreshed: {len(self.available_providers)} available")
        for p in self.available_providers:
            logger.info(f"  ✅ {p.name} (Vision: {p.supports_vision})")

    def get_provider(self, vision_required: bool = False) -> Optional[ProviderConfig]:
        """Get next available provider, with vision support if required."""
        if not self.available_providers:
            logger.error("❌ No LLM providers available!")
            return None

        # Filter by vision requirement
        candidates = (
            self.available_providers
            if not vision_required
            else [p for p in self.available_providers if p.supports_vision]
        )

        if not candidates:
            logger.warning(f"No vision-capable providers available, using text-only")
            candidates = self.available_providers

        provider = candidates[self.current_idx % len(candidates)]
        self.current_idx += 1

        logger.debug(f"📡 Selected provider: {provider.name}")
        return provider

    def create_client(self, provider: ProviderConfig):
        """Create API client for the selected provider."""
        api_key = os.getenv(provider.api_key_env)

        if provider.name.startswith("Groq"):
            from groq import Groq
            return Groq(api_key=api_key)

        elif provider.name.startswith("OpenAI"):
            from openai import OpenAI
            return OpenAI(api_key=api_key)

        elif provider.name.startswith("Anthropic"):
            from anthropic import Anthropic
            return Anthropic(api_key=api_key)

        elif provider.name.startswith("HuggingFace"):
            import requests
            return requests.Session()  # Raw HTTP client for HF

        elif provider.name.startswith("Together"):
            import together
            together.api_key = api_key
            return together

        else:
            raise ValueError(f"Unknown provider: {provider.name}")

    def route_completion(
        self,
        prompt: str,
        system_prompt: str = "",
        vision_data: Optional[bytes] = None,
        max_tokens: int = 1024,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Route a completion request to best available provider.

        Args:
            prompt: User message
            system_prompt: System context
            vision_data: Optional screenshot bytes (base64)
            max_tokens: Max response length
            task_id: Task ID for cost tracking

        Returns:
            {
                "response": str,
                "provider": str,
                "tokens_used": int,
                "cost": float,
                "tokens_input": int,
                "tokens_output": int
            }
        """
        vision_required = vision_data is not None
        provider = self.get_provider(vision_required=vision_required)

        if not provider:
            raise RuntimeError("No LLM providers available")

        self.current_task_id = task_id

        try:
            if provider.name.startswith("Groq"):
                return self._groq_completion(
                    provider, prompt, system_prompt, vision_data, max_tokens, task_id
                )
            elif provider.name.startswith("OpenAI"):
                return self._openai_completion(
                    provider, prompt, system_prompt, vision_data, max_tokens, task_id
                )
            elif provider.name.startswith("Anthropic"):
                return self._anthropic_completion(
                    provider, prompt, system_prompt, vision_data, max_tokens, task_id
                )
            elif provider.name.startswith("HuggingFace"):
                return self._huggingface_completion(
                    provider, prompt, system_prompt, max_tokens, task_id
                )
            else:
                raise ValueError(f"Provider not implemented: {provider.name}")

        except Exception as e:
            logger.error(f"❌ {provider.name} failed: {str(e)[:100]}")
            # Try next provider
            return self.route_completion(prompt, system_prompt, vision_data, max_tokens, task_id)

    def _groq_completion(self, provider, prompt, system_prompt, vision_data, max_tokens, task_id):
        """Groq API completion."""
        from groq import Groq

        client = self._create_groq_client(provider)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if vision_data:
            import base64

            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64.b64encode(vision_data).decode()}"
                            },
                        },
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=provider.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        tokens_input = response.usage.prompt_tokens
        tokens_output = response.usage.completion_tokens

        # Record cost
        tracker = self._get_cost_tracker()
        if tracker and task_id:
            tracker.record_inference(
                task_id=task_id,
                provider=provider.name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                model=provider.model_id,
            )

        return {
            "response": response.choices[0].message.content,
            "provider": provider.name,
            "tokens_used": response.usage.total_tokens,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost": 0.0,  # Groq is free
        }

    def _openai_completion(self, provider, prompt, system_prompt, vision_data, max_tokens, task_id):
        """OpenAI GPT-4V completion."""
        from openai import OpenAI

        client = self._create_openai_client(provider)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if vision_data:
            import base64

            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64.b64encode(vision_data).decode()}"
                            },
                        },
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=provider.model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )

        tokens_input = response.usage.prompt_tokens
        tokens_output = response.usage.completion_tokens

        # Record cost
        tracker = self._get_cost_tracker()
        if tracker and task_id:
            tracker.record_inference(
                task_id=task_id,
                provider=provider.name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                model=provider.model_id,
            )

        return {
            "response": response.choices[0].message.content,
            "provider": provider.name,
            "tokens_used": response.usage.total_tokens,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost": 0.01,  # Approximate
        }

    def _anthropic_completion(
        self, provider, prompt, system_prompt, vision_data, max_tokens, task_id
    ):
        """Anthropic Claude completion."""
        from anthropic import Anthropic

        client = self._create_anthropic_client(provider)

        messages = []

        if vision_data:
            import base64

            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": base64.b64encode(vision_data).decode(),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            )
        else:
            messages.append({"role": "user", "content": prompt})

        response = client.messages.create(
            model=provider.model_id,
            max_tokens=max_tokens,
            system=system_prompt or "",
            messages=messages,
        )

        tokens_input = response.usage.input_tokens
        tokens_output = response.usage.output_tokens

        # Record cost
        tracker = self._get_cost_tracker()
        if tracker and task_id:
            tracker.record_inference(
                task_id=task_id,
                provider=provider.name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                model=provider.model_id,
            )

        return {
            "response": response.content[0].text,
            "provider": provider.name,
            "tokens_used": tokens_input + tokens_output,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost": 0.01,
        }

    def _huggingface_completion(self, provider, prompt, system_prompt, max_tokens, task_id):
        """HuggingFace Inference API completion."""
        import requests

        api_key = os.getenv(provider.api_key_env)
        headers = {"Authorization": f"Bearer {api_key}"}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = requests.post(
            f"https://api-inference.huggingface.co/models/{provider.model_id}",
            headers=headers,
            json={"inputs": prompt, "parameters": {"max_length": max_tokens}},
        )

        # HuggingFace doesn't return token counts, estimate them
        tokens_output = len(response.json()[0]["generated_text"].split())
        tokens_input = len(prompt.split())

        # Record cost (HuggingFace free tier)
        tracker = self._get_cost_tracker()
        if tracker and task_id:
            tracker.record_inference(
                task_id=task_id,
                provider=provider.name,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                model=provider.model_id,
            )

        return {
            "response": response.json()[0]["generated_text"],
            "provider": provider.name,
            "tokens_used": tokens_input + tokens_output,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "cost": 0.0,
        }

    def _create_groq_client(self, provider):
        api_key = os.getenv(provider.api_key_env)
        from groq import Groq

        return Groq(api_key=api_key)

    def _create_openai_client(self, provider):
        api_key = os.getenv(provider.api_key_env)
        from openai import OpenAI

        return OpenAI(api_key=api_key)

    def _create_anthropic_client(self, provider):
        api_key = os.getenv(provider.api_key_env)
        from anthropic import Anthropic

        return Anthropic(api_key=api_key)

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "available_providers": len(self.available_providers),
            "prefer_tier": self.prefer_tier.value,
            "providers": [
                {
                    "name": p.name,
                    "tier": p.tier.value,
                    "vision_capable": p.supports_vision,
                }
                for p in self.available_providers
            ],
        }
