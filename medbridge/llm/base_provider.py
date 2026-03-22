"""
Base LLM Provider

Abstract base class for LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class LLMResponse(BaseModel):
    """Response from an LLM generation call."""
    
    text: str = Field(description="Generated text")
    model: str = Field(description="Model used")
    tokens_used: Optional[int] = Field(default=None, description="Total tokens consumed")
    prompt_tokens: Optional[int] = Field(default=None, description="Prompt tokens")
    completion_tokens: Optional[int] = Field(default=None, description="Completion tokens")
    latency_ms: float = Field(description="Generation latency in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Structured output (if JSON mode used)
    structured_output: Optional[Dict[str, Any]] = Field(default=None, description="Parsed JSON output")
    
    # Native tool calls
    tool_calls: Optional[List[Dict[str, Any]]] = Field(default=None, description="Native tool calls requested by the LLM")


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM providers (Ollama, OpenAI-compatible, etc.) must implement this interface.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
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
        Generate text or tool calls.
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"