"""Model adapters exported from the consolidated model boundary."""

from .anthropic_compatible import AnthropicCompatibleProvider
from .fastembed_adapter import FastEmbedProvider
from .gemini_native import GeminiNativeProvider
from .openai_compatible import OpenAICompatibleProvider

__all__ = [
    "AnthropicCompatibleProvider",
    "FastEmbedProvider",
    "GeminiNativeProvider",
    "OpenAICompatibleProvider",
]
