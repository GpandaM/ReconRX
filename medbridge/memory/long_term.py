"""
Long-Term Memory

Redis-based persistent storage for patient state (90-day TTL).
Stores medication lists, discrepancies, and patient context.
"""

import logging
import json
from typing import Optional, List, Dict, Any
import redis

from medbridge.config import get_settings
from medbridge.memory.base_memory import MemoryStore
from medbridge.models.medication import CanonicalMedication

logger = logging.getLogger(__name__)
settings = get_settings()


class LongTermMemory(MemoryStore):
    """
    Long-Term Memory using Redis.
    
    Stores:
    - List A (discharge medications)
    - List B (pharmacy medications)
    - List C (self-reported medications)
    - Discrepancies
    - Patient context
    
    TTL: 90 days (configurable)
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize long-term memory.
        
        Args:
            redis_client: Redis client (optional, creates new if not provided)
        """
        super().__init__(name="long_term")
        
        if redis_client:
            self.redis = redis_client
        else:
            self.redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=settings.redis_decode_responses
            )
        
        self.ttl = settings.redis_ttl_long_term
        
        logger.info(f"Initialized LongTermMemory with TTL={self.ttl}s")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        try:
            value = self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value by key with TTL."""
        try:
            ttl = ttl or self.ttl
            serialized = json.dumps(value, default=str)
            self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key."""
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking key {key}: {e}")
            return False
    
    # Patient medication lists
    
    def store_discharge_meds(
        self,
        patient_id: str,
        medications: List[CanonicalMedication]
    ) -> bool:
        """
        Store List A (discharge medications).
        
        Args:
            patient_id: Patient subject ID
            medications: List of medications
            
        Returns:
            bool: True if successful
        """
        key = f"patient:{patient_id}:discharge_meds"
        
        # Convert to dict for JSON serialization
        meds_dict = [med.model_dump() for med in medications]
        
        success = self.set(key, meds_dict)
        
        if success:
            logger.info(
                f"[LongTermMemory] Stored List A for patient {patient_id}: "
                f"{len(medications)} medications"
            )
        
        return success
    
    def get_discharge_meds(self, patient_id: str) -> List[CanonicalMedication]:
        """
        Get List A (discharge medications).
        
        Args:
            patient_id: Patient subject ID
            
        Returns:
            List[CanonicalMedication]: Discharge medications
        """
        key = f"patient:{patient_id}:discharge_meds"
        data = self.get(key)
        
        if not data:
            return []
        
        medications = [CanonicalMedication(**med) for med in data]
        logger.info(
            f"[LongTermMemory] Retrieved List A for patient {patient_id}: "
            f"{len(medications)} medications"
        )
        
        return medications
    
    def store_pharmacy_meds(
        self,
        patient_id: str,
        medications: List[CanonicalMedication]
    ) -> bool:
        """
        Store List B (pharmacy medications).
        
        Args:
            patient_id: Patient subject ID
            medications: List of medications
            
        Returns:
            bool: True if successful
        """
        key = f"patient:{patient_id}:pharmacy_meds"
        meds_dict = [med.model_dump() for med in medications]
        
        success = self.set(key, meds_dict)
        
        if success:
            logger.info(
                f"[LongTermMemory] Stored List B for patient {patient_id}: "
                f"{len(medications)} medications"
            )
        
        return success
    
    def get_pharmacy_meds(self, patient_id: str) -> List[CanonicalMedication]:
        """
        Get List B (pharmacy medications).
        
        Args:
            patient_id: Patient subject ID
            
        Returns:
            List[CanonicalMedication]: Pharmacy medications
        """
        key = f"patient:{patient_id}:pharmacy_meds"
        data = self.get(key)
        
        if not data:
            return []
        
        medications = [CanonicalMedication(**med) for med in data]
        logger.info(
            f"[LongTermMemory] Retrieved List B for patient {patient_id}: "
            f"{len(medications)} medications"
        )
        
        return medications
    
    def store_reported_meds(
        self,
        patient_id: str,
        medications: List[CanonicalMedication]
    ) -> bool:
        """
        Store List C (self-reported medications).
        
        Args:
            patient_id: Patient subject ID
            medications: List of medications
            
        Returns:
            bool: True if successful
        """
        key = f"patient:{patient_id}:reported_meds"
        meds_dict = [med.model_dump() for med in medications]
        
        success = self.set(key, meds_dict)
        
        if success:
            logger.info(
                f"[LongTermMemory] Stored List C for patient {patient_id}: "
                f"{len(medications)} medications"
            )
        
        return success
    
    def get_reported_meds(self, patient_id: str) -> List[CanonicalMedication]:
        """
        Get List C (self-reported medications).
        
        Args:
            patient_id: Patient subject ID
            
        Returns:
            List[CanonicalMedication]: Self-reported medications
        """
        key = f"patient:{patient_id}:reported_meds"
        data = self.get(key)
        
        if not data:
            return []
        
        medications = [CanonicalMedication(**med) for med in data]
        logger.info(
            f"[LongTermMemory] Retrieved List C for patient {patient_id}: "
            f"{len(medications)} medications"
        )
        
        return medications
    
    def store_discrepancies(
        self,
        patient_id: str,
        discrepancies: List[Dict[str, Any]]
    ) -> bool:
        """
        Store discrepancies for a patient.
        
        Args:
            patient_id: Patient subject ID
            discrepancies: List of discrepancy dicts
            
        Returns:
            bool: True if successful
        """
        key = f"patient:{patient_id}:discrepancies"
        
        success = self.set(key, discrepancies)
        
        if success:
            logger.info(
                f"[LongTermMemory] Stored discrepancies for patient {patient_id}: "
                f"{len(discrepancies)} discrepancies"
            )
        
        return success
    
    def get_discrepancies(self, patient_id: str) -> List[Dict[str, Any]]:
        """
        Get discrepancies for a patient.
        
        Args:
            patient_id: Patient subject ID
            
        Returns:
            List[Dict]: Discrepancies
        """
        key = f"patient:{patient_id}:discrepancies"
        data = self.get(key)
        
        if not data:
            return []
        
        logger.info(
            f"[LongTermMemory] Retrieved discrepancies for patient {patient_id}: "
            f"{len(data)} discrepancies"
        )
        
        return data
    
    def health_check(self) -> bool:
        """Check if Redis is accessible."""
        try:
            self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global instance
_long_term_memory: Optional[LongTermMemory] = None


def get_long_term_memory() -> LongTermMemory:
    """
    Get the global long-term memory instance (singleton pattern).
    
    Returns:
        LongTermMemory: The global instance
    """
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory
