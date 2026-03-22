"""
ReAct Models

Data models for ReAct (Reasoning + Acting) loop execution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional


@dataclass
class ReActStep:
    """
    Single step in a ReAct reasoning loop.
    
    Represents one Think -> Act -> Observe cycle.
    """
    
    iteration: int
    thought: str                    # Agent's reasoning about what to do next
    action: str                     # Tool name to call
    action_input: Dict[str, Any]    # Tool arguments
    observation: str                # Tool result
    latency_ms: float               # Time taken for this step
    tokens_used: int                # LLM tokens consumed
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "iteration": self.iteration,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "latency_ms": self.latency_ms,
            "tokens_used": self.tokens_used,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ReActTrace:
    """
    Complete trace of a ReAct reasoning loop execution.
    
    Contains all steps, final output, and performance metrics.
    """
    
    run_id: str                     # Links to RunContext.run_id
    thread_id: str                  # Links to RunContext.thread_id
    agent_name: str                 # Agent that executed this trace
    steps: List[ReActStep]          # All reasoning steps
    final_output: str               # Final answer/assessment
    total_latency_ms: float         # Total execution time
    total_tokens: int               # Total tokens consumed
    stopped_reason: str             # "max_iterations" | "stop_condition" | "no_action" | "error"
    error: Optional[str] = None     # Error message if stopped due to error
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "agent_name": self.agent_name,
            "steps": [step.to_dict() for step in self.steps],
            "final_output": self.final_output,
            "total_latency_ms": self.total_latency_ms,
            "total_tokens": self.total_tokens,
            "stopped_reason": self.stopped_reason,
            "error": self.error,
            "step_count": len(self.steps)
        }
