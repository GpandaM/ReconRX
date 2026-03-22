"""
Patient Data Models

Patient, admission, and discharge context models.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class Admission(BaseModel):
    """Hospital admission record."""
    
    hadm_id: str = Field(description="Hospital admission ID")
    subject_id: str = Field(description="Patient subject ID")
    admission_date: Optional[datetime] = Field(default=None, description="Admission date")
    discharge_date: Optional[datetime] = Field(default=None, description="Discharge date")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hadm_id": "22841357",
                "subject_id": "10000032",
                "admission_date": "2180-06-20T00:00:00",
                "discharge_date": "2180-06-27T00:00:00"
            }
        }


class DischargeContext(BaseModel):
    """
    Discharge context extracted from discharge summary.
    
    Contains structured information about the patient's hospitalization,
    diagnoses, and discharge plan.
    """
    
    note_id: str = Field(description="Note ID")
    subject_id: str = Field(description="Patient subject ID")
    hadm_id: str = Field(description="Hospital admission ID")
    note_type: str = Field(description="Note type (e.g., 'DS' for discharge summary)")
    note_seq: int = Field(description="Note sequence number")
    charttime: Optional[datetime] = Field(default=None, description="Chart time")
    storetime: Optional[datetime] = Field(default=None, description="Store time")
    
    # Extracted sections (populated by Extraction Agent)
    discharge_diagnosis: Optional[str] = Field(default=None, description="Discharge diagnosis")
    history_present_illness: Optional[str] = Field(default=None, description="History of present illness")
    past_medical_history: Optional[str] = Field(default=None, description="Past medical history")
    medications_on_admission: Optional[str] = Field(default=None, description="Medications on admission section")
    discharge_medications: Optional[str] = Field(default=None, description="Discharge medications section")
    discharge_instructions: Optional[str] = Field(default=None, description="Discharge instructions")
    
    # Full text
    full_text: str = Field(description="Full discharge summary text")
    
    class Config:
        json_schema_extra = {
            "example": {
                "note_id": "10000032-DS-22",
                "subject_id": "10000032",
                "hadm_id": "22841357",
                "note_type": "DS",
                "note_seq": 22,
                "charttime": "2180-06-27T00:00:00",
                "storetime": "2180-07-01T10:15:00",
                "full_text": "Name: ___ Unit No: ___\n\nAdmission Date: ___ Discharge Date: ___\n\n..."
            }
        }


class Patient(BaseModel):
    """
    Patient record with demographic and clinical context.
    
    Aggregates information from multiple sources for a complete patient view.
    """
    
    subject_id: str = Field(description="Patient subject ID (primary key)")
    
    # Demographics (would be populated from EHR in production)
    age: Optional[int] = Field(default=None, description="Patient age")
    gender: Optional[str] = Field(default=None, description="Patient gender")
    
    # Clinical context
    diagnoses: List[str] = Field(default_factory=list, description="List of diagnoses")
    comorbidities: List[str] = Field(default_factory=list, description="List of comorbidities")
    allergies: List[str] = Field(default_factory=list, description="Known drug allergies")
    
    # Most recent admission
    current_admission: Optional[Admission] = Field(default=None, description="Current/most recent admission")
    
    # Discharge context
    discharge_context: Optional[DischargeContext] = Field(default=None, description="Most recent discharge context")
    
    # Metadata
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "subject_id": "10000032",
                "age": 65,
                "gender": "M",
                "diagnoses": ["Heart Failure", "Hypertension"],
                "comorbidities": ["Diabetes Type 2", "CKD Stage 3"],
                "allergies": ["Penicillin"],
                "last_updated": "2180-06-27T10:15:00"
            }
        }
