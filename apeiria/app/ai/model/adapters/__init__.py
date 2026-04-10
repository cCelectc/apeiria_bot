"""Model adapters exported from the consolidated model boundary."""

from .anthropic_compatible import AnthropicCompatibleProvider
from .openai_compatible import OpenAICompatibleProvider

__all__ = ["AnthropicCompatibleProvider", "OpenAICompatibleProvider"]
