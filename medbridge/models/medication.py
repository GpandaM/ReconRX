"""
Medication Data Models

Canonical medication representation used throughout MedBridge.
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class MedSource(str, Enum):
    """Source of medication data."""
    DISCHARGE = "discharge"  # List A: extracted from discharge summary
    PHARMACY = "pharmacy"    # List B: pharmacy claims data
    SELF_REPORT = "self_report"  # List C: patient self-reported
    SIMULATED = "simulated"  # Synthetic data for testing


class DoseForm(str, Enum):
    """Medication dose form."""
    TABLET = "Tablet"
    CAPSULE = "Capsule"
    LIQUID = "Liquid"
    INJECTION = "Injection"
    CREAM = "Cream"
    OINTMENT = "Ointment"
    PATCH = "Patch"
    INHALER = "Inhaler"
    SUPPOSITORY = "Suppository"
    UNKNOWN = "Unknown"


class Frequency(str, Enum):
    """Medication frequency."""
    DAILY = "DAILY"
    BID = "BID"  # Twice daily
    TID = "TID"  # Three times daily
    QID = "QID"  # Four times daily
    QHS = "QHS"  # At bedtime
    PRN = "PRN"  # As needed
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    UNKNOWN = "UNKNOWN"


class CanonicalMedication(BaseModel):
    """
    Canonical medication representation.
    
    All medication data (from discharge summaries, pharmacy claims, or patient reports)
    is normalized into this schema for consistent reconciliation.
    """
    
    # Identifiers
    rxnorm_code: Optional[str] = Field(default=None, description="RxNorm concept unique identifier")
    ndc: Optional[str] = Field(default=None, description="National Drug Code (pharmacy data)")
    
    # Drug information
    drug_name: str = Field(description="Drug name (generic or brand)")
    drug_name_normalized: Optional[str] = Field(default=None, description="Normalized drug name via RxNorm")
    
    # Dosage
    dose: Optional[str] = Field(default=None, description="Dose strength (e.g., '40 mg', '500 mg')")
    dose_value: Optional[float] = Field(default=None, description="Numeric dose value")
    dose_unit: Optional[str] = Field(default=None, description="Dose unit (mg, g, mL, etc.)")
    
    # Administration
    dose_form: DoseForm = Field(default=DoseForm.UNKNOWN, description="Dose form")
    route: Optional[str] = Field(default=None, description="Route of administration (PO, IV, etc.)")
    frequency: Frequency = Field(default=Frequency.UNKNOWN, description="Frequency")
    
    # Quantity (pharmacy data)
    quantity: Optional[int] = Field(default=None, description="Quantity dispensed")
    
    # Metadata
    source: MedSource = Field(description="Source of this medication record")
    original_text: Optional[str] = Field(default=None, description="Original text from source (for traceability)")
    date: Optional[datetime] = Field(default=None, description="Date of record (fill date, discharge date, etc.)")
    
    # Patient linkage
    subject_id: str = Field(description="Patient subject ID")
    
    # Additional pharmacy data
    case_type: Optional[str] = Field(default=None, description="Case type from pharmacy data")
    original_prescribed: Optional[str] = Field(default=None, description="Original prescribed indicator")
    
    # Extraction confidence (for LLM-extracted data)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Extraction confidence (0-1)")
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "rxnorm_code": "4603",
                "ndc": "00054-4297-25",
                "drug_name": "Furosemide",
                "drug_name_normalized": "furosemide",
                "dose": "40 mg",
                "dose_value": 40.0,
                "dose_unit": "mg",
                "dose_form": "Tablet",
                "route": "PO",
                "frequency": "DAILY",
                "quantity": 30,
                "source": "pharmacy",
                "date": "2180-05-09T00:00:00",
                "subject_id": "10000032",
                "case_type": "Historical",
                "original_prescribed": "Historical Refill"
            }
        }
    
    def to_key(self) -> str:
        """
        Generate a unique key for this medication.
        
        Used for matching medications across lists (reconciliation).
        Returns RxNorm code if available, otherwise normalized drug name.
        Note: This is for matching the SAME drug, not for deduplication.
        """
        if self.rxnorm_code and self.rxnorm_code != "000000":
            return f"rxnorm:{self.rxnorm_code}"
        if self.drug_name_normalized:
            return f"name:{self.drug_name_normalized.lower()}"
        return f"name:{self.drug_name.lower()}"
    
    def to_dedup_key(self) -> str:
        """
        Generate a deduplication key that includes dose, form, and quantity.
        
        Two records are considered duplicates only if they match on:
        - Drug (RxNorm code or name)
        - Dose
        - Dose form
        - Quantity
        - Date
        """
        base_key = self.to_key()
        
        # Add dose information
        dose_key = self.dose or "no_dose"
        
        # Add form (already a string due to use_enum_values = True)
        form_key = str(self.dose_form) if self.dose_form else "no_form"
        
        # Add quantity
        qty_key = str(self.quantity) if self.quantity else "no_qty"
        
        # Add date
        date_key = self.date.strftime("%Y-%m-%d") if self.date else "no_date"
        
        return f"{base_key}|{dose_key}|{form_key}|{qty_key}|{date_key}"
    
    def __hash__(self):
        """
        Hash based on matching key for set operations.
        
        Note: This uses to_key() which matches on drug only (not dose/form).
        This is intentional for reconciliation - we want to group all records
        of the same drug together, even if doses differ.
        """
        return hash(self.to_key())
    
    def __eq__(self, other):
        """
        Equality based on matching key.
        
        Note: This uses to_key() which matches on drug only (not dose/form).
        Two medications are "equal" if they're the same drug, even if doses differ.
        This is for reconciliation purposes, not exact deduplication.
        """
        if not isinstance(other, CanonicalMedication):
            return False
        return self.to_key() == other.to_key()
