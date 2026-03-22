"""
MedBridge LLM Module

LLM provider abstraction with routing and fallback support.
"""

from medbridge.llm.base_provider import LLMProvider, LLMResponse
from medbridge.llm.router import get_llm_router, LLMRouter

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "LLMRouter",
    "get_llm_router",
]
