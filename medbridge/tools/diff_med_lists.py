"""
Three-list comparison for medication reconciliation based on clinical workflow.
"""

import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import pandas as pd

from medbridge.models.medication import CanonicalMedication
from medbridge.models.discrepancy import Discrepancy, DiscrepancyType
from medbridge.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def compare_three_lists(
    list_a: List[CanonicalMedication],
    list_b: List[CanonicalMedication],
    list_c: List[CanonicalMedication],
    patient_id: str,
    discharge_date: Optional[str] = None
) -> List[Discrepancy]:
    """
    Compare three medication lists to ensure complete alignment.
    
    Objective: All three lists should have the same medications with matching attributes:
    - Name, RxNorm code, dose value, dose unit, dose form, route, frequency, quantity
    
    Discrepancy Detection:
    1. Presence: Check if medication exists in all three lists
    2. Attributes: For medications in multiple lists, check if all attributes match
    3. Temporal: Check for gaps in pharmacy fills after discharge
    
    Lists:
    - List A: Discharge medications (what was prescribed)
    - List B: Pharmacy fills (what was actually filled)
    - List C: Self-reported medications (what patient says they're taking)
    
    Args:
        list_a: List A (discharge medications)
        list_b: List B (pharmacy medications)
        list_c: List C (self-reported medications)
        patient_id: Patient subject ID
        discharge_date: Discharge date (charttime)
        
    Returns:
        List[Discrepancy]: List of identified discrepancies
    """
    discrepancies = []

    print("\n\n")
    print("list_a", list_a)
    print("\n")
    print("list_b", list_b)
    print("\n")
    print("list_c", list_c)
    print("\n\n")
    
    # Build medication dictionaries by key
    dict_a = {med.to_key(): med for med in list_a}
    dict_b_all = {med.to_key(): [] for med in list_b}
    for med in list_b:
        dict_b_all[med.to_key()].append(med)
    
    dict_c = {med.to_key(): med for med in list_c}
    
    logger.info(
        f"Comparing medication lists: "
        f"A={len(dict_a)}, B={len(list_b)} ({len(dict_b_all)} unique), C={len(dict_c)}"
    )

    # Convert discharge_date to datetime if it's a string
    discharge_datetime = None
    if discharge_date:
        if isinstance(discharge_date, str):
            discharge_datetime = pd.Timestamp(discharge_date)
        else:
            discharge_datetime = discharge_date
    
    # Calculate days since discharge
    days_since_discharge = None
    if discharge_datetime:
        days_since_discharge = (pd.Timestamp.now() - discharge_datetime).days
    

    print("\n\n")
    print("list a keys", dict_a.keys())
    print("\n")
    print("list b keys", dict_b_all.keys())
    print("\n")
    print("list c keys", dict_c.keys())
    print("\n\n")
    
    # Get all unique medication keys across all three lists
    all_keys = set(dict_a.keys()) | set(dict_b_all.keys()) | set(dict_c.keys())
    
    logger.info(f"Total unique medications across all lists: {len(all_keys)}")

    print("\n\n")
    print("all keys", all_keys)
    print("\n\n")
    
    # Process each unique medication
    for key in all_keys:
        print("\n\n")
        print("Processing key:", key)
        
        med_a = dict_a.get(key)
        pharmacy_fills = dict_b_all.get(key, [])
        med_c = dict_c.get(key)
        
        # Get pharmacy fills (filter by discharge date if provided)
        post_discharge_fills = []
        if pharmacy_fills:
            if discharge_datetime:
                for fill in pharmacy_fills:
                    if fill.date and fill.date >= discharge_datetime:
                        post_discharge_fills.append(fill)
                    elif not fill.date:
                        # No date - assume current
                        post_discharge_fills.append(fill)
            else:
                # No discharge date - treat all as current
                post_discharge_fills = pharmacy_fills
            
            # Sort by date
            post_discharge_fills.sort(key=lambda x: x.date if x.date else datetime.max)
        
        first_fill = post_discharge_fills[0] if post_discharge_fills else None
        last_fill = post_discharge_fills[-1] if post_discharge_fills else None
        
        print(f"med_a: {med_a is not None}, med_b: {last_fill is not None}, med_c: {med_c is not None}")
        
        # ===== PRESENCE CHECKS =====
        
        # Check 1: MISSING_IN_LIST_A - Not in discharge list
        if not med_a and (last_fill or med_c):
            discrepancies.append(_create_discrepancy(
                patient_id=patient_id,
                discrepancy_type=DiscrepancyType.MISSING_IN_LIST_A,
                drug_name=(last_fill.drug_name if last_fill else med_c.drug_name),
                rxnorm_code=(last_fill.rxnorm_code if last_fill else med_c.rxnorm_code),
                med_a=None,
                med_b=last_fill,
                med_c=med_c,
                discharge_date=discharge_date,
                first_fill_date=first_fill.date if first_fill else None,
                last_fill_date=last_fill.date if last_fill else None,
                days_since_discharge=days_since_discharge
            ))
        
        # Check 2: MISSING_IN_LIST_B - Not in pharmacy list
        if not last_fill and (med_a or med_c):
            discrepancies.append(_create_discrepancy(
                patient_id=patient_id,
                discrepancy_type=DiscrepancyType.MISSING_IN_LIST_B,
                drug_name=(med_a.drug_name if med_a else med_c.drug_name),
                rxnorm_code=(med_a.rxnorm_code if med_a else med_c.rxnorm_code),
                med_a=med_a,
                med_b=None,
                med_c=med_c,
                discharge_date=discharge_date,
                first_fill_date=None,
                last_fill_date=None,
                days_since_discharge=days_since_discharge
            ))
        
        # Check 3: MISSING_IN_LIST_C - Not in self-report list (only if List C exists)
        if list_c and not med_c and (med_a or last_fill):
            discrepancies.append(_create_discrepancy(
                patient_id=patient_id,
                discrepancy_type=DiscrepancyType.MISSING_IN_LIST_C,
                drug_name=(med_a.drug_name if med_a else last_fill.drug_name),
                rxnorm_code=(med_a.rxnorm_code if med_a else last_fill.rxnorm_code),
                med_a=med_a,
                med_b=last_fill,
                med_c=None,
                discharge_date=discharge_date,
                first_fill_date=first_fill.date if first_fill else None,
                last_fill_date=last_fill.date if last_fill else None,
                days_since_discharge=days_since_discharge
            ))
        
        # ===== TEMPORAL CHECKS (only if medication exists in relevant lists) =====
        
        # Check 4: FILL_GAP - Gap between discharge and first fill
        if med_a and first_fill and discharge_datetime and first_fill.date:
            days_to_fill = (first_fill.date - discharge_datetime).days
            
            if days_to_fill > settings.reconciliation_fill_gap_threshold_days:
                discrepancies.append(_create_discrepancy(
                    patient_id=patient_id,
                    discrepancy_type=DiscrepancyType.FILL_GAP,
                    drug_name=med_a.drug_name,
                    rxnorm_code=med_a.rxnorm_code,
                    med_a=med_a,
                    med_b=first_fill,
                    med_c=med_c,
                    discharge_date=discharge_date,
                    first_fill_date=first_fill.date,
                    last_fill_date=last_fill.date,
                    fill_gap_days=days_to_fill,
                    days_since_discharge=days_since_discharge
                ))
        
        # ===== ATTRIBUTE CHECKS (only if medication exists in at least 2 lists) =====
        # Compare attributes across all available lists
        
        # Get all available medications for this key
        meds_to_compare = []
        if med_a:
            meds_to_compare.append(('A', med_a))
        if last_fill:
            meds_to_compare.append(('B', last_fill))
        if med_c:
            meds_to_compare.append(('C', med_c))
        
        # Only check attributes if medication exists in at least 2 lists
        if len(meds_to_compare) >= 2:
            # Check 5: DOSE_VALUE_MISMATCH
            dose_values = [(label, m.dose_value) for label, m in meds_to_compare if m.dose_value is not None]
            if len(dose_values) >= 2 and len(set(v for _, v in dose_values)) > 1:
                discrepancies.append(_create_discrepancy(
                    patient_id=patient_id,
                    discrepancy_type=DiscrepancyType.DOSE_VALUE_MISMATCH,
                    drug_name=(med_a.drug_name if med_a else (last_fill.drug_name if last_fill else med_c.drug_name)),
                    rxnorm_code=(med_a.rxnorm_code if med_a else (last_fill.rxnorm_code if last_fill else med_c.rxnorm_code)),
                    med_a=med_a,
                    med_b=last_fill,
                    med_c=med_c,
                    discharge_date=discharge_date,
                    first_fill_date=first_fill.date if first_fill else None,
                    last_fill_date=last_fill.date if last_fill else None,
                    days_since_discharge=days_since_discharge
                ))
            
            # Check 6: DOSE_UNIT_MISMATCH
            dose_units = [(label, m.dose_unit.lower()) for label, m in meds_to_compare if m.dose_unit]
            if len(dose_units) >= 2 and len(set(u for _, u in dose_units)) > 1:
                discrepancies.append(_create_discrepancy(
                    patient_id=patient_id,
                    discrepancy_type=DiscrepancyType.DOSE_UNIT_MISMATCH,
                    drug_name=(med_a.drug_name if med_a else (last_fill.drug_name if last_fill else med_c.drug_name)),
                    rxnorm_code=(med_a.rxnorm_code if med_a else (last_fill.rxnorm_code if last_fill else med_c.rxnorm_code)),
                    med_a=med_a,
                    med_b=last_fill,
                    med_c=med_c,
                    discharge_date=discharge_date,
                    first_fill_date=first_fill.date if first_fill else None,
                    last_fill_date=last_fill.date if last_fill else None,
                    days_since_discharge=days_since_discharge
                ))
            
            # Check 7: DOSE_FORM_MISMATCH
            dose_forms = [(label, str(m.dose_form)) for label, m in meds_to_compare 
                         if m.dose_form and str(m.dose_form) != "UNKNOWN"]
            if len(dose_forms) >= 2 and len(set(f for _, f in dose_forms)) > 1:
                discrepancies.append(_create_discrepancy(
                    patient_id=patient_id,
                    discrepancy_type=DiscrepancyType.DOSE_FORM_MISMATCH,
                    drug_name=(med_a.drug_name if med_a else (last_fill.drug_name if last_fill else med_c.drug_name)),
                    rxnorm_code=(med_a.rxnorm_code if med_a else (last_fill.rxnorm_code if last_fill else med_c.rxnorm_code)),
                    med_a=med_a,
                    med_b=last_fill,
                    med_c=med_c,
                    discharge_date=discharge_date,
                    first_fill_date=first_fill.date if first_fill else None,
                    last_fill_date=last_fill.date if last_fill else None,
                    days_since_discharge=days_since_discharge
                ))
            
            # Check 8: ROUTE_MISMATCH
            routes = [(label, m.route.upper()) for label, m in meds_to_compare if m.route]
            if len(routes) >= 2 and len(set(r for _, r in routes)) > 1:
                discrepancies.append(_create_discrepancy(
                    patient_id=patient_id,
                    discrepancy_type=DiscrepancyType.ROUTE_MISMATCH,
                    drug_name=(med_a.drug_name if med_a else (last_fill.drug_name if last_fill else med_c.drug_name)),
                    rxnorm_code=(med_a.rxnorm_code if med_a else (last_fill.rxnorm_code if last_fill else med_c.rxnorm_code)),
                    med_a=med_a,
                    med_b=last_fill,
                    med_c=med_c,
                    discharge_date=discharge_date,
                    first_fill_date=first_fill.date if first_fill else None,
                    last_fill_date=last_fill.date if last_fill else None,
                    days_since_discharge=days_since_discharge
                ))
            
            # Check 9: QUANTITY_MISMATCH
            quantities = [(label, m.quantity) for label, m in meds_to_compare if m.quantity is not None]
            if len(quantities) >= 2 and len(set(q for _, q in quantities)) > 1:
                discrepancies.append(_create_discrepancy(
                    patient_id=patient_id,
                    discrepancy_type=DiscrepancyType.QUANTITY_MISMATCH,
                    drug_name=(med_a.drug_name if med_a else (last_fill.drug_name if last_fill else med_c.drug_name)),
                    rxnorm_code=(med_a.rxnorm_code if med_a else (last_fill.rxnorm_code if last_fill else med_c.rxnorm_code)),
                    med_a=med_a,
                    med_b=last_fill,
                    med_c=med_c,
                    discharge_date=discharge_date,
                    first_fill_date=first_fill.date if first_fill else None,
                    last_fill_date=last_fill.date if last_fill else None,
                    days_since_discharge=days_since_discharge
                ))
            
            # Check 10: FREQUENCY_MISMATCH
            frequencies = [(label, str(m.frequency)) for label, m in meds_to_compare 
                          if m.frequency and str(m.frequency) != "UNKNOWN"]
            if len(frequencies) >= 2 and len(set(f for _, f in frequencies)) > 1:
                discrepancies.append(_create_discrepancy(
                    patient_id=patient_id,
                    discrepancy_type=DiscrepancyType.FREQUENCY_MISMATCH,
                    drug_name=(med_a.drug_name if med_a else (last_fill.drug_name if last_fill else med_c.drug_name)),
                    rxnorm_code=(med_a.rxnorm_code if med_a else (last_fill.rxnorm_code if last_fill else med_c.rxnorm_code)),
                    med_a=med_a,
                    med_b=last_fill,
                    med_c=med_c,
                    discharge_date=discharge_date,
                    first_fill_date=first_fill.date if first_fill else None,
                    last_fill_date=last_fill.date if last_fill else None,
                    days_since_discharge=days_since_discharge
                ))
    
    logger.info(f"Found {len(discrepancies)} discrepancies for patient {patient_id}")
    
    return discrepancies


def _create_discrepancy(
    patient_id: str,
    discrepancy_type: DiscrepancyType,
    drug_name: str,
    rxnorm_code: Optional[str],
    med_a: Optional[CanonicalMedication],
    med_b: Optional[CanonicalMedication],
    med_c: Optional[CanonicalMedication],
    discharge_date: Optional[str],
    first_fill_date: Optional[datetime],
    last_fill_date: Optional[datetime],
    days_since_discharge: Optional[int],
    fill_gap_days: Optional[int] = None
) -> Discrepancy:
    """Create a discrepancy object."""
    
    # Calculate temporal metrics
    days_to_first_fill = None
    if discharge_date and first_fill_date:
        # Convert discharge_date to datetime if it's a string
        discharge_dt = pd.Timestamp(discharge_date) if isinstance(discharge_date, str) else discharge_date
        days_to_first_fill = (first_fill_date - discharge_dt).days
    
    days_since_last_fill = None
    if last_fill_date:
        days_since_last_fill = (pd.Timestamp.now() - pd.Timestamp(last_fill_date)).days
    
    return Discrepancy(
        discrepancy_id=str(uuid.uuid4()),
        patient_id=patient_id,
        discrepancy_type=discrepancy_type,
        drug_name=drug_name,
        rxnorm_code=rxnorm_code,
        in_list_a=med_a is not None,
        in_list_b=med_b is not None,
        in_list_c=med_c is not None,
        list_a_details=_format_med_details(med_a) if med_a else None,
        list_b_details=_format_med_details(med_b) if med_b else None,
        list_c_details=_format_med_details(med_c) if med_c else None,
        dose_a=med_a.dose if med_a else None,
        dose_b=med_b.dose if med_b else None,
        dose_c=med_c.dose if med_c else None,
        frequency_a=str(med_a.frequency) if med_a else None,
        frequency_b=str(med_b.frequency) if med_b else None,
        frequency_c=str(med_c.frequency) if med_c else None,
        discharge_date=discharge_date,
        first_fill_date=first_fill_date,
        last_fill_date=last_fill_date,
        days_to_first_fill=days_to_first_fill,
        days_since_last_fill=days_since_last_fill,
        fill_gap_days=fill_gap_days,
        days_since_discharge=days_since_discharge
    )


def _format_med_details(med: CanonicalMedication) -> str:
    """Format medication details as a string."""
    parts = [med.drug_name]
    if med.dose:
        parts.append(med.dose)
    if med.route:
        parts.append(med.route)
    if med.frequency and str(med.frequency) != "UNKNOWN":
        parts.append(str(med.frequency))
    if med.date:
        parts.append(f"(date: {med.date.strftime('%Y-%m-%d')})")
    return " ".join(parts)