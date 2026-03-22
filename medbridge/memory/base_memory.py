"""
Base Memory Store

Abstract base class for memory implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Any

logger = logging.getLogger(__name__)


class MemoryStore(ABC):
    """
    Abstract base class for memory storage.
    
    Provides interface for key-value storage with TTL support.
    Implementations: LongTermMemory (Redis), ShortTermMemory (in-memory cache).
    """
    
    def __init__(self, name: str):
        """
        Initialize memory store.
        
        Args:
            name: Name of the memory store (for logging)
        """
        self.name = name
        self.logger = logging.getLogger(f"medbridge.memory.{name}")
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get value by key.
        
        Args:
            key: Storage key
            
        Returns:
            Optional[Any]: Value if exists, None otherwise
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value by key with optional TTL.
        
        Args:
            key: Storage key
            value: Value to store
            ttl: Time-to-live in seconds (optional)
            
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete key.
        
        Args:
            key: Storage key
            
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        Check if key exists.
        
        Args:
            key: Storage key
            
        Returns:
            bool: True if key exists
        """
        pass
    
    def clear(self) -> bool:
        """
        Clear all data (optional, not all stores may support this).
        
        Returns:
            bool: True if successful
        """
        self.logger.warning(f"clear() not implemented for {self.name}")
        return False
