"""
LLM Router

Routes LLM requests to appropriate providers with fallback support.
"""

import logging
from typing import Optional, List, Dict, Any

from medbridge.config import get_settings
from medbridge.llm.base_provider import LLMProvider, LLMResponse
from medbridge.llm.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMRouter:
    """
    LLM Router with fallback chain.
    """
    
    def __init__(
        self,
        primary_provider: Optional[LLMProvider] = None,
        fallback_providers: Optional[List[LLMProvider]] = None
    ):
        self.primary_provider = primary_provider or self._create_default_provider()
        self.fallback_providers = fallback_providers or []
        
        logger.info(
            f"Initialized LLM router with primary={self.primary_provider.name}, "
            f"fallbacks={[p.name for p in self.fallback_providers]}"
        )
    
    def _create_default_provider(self) -> LLMProvider:
        provider_name = settings.llm_primary_provider
        
        if provider_name == "ollama":
            return OllamaProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {provider_name}")
    
    def generate(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        json_mode: bool = False,
        stop_sequences: Optional[List[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate text or tool calls using primary provider with fallback.
        """
        providers = [self.primary_provider] + self.fallback_providers
        last_error = None
        
        for provider in providers:
            try:
                logger.debug(f"Attempting generation with provider: {provider.name}")
                
                response = provider.generate(
                    prompt=prompt,
                    messages=messages,
                    tools=tools,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    json_mode=json_mode,
                    stop_sequences=stop_sequences,
                    **kwargs
                )
                
                logger.info(
                    f"Generation successful with {provider.name}: "
                    f"{response.tokens_used} tokens, {response.latency_ms:.0f}ms"
                )
                
                return response
                
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                last_error = e
                continue
        
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    def is_available(self) -> bool:
        return any(p.is_available() for p in [self.primary_provider] + self.fallback_providers)


# Global router instance
_router: Optional[LLMRouter] = None

def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
