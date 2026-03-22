"""
Discrepancy Models

Models for medication discrepancies and urgency scoring.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DiscrepancyType(str, Enum):
    """Type of medication discrepancy."""
    # Presence discrepancies
    MISSING_IN_LIST_A = "missing_in_list_a"            # Not in discharge list
    MISSING_IN_LIST_B = "missing_in_list_b"            # Not in pharmacy list
    MISSING_IN_LIST_C = "missing_in_list_c"            # Not in self-report list
    
    # Attribute discrepancies (when medication exists in multiple lists but attributes differ)
    DOSE_VALUE_MISMATCH = "dose_value_mismatch"        # Different dose value across lists
    DOSE_UNIT_MISMATCH = "dose_unit_mismatch"          # Different dose unit across lists
    DOSE_FORM_MISMATCH = "dose_form_mismatch"          # Different dose form across lists
    ROUTE_MISMATCH = "route_mismatch"                  # Different route across lists
    QUANTITY_MISMATCH = "quantity_mismatch"            # Different quantity across lists
    FREQUENCY_MISMATCH = "frequency_mismatch"          # Different frequency across lists
    
    # Temporal discrepancies
    FILL_GAP = "fill_gap"                              # Gap > N days between discharge and first fill


class UrgencyLevel(str, Enum):
    """Urgency level for discrepancies."""
    CRITICAL = "critical"    # Immediate action required
    HIGH = "high"            # Action required within 24 hours
    MEDIUM = "medium"        # Action required within 72 hours
    LOW = "low"              # Monitor, no immediate action
    INFO = "info"            # Informational only


class Discrepancy(BaseModel):
    """
    Medication discrepancy between lists.
    
    Represents a mismatch or missing medication across
    List A (discharge), List B (pharmacy), List C (self-report).
    """
    
    discrepancy_id: str = Field(description="Unique discrepancy ID")
    patient_id: str = Field(description="Patient subject ID")
    
    # Discrepancy details
    discrepancy_type: DiscrepancyType = Field(description="Type of discrepancy")
    drug_name: str = Field(description="Drug name")
    rxnorm_code: Optional[str] = Field(default=None, description="RxNorm code if available")
    
    # List presence
    in_list_a: bool = Field(default=False, description="Present in List A (discharge)")
    in_list_b: bool = Field(default=False, description="Present in List B (pharmacy)")
    in_list_c: bool = Field(default=False, description="Present in List C (self-report)")
    
    # Details from each list
    list_a_details: Optional[str] = Field(default=None, description="Details from discharge")
    list_b_details: Optional[str] = Field(default=None, description="Details from pharmacy")
    list_c_details: Optional[str] = Field(default=None, description="Details from self-report")
    
    # Specific mismatch details
    dose_a: Optional[str] = Field(default=None, description="Dose from List A")
    dose_b: Optional[str] = Field(default=None, description="Dose from List B")
    dose_c: Optional[str] = Field(default=None, description="Dose from List C")
    
    frequency_a: Optional[str] = Field(default=None, description="Frequency from List A")
    frequency_b: Optional[str] = Field(default=None, description="Frequency from List B")
    frequency_c: Optional[str] = Field(default=None, description="Frequency from List C")
    
    # Urgency (populated by Clinical Reasoning Agent)
    urgency_score: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Urgency score (0-10)")
    urgency_level: Optional[UrgencyLevel] = Field(default=None, description="Urgency level")
    clinical_rationale: Optional[str] = Field(default=None, description="Clinical reasoning for urgency")
    
    # Temporal data
    discharge_date: Optional[datetime] = Field(default=None, description="Discharge date (charttime)")
    first_fill_date: Optional[datetime] = Field(default=None, description="First pharmacy fill after discharge")
    last_fill_date: Optional[datetime] = Field(default=None, description="Most recent pharmacy fill")
    days_to_first_fill: Optional[int] = Field(default=None, description="Days from discharge to first fill")
    days_since_last_fill: Optional[int] = Field(default=None, description="Days since last fill")
    fill_gap_days: Optional[int] = Field(default=None, description="Gap in days (for FILL_GAP type)")
    
    # Metadata
    detected_at: datetime = Field(default_factory=datetime.utcnow, description="When discrepancy was detected")
    days_since_discharge: Optional[int] = Field(default=None, description="Days since discharge")
    
    # Resolution
    resolved: bool = Field(default=False, description="Whether discrepancy has been resolved")
    resolved_at: Optional[datetime] = Field(default=None, description="When resolved")
    resolution_notes: Optional[str] = Field(default=None, description="Resolution notes")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "discrepancy_id": "disc-123",
                "patient_id": "10000032",
                "discrepancy_type": "dose_mismatch",
                "drug_name": "Furosemide",
                "rxnorm_code": "4603",
                "in_list_a": True,
                "in_list_b": True,
                "in_list_c": False,
                "dose_a": "40 mg",
                "dose_b": "20 mg",
                "urgency_score": 7.5,
                "urgency_level": "high",
                "days_since_discharge": 3
            }
        }


class UrgencyScore(BaseModel):
    """
    Urgency score for a discrepancy.
    
    Calculated by Clinical Reasoning Agent based on:
    - Drug class and risk
    - Type of discrepancy
    - Time since discharge
    - Patient context
    """
    
    discrepancy_id: str = Field(description="Discrepancy ID")
    score: float = Field(ge=0.0, le=10.0, description="Urgency score (0-10)")
    level: UrgencyLevel = Field(description="Urgency level")
    
    # Score components
    drug_risk_score: float = Field(default=0.0, description="Drug risk component (0-3)")
    discrepancy_type_score: float = Field(default=0.0, description="Discrepancy type component (0-3)")
    time_decay_score: float = Field(default=0.0, description="Time decay component (0-2)")
    patient_context_score: float = Field(default=0.0, description="Patient context component (0-2)")
    
    # Rationale
    rationale: str = Field(description="Clinical rationale for score")
    recommended_action: str = Field(description="Recommended action")
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow, description="When score was calculated")
    calculated_by: str = Field(default="clinical_agent", description="Agent that calculated score")
    
    class Config:
        use_enum_values = True
