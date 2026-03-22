"""
Agent State Models

Models for tracking agent execution, run context, sessions, and messages.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Status of an agent run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RunContext(BaseModel):
    """
    Run context injected into every agent invocation.
    
    Provides full traceability for agent execution with hierarchical tracking.
    """
    
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique run identifier")
    thread_id: str = Field(description="Thread ID grouping all runs in one pipeline execution")
    parent_run_id: Optional[str] = Field(default=None, description="Parent run ID (for child agent runs)")
    agent_name: str = Field(description="Agent name: supervisor, extraction, reconciliation, clinical, chat")
    
    patient_id: str = Field(description="Patient subject ID")
    session_id: Optional[str] = Field(default=None, description="Session ID (only for chat interactions)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Run creation timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")
    
    # Runtime fields (updated during execution)
    status: RunStatus = Field(default=RunStatus.PENDING, description="Current run status")
    completed_at: Optional[datetime] = Field(default=None, description="Run completion timestamp")
    latency_ms: Optional[float] = Field(default=None, description="Total latency in milliseconds")
    tokens_used: Optional[int] = Field(default=None, description="Total tokens consumed")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    
    class Config:
        use_enum_values = True
    
    def mark_running(self):
        """Mark run as running."""
        import logging
        logger = logging.getLogger(f"medbridge.run_context.{self.agent_name}")
        
        self.status = RunStatus.RUNNING
        logger.info(
            f"[RunContext] {self.agent_name} RUNNING | "
            f"run_id={self.run_id[:8]}... | thread_id={self.thread_id} | "
            f"patient_id={self.patient_id}"
        )
    
    def mark_completed(self, latency_ms: Optional[float] = None, tokens_used: Optional[int] = None):
        """Mark run as completed."""
        import logging
        logger = logging.getLogger(f"medbridge.run_context.{self.agent_name}")
        
        self.status = RunStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if latency_ms is not None:
            self.latency_ms = latency_ms
        if tokens_used is not None:
            self.tokens_used = tokens_used
        
        logger.info(
            f"[RunContext] {self.agent_name} COMPLETED | "
            f"run_id={self.run_id[:8]}... | "
            f"latency={self.latency_ms:.0f}ms | "
            f"tokens={self.tokens_used or 0} | "
            f"parent_run_id={self.parent_run_id[:8] + '...' if self.parent_run_id else 'None'}"
        )
    
    def mark_failed(self, error: str):
        """Mark run as failed."""
        import logging
        logger = logging.getLogger(f"medbridge.run_context.{self.agent_name}")
        
        self.status = RunStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error = error
        
        logger.error(
            f"[RunContext] {self.agent_name} FAILED | "
            f"run_id={self.run_id[:8]}... | "
            f"error={error}"
        )


class AgentStep(BaseModel):
    """
    Single step in an agent execution.
    
    Used for logging and tracing agent actions.
    """
    
    step_number: int = Field(description="Step number in sequence")
    action: str = Field(description="Action taken (e.g., 'extract_section', 'llm_call', 'store_result')")
    input_data: Optional[Dict[str, Any]] = Field(default=None, description="Input data for this step")
    output_data: Optional[Dict[str, Any]] = Field(default=None, description="Output data from this step")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Step timestamp")
    latency_ms: Optional[float] = Field(default=None, description="Step latency in milliseconds")
    error: Optional[str] = Field(default=None, description="Error message if step failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "step_number": 1,
                "action": "extract_section",
                "input_data": {"section": "Discharge Medications"},
                "output_data": {"text": "1. Furosemide 40 mg PO DAILY\n2. Lisinopril 10 mg PO DAILY"},
                "timestamp": "2180-06-27T10:15:00",
                "latency_ms": 50.0
            }
        }


class SupervisorState(BaseModel):
    """
    State of the Supervisor orchestration.
    
    Tracks the overall pipeline execution across all agents.
    """
    
    thread_id: str = Field(description="Pipeline thread ID")
    patient_id: str = Field(description="Patient subject ID")
    trigger: str = Field(description="What triggered this pipeline (api, celery, manual)")
    
    # Phase tracking
    extraction_completed: bool = Field(default=False, description="Extraction phase completed")
    reconciliation_completed: bool = Field(default=False, description="Reconciliation phase completed")
    clinical_completed: bool = Field(default=False, description="Clinical reasoning phase completed")
    
    # Run IDs for each phase
    extraction_run_id: Optional[str] = Field(default=None, description="Extraction agent run ID")
    reconciliation_run_id: Optional[str] = Field(default=None, description="Reconciliation agent run ID")
    clinical_run_id: Optional[str] = Field(default=None, description="Clinical agent run ID")
    
    # Results
    list_a_count: Optional[int] = Field(default=None, description="Number of medications in List A")
    list_b_count: Optional[int] = Field(default=None, description="Number of medications in List B")
    list_c_count: Optional[int] = Field(default=None, description="Number of medications in List C")
    discrepancy_count: Optional[int] = Field(default=None, description="Number of discrepancies found")
    
    # Timing
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Pipeline start time")
    completed_at: Optional[datetime] = Field(default=None, description="Pipeline completion time")
    
    # Status
    status: RunStatus = Field(default=RunStatus.PENDING, description="Overall pipeline status")
    error: Optional[str] = Field(default=None, description="Error message if pipeline failed")
    
    class Config:
        use_enum_values = True


class Message(BaseModel):
    """
    Single message in a conversation.
    
    Used by the Chat Agent for patient interactions.
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Message ID")
    session_id: str = Field(description="Session ID this message belongs to")
    role: str = Field(description="Message role: user, assistant, system, tool")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg-123",
                "session_id": "session-456",
                "role": "user",
                "content": "What medications am I taking?",
                "timestamp": "2180-06-27T10:15:00",
                "metadata": {"run_id": "run-789"}
            }
        }


class SessionStatus(str, Enum):
    """Status of a conversation session."""
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class Session(BaseModel):
    """
    A bounded conversation session with a patient.
    
    Used by the Chat Agent to manage conversation context.
    """
    
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Session ID")
    patient_id: str = Field(description="Patient subject ID")
    thread_id: str = Field(description="Pipeline thread this session belongs to")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="Session start time")
    ended_at: Optional[datetime] = Field(default=None, description="Session end time")
    message_count: int = Field(default=0, description="Number of messages in session")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Session status")
    
    class Config:
        use_enum_values = True
    
    def close(self):
        """Close the session."""
        self.status = SessionStatus.CLOSED
        self.ended_at = datetime.utcnow()
    
    def expire(self):
        """Expire the session."""
        self.status = SessionStatus.EXPIRED
        self.ended_at = datetime.utcnow()
