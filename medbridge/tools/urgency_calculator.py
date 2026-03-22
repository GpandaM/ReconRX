"""
Urgency Calculator Tool

Calculates urgency scores for medication discrepancies.
"""

import logging
from medbridge.models.discrepancy import Discrepancy, DiscrepancyType, UrgencyLevel, UrgencyScore
from medbridge.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# Risk weights for different discrepancy types
DISCREPANCY_TYPE_WEIGHTS = {
    # Presence discrepancies
    DiscrepancyType.MISSING_IN_LIST_A: 2.0,           # Medium-high - not prescribed but patient has it
    DiscrepancyType.MISSING_IN_LIST_B: 3.0,           # Critical - prescribed but not filled
    DiscrepancyType.MISSING_IN_LIST_C: 1.5,           # Medium - possible non-adherence or reporting issue
    
    # Attribute discrepancies
    DiscrepancyType.DOSE_VALUE_MISMATCH: 2.8,         # High risk - wrong dose value
    DiscrepancyType.DOSE_UNIT_MISMATCH: 2.5,          # High risk - wrong dose unit
    DiscrepancyType.DOSE_FORM_MISMATCH: 1.8,          # Medium risk - different form
    DiscrepancyType.ROUTE_MISMATCH: 2.8,              # High risk - wrong route
    DiscrepancyType.QUANTITY_MISMATCH: 1.5,           # Medium risk - quantity difference
    DiscrepancyType.FREQUENCY_MISMATCH: 2.5,          # High risk - wrong frequency
    
    # Temporal discrepancies
    DiscrepancyType.FILL_GAP: 2.5,                    # High risk - delay in filling
}


def calculate_urgency(discrepancy: Discrepancy) -> UrgencyScore:
    """
    Calculate urgency score for a discrepancy.
    
    Score components (0-10 scale):
    - Drug risk: 0-3 (based on drug class - simplified for now)
    - Discrepancy type: 0-3 (based on type of mismatch)
    - Time decay: 0-2 (increases with days since discharge)
    - Patient context: 0-2 (comorbidities, age - simplified for now)
    
    Args:
        discrepancy: Discrepancy to score
        
    Returns:
        UrgencyScore: Calculated urgency score
    """
    
    # Component 1: Drug risk (simplified - assume all drugs are medium risk)
    # TODO: Use drug database to get actual risk class
    drug_risk_score = 2.0  # Medium risk default
    
    # Component 2: Discrepancy type
    discrepancy_type_score = DISCREPANCY_TYPE_WEIGHTS.get(
        discrepancy.discrepancy_type,
        1.5  # Default medium risk
    )
    
    # Component 3: Time-based urgency
    time_decay_score = 0.0
    
    # For FILL_GAP, use the gap days
    if discrepancy.discrepancy_type == DiscrepancyType.FILL_GAP and discrepancy.fill_gap_days:
        gap = discrepancy.fill_gap_days
        if gap <= 7:
            time_decay_score = 0.5
        elif gap <= 14:
            time_decay_score = 1.0
        elif gap <= 30:
            time_decay_score = 1.5
        else:
            time_decay_score = 2.0
    
    # For MISSING_IN_LIST_B (not filled), urgency increases with days since discharge
    elif discrepancy.discrepancy_type == DiscrepancyType.MISSING_IN_LIST_B:
        if discrepancy.days_since_discharge is not None:
            days = discrepancy.days_since_discharge
            if days <= 3:
                time_decay_score = 1.0  # Already urgent
            elif days <= 7:
                time_decay_score = 1.5
            elif days <= 14:
                time_decay_score = 1.8
            else:
                time_decay_score = 2.0  # Very urgent
    
    # For other types, use days since discharge
    elif discrepancy.days_since_discharge is not None:
        days = discrepancy.days_since_discharge
        if days <= 3:
            time_decay_score = 0.5
        elif days <= 7:
            time_decay_score = 1.0
        elif days <= 14:
            time_decay_score = 1.5
        else:
            time_decay_score = 2.0
    
    # Component 4: Patient context (simplified - assume medium risk)
    # TODO: Use patient comorbidities, age, etc.
    patient_context_score = 1.0
    
    # Calculate total score
    total_score = (
        drug_risk_score +
        discrepancy_type_score +
        time_decay_score +
        patient_context_score
    )
    
    # Cap at 10.0
    total_score = min(total_score, 10.0)
    
    # Determine urgency level
    if total_score >= settings.alert_threshold_critical:
        level = UrgencyLevel.CRITICAL
        action = "IMMEDIATE: Contact patient and prescriber within 1 hour"
    elif total_score >= settings.alert_threshold_high:
        level = UrgencyLevel.HIGH
        action = "URGENT: Contact patient within 24 hours"
    elif total_score >= settings.alert_threshold_medium:
        level = UrgencyLevel.MEDIUM
        action = "MODERATE: Follow up within 72 hours"
    elif total_score >= settings.alert_threshold_low:
        level = UrgencyLevel.LOW
        action = "LOW: Monitor, no immediate action required"
    else:
        level = UrgencyLevel.INFO
        action = "INFO: Informational only, document in chart"
    
    # Build rationale
    rationale_parts = [
        f"Type: {discrepancy.discrepancy_type.value} (score: {discrepancy_type_score:.1f})",
        f"Drug risk: medium (score: {drug_risk_score:.1f})",
    ]
    
    # Add temporal context
    if discrepancy.discrepancy_type == DiscrepancyType.FILL_GAP and discrepancy.fill_gap_days:
        rationale_parts.append(
            f"Fill gap: {discrepancy.fill_gap_days} days (score: {time_decay_score:.1f})"
        )
    elif discrepancy.discrepancy_type == DiscrepancyType.MISSING_IN_LIST_B and discrepancy.days_since_discharge:
        rationale_parts.append(
            f"Not filled for {discrepancy.days_since_discharge} days (score: {time_decay_score:.1f})"
        )
    elif discrepancy.days_since_discharge is not None:
        rationale_parts.append(
            f"Days since discharge: {discrepancy.days_since_discharge} (score: {time_decay_score:.1f})"
        )
    
    # Add attribute mismatch details if applicable
    if discrepancy.discrepancy_type == DiscrepancyType.DOSE_VALUE_MISMATCH:
        rationale_parts.append(
            f"Dose value mismatch: A={discrepancy.dose_a}, B={discrepancy.dose_b}, C={discrepancy.dose_c}"
        )
    elif discrepancy.discrepancy_type == DiscrepancyType.DOSE_UNIT_MISMATCH:
        rationale_parts.append(
            f"Dose unit mismatch across lists"
        )
    elif discrepancy.discrepancy_type == DiscrepancyType.DOSE_FORM_MISMATCH:
        rationale_parts.append(
            f"Dose form mismatch across lists"
        )
    elif discrepancy.discrepancy_type == DiscrepancyType.ROUTE_MISMATCH:
        rationale_parts.append(
            f"Route mismatch across lists"
        )
    elif discrepancy.discrepancy_type == DiscrepancyType.FREQUENCY_MISMATCH:
        rationale_parts.append(
            f"Frequency mismatch: A={discrepancy.frequency_a}, B={discrepancy.frequency_b}, C={discrepancy.frequency_c}"
        )
    elif discrepancy.discrepancy_type == DiscrepancyType.QUANTITY_MISMATCH:
        rationale_parts.append(
            f"Quantity mismatch across lists"
        )
    
    rationale_parts.append(f"Patient context: standard (score: {patient_context_score:.1f})")
    rationale = "; ".join(rationale_parts)
    
    return UrgencyScore(
        discrepancy_id=discrepancy.discrepancy_id,
        score=total_score,
        level=level,
        drug_risk_score=drug_risk_score,
        discrepancy_type_score=discrepancy_type_score,
        time_decay_score=time_decay_score,
        patient_context_score=patient_context_score,
        rationale=rationale,
        recommended_action=action
    )
