"""
Base Agent

Abstract base class for all agents.
"""

import logging
from abc import ABC
from pathlib import Path
from typing import Optional

from medbridge.config import get_settings
from medbridge.llm.router import get_llm_router, LLMRouter

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Provides common functionality:
    - LLM access via router
    - Prompt loading
    - Logging
    """
    
    def __init__(self, name: str, llm_router: Optional[LLMRouter] = None):
        """
        Initialize base agent.
        
        Args:
            name: Agent name
            llm_router: LLM router instance (defaults to global router)
        """
        self.name = name
        self.llm = llm_router or get_llm_router()
        self.logger = logging.getLogger(f"medbridge.agents.{name}")
        
        self.logger.info(f"Initialized {self.__class__.__name__}")
    
    def load_prompt(self, prompt_file: str, **kwargs) -> str:
        """
        Load and format a prompt template.
        
        Args:
            prompt_file: Prompt filename (e.g., "extraction.txt")
            **kwargs: Variables to substitute in the prompt
            
        Returns:
            str: Formatted prompt
        """
        prompt_path = Path("prompts") / prompt_file
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        
        template = prompt_path.read_text()
        
        # Simple string formatting
        try:
            formatted = template.format(**kwargs)
            return formatted
        except KeyError as e:
            raise ValueError(f"Missing prompt variable: {e}")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
