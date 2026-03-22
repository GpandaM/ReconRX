"""
Ollama LLM Provider
"""

import logging
import time
import json
from typing import Optional, List, Dict, Any
import requests

from medbridge.config import get_settings
from medbridge.llm.base_provider import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)
settings = get_settings()

class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None
    ):
        super().__init__(name="ollama")
        self.base_url = (base_url or settings.ollama_base_url).rstrip('/')
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        
        logger.info(f"Initialized Ollama provider: {self.base_url}, model={self.model}")
    
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
        start_time = time.time()
        
        # Build messages if not explicitly provided
        if not messages:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            if prompt:
                messages.append({"role": "user", "content": prompt})
        
        # Build request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {}
        }
        
        if tools:
            payload["tools"] = tools
            
        if temperature is not None:
            payload["options"]["temperature"] = temperature
        elif settings.llm_temperature is not None:
            payload["options"]["temperature"] = settings.llm_temperature
            
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        elif settings.llm_max_tokens is not None:
            payload["options"]["num_predict"] = settings.llm_max_tokens
            
        if top_p is not None:
            payload["options"]["top_p"] = top_p
        elif settings.llm_top_p is not None:
            payload["options"]["top_p"] = settings.llm_top_p
            
        if stop_sequences:
            payload["options"]["stop"] = stop_sequences
            
        if json_mode:
            payload["format"] = "json"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            message_data = result.get("message", {})
            text = message_data.get("content", "")
            tool_calls = message_data.get("tool_calls", None)
            
            structured_output = None
            if json_mode and text:
                try:
                    structured_output = json.loads(text)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
            
            prompt_tokens = result.get("prompt_eval_count")
            completion_tokens = result.get("eval_count")
            tokens_used = (prompt_tokens or 0) + (completion_tokens or 0) if prompt_tokens else None
            
            return LLMResponse(
                text=text,
                model=result.get("model", self.model),
                tokens_used=tokens_used,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                structured_output=structured_output,
                tool_calls=tool_calls,
                metadata={"provider": "ollama", "base_url": self.base_url}
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            raise RuntimeError(f"Ollama generation failed: {e}")

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
