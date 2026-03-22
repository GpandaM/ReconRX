"""
Normalizer Module

Normalizes pharmacy claims data into CanonicalMedication format.
Maps CSV columns to the canonical schema for consistent reconciliation.
"""

import logging
from typing import List, Optional
import pandas as pd
from datetime import datetime

from medbridge.models.medication import (
    CanonicalMedication,
    MedSource,
    DoseForm,
    Frequency,
)

logger = logging.getLogger(__name__)


# Mapping from pharmacy CSV dose form to canonical DoseForm enum
DOSE_FORM_MAPPING = {
    "Tablet": DoseForm.TABLET,
    "Capsule": DoseForm.CAPSULE,
    "Liquid": DoseForm.LIQUID,
    "Injection": DoseForm.INJECTION,
    "Cream": DoseForm.CREAM,
    "Ointment": DoseForm.OINTMENT,
    "Patch": DoseForm.PATCH,
    "Inhaler": DoseForm.INHALER,
    "Suppository": DoseForm.SUPPOSITORY,
    "Unknown": DoseForm.UNKNOWN,
    # Add common variations
    "Tab": DoseForm.TABLET,
    "Cap": DoseForm.CAPSULE,
    "Soln": DoseForm.LIQUID,
    "Solution": DoseForm.LIQUID,
    "Inj": DoseForm.INJECTION,
}


def parse_dose(dose_str: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """
    Parse dose string into value and unit.
    
    Args:
        dose_str: Dose string (e.g., "40 mg", "500mg", "1.5 g")
        
    Returns:
        tuple: (dose_value, dose_unit) or (None, None) if parsing fails
        
    Examples:
        >>> parse_dose("40 mg")
        (40.0, "mg")
        >>> parse_dose("1.5 g")
        (1.5, "g")
        >>> parse_dose("500mg")
        (500.0, "mg")
    """
    if not dose_str or pd.isna(dose_str):
        return None, None
    
    dose_str = str(dose_str).strip()
    
    # Try to split on space
    parts = dose_str.split()
    if len(parts) == 2:
        try:
            value = float(parts[0])
            unit = parts[1]
            return value, unit
        except ValueError:
            pass
    
    # Try to extract number and unit without space (e.g., "500mg")
    import re
    match = re.match(r'([\d.]+)\s*([a-zA-Z]+)', dose_str)
    if match:
        try:
            value = float(match.group(1))
            unit = match.group(2)
            return value, unit
        except ValueError:
            pass
    
    logger.warning(f"Could not parse dose: {dose_str}")
    return None, None


def normalize_dose_form(dose_form_str: Optional[str]) -> DoseForm:
    """
    Normalize dose form string to DoseForm enum.
    
    Args:
        dose_form_str: Dose form string from pharmacy data
        
    Returns:
        DoseForm: Normalized dose form enum
    """
    if not dose_form_str or pd.isna(dose_form_str):
        return DoseForm.UNKNOWN
    
    dose_form_str = str(dose_form_str).strip()
    return DOSE_FORM_MAPPING.get(dose_form_str, DoseForm.UNKNOWN)


def normalize_pharmacy_record(row: pd.Series) -> CanonicalMedication:
    """
    Normalize a single pharmacy claims record to CanonicalMedication.
    
    Args:
        row: Pandas Series representing one pharmacy claim row
        
    Returns:
        CanonicalMedication: Normalized medication record
        
    Expected CSV columns:
        - subject_id: Patient ID
        - Date: Fill date
        - NDC: National Drug Code
        - RxNorm Code: RxNorm concept ID
        - Drug Name: Drug name
        - Dose: Dose (e.g., "40 mg")
        - Quantity: Quantity dispensed
        - Dose Form: Dose form (e.g., "Tablet")
        - Original Prescribed: Original prescribed indicator
        - Case Type: Case type (e.g., "Historical", "Current")
    """
    # Parse dose
    dose_value, dose_unit = parse_dose(row.get('Dose'))
    
    # Normalize dose form
    dose_form = normalize_dose_form(row.get('Dose Form'))
    
    # Handle RxNorm code (convert to string, handle missing/invalid)
    rxnorm_code = str(row.get('RxNorm Code', '000000'))
    if rxnorm_code == '000000' or rxnorm_code == 'nan' or rxnorm_code == '000nan' or not rxnorm_code or rxnorm_code == '':
        rxnorm_code = None
    
    # Handle NDC
    ndc = str(row.get('NDC', ''))
    if ndc == 'nan' or ndc == '00000-0000-00':
        ndc = None
    
    # Parse date
    date = row.get('Date')
    if pd.notna(date):
        if isinstance(date, str):
            try:
                date = pd.to_datetime(date)
            except:
                date = None
    else:
        date = None
    
    # Create canonical medication
    med = CanonicalMedication(
        rxnorm_code=rxnorm_code,
        ndc=ndc,
        drug_name=str(row.get('Drug Name', 'Unknown')),
        drug_name_normalized=str(row.get('Drug Name', 'Unknown')).lower() if pd.notna(row.get('Drug Name')) else None,
        dose=str(row.get('Dose')) if pd.notna(row.get('Dose')) else None,
        dose_value=dose_value,
        dose_unit=dose_unit,
        dose_form=dose_form,
        route=None,  # Not provided in pharmacy data
        frequency=Frequency.UNKNOWN,  # Not provided in pharmacy data
        quantity=int(row.get('Quantity', 0)) if pd.notna(row.get('Quantity')) else None,
        source=MedSource.PHARMACY,
        date=date,
        subject_id=str(row.get('subject_id')),
        case_type=str(row.get('Case Type')) if pd.notna(row.get('Case Type')) else None,
        original_prescribed=str(row.get('Original Prescribed')) if pd.notna(row.get('Original Prescribed')) else None,
        confidence=1.0,  # Pharmacy data is structured, so confidence is 1.0
    )
    
    return med


def normalize_pharmacy_batch(df: pd.DataFrame) -> List[CanonicalMedication]:
    """
    Normalize a batch of pharmacy claims records.
    
    Args:
        df: DataFrame of pharmacy claims
        
    Returns:
        List[CanonicalMedication]: List of normalized medications
    """
    medications = []
    
    for idx, row in df.iterrows():
        try:
            med = normalize_pharmacy_record(row)
            medications.append(med)
        except Exception as e:
            logger.error(f"Error normalizing pharmacy record at index {idx}: {e}")
            logger.debug(f"Problematic row: {row.to_dict()}")
            continue
    
    logger.info(f"Normalized {len(medications)} pharmacy records from {len(df)} rows")
    return medications


def get_patient_pharmacy_meds(subject_id: str, pharmacy_df: pd.DataFrame) -> List[CanonicalMedication]:
    """
    Get normalized pharmacy medications for a specific patient.
    
    Args:
        subject_id: Patient subject ID
        pharmacy_df: Full pharmacy claims DataFrame
        
    Returns:
        List[CanonicalMedication]: List of normalized medications for the patient
    """
    patient_fills = pharmacy_df[pharmacy_df['subject_id'].astype(str) == str(subject_id)]
    
    if patient_fills.empty:
        logger.warning(f"No pharmacy fills found for patient {subject_id}")
        return []
    
    medications = normalize_pharmacy_batch(patient_fills)
    logger.info(f"Retrieved {len(medications)} pharmacy medications for patient {subject_id}")
    
    return medications


def deduplicate_medications(medications: List[CanonicalMedication]) -> List[CanonicalMedication]:
    """
    Deduplicate medications based on exact match of drug, dose, form, quantity, and date.
    
    Two records are considered duplicates ONLY if they match on:
    - Drug (RxNorm code or name)
    - Dose
    - Dose form
    - Quantity
    - Date
    
    This preserves legitimate variations like:
    - Same drug, different doses (e.g., 20mg vs 40mg)
    - Same drug, different forms (e.g., Tablet vs Liquid)
    - Same drug, different dates (refills over time)
    
    Args:
        medications: List of medications (potentially with duplicates)
        
    Returns:
        List[CanonicalMedication]: Deduplicated list
    """
    if not medications:
        return []
    
    # Group by deduplication key (includes dose, form, quantity, date)
    seen_keys = set()
    deduplicated = []
    
    for med in medications:
        dedup_key = med.to_dedup_key()
        
        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            deduplicated.append(med)
    
    if len(deduplicated) < len(medications):
        removed_count = len(medications) - len(deduplicated)
        logger.info(
            f"Removed {removed_count} exact duplicate(s) from {len(medications)} medications "
            f"(kept {len(deduplicated)} unique records)"
        )
    
    return deduplicated
