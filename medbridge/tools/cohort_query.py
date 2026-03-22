"""
Cohort Query Tool

Queries historical patient data to find similar cases and outcomes.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# Simplified cohort database (V1)
# TODO: Replace with actual PySpark queries on patient database
COHORT_OUTCOMES = {
    "anticoagulant_not_filled": {
        "query": "Patients prescribed anticoagulants at discharge who didn't fill within 7 days",
        "cohort_size": 127,
        "outcomes": {
            "readmission_30d": 0.34,  # 34% readmitted within 30 days
            "adverse_events": 0.28,    # 28% had adverse events
            "mortality_90d": 0.12      # 12% mortality at 90 days
        },
        "common_reasons": [
            "Cost/insurance issues (45%)",
            "Patient didn't understand importance (32%)",
            "Prescription not sent to pharmacy (23%)"
        ]
    },
    "dose_mismatch_high_risk": {
        "query": "Patients with dose mismatches on high-risk medications",
        "cohort_size": 89,
        "outcomes": {
            "readmission_30d": 0.29,
            "adverse_events": 0.41,
            "medication_error": 0.56
        },
        "common_reasons": [
            "Hospital dose not communicated to outpatient provider (52%)",
            "Patient continued pre-admission dose (38%)",
            "Pharmacy substitution without notification (10%)"
        ]
    },
    "heart_failure_gap": {
        "query": "Heart failure patients with diuretic fill gaps > 3 days",
        "cohort_size": 203,
        "outcomes": {
            "readmission_30d": 0.47,  # 47% readmitted
            "volume_overload": 0.62,
            "mortality_90d": 0.18
        },
        "common_reasons": [
            "Patient felt better, stopped taking (41%)",
            "Pharmacy out of stock (22%)",
            "Cost/insurance (20%)",
            "Side effects (17%)"
        ]
    },
    "default": {
        "query": "General medication discrepancy outcomes",
        "cohort_size": 1543,
        "outcomes": {
            "readmission_30d": 0.22,
            "adverse_events": 0.15,
            "medication_error": 0.31
        },
        "common_reasons": [
            "Communication breakdown (35%)",
            "Patient non-adherence (28%)",
            "Prescription errors (22%)",
            "Pharmacy issues (15%)"
        ]
    }
}


def query_cohort(
    discrepancy_type: str,
    drug_name: Optional[str] = None,
    drug_risk_class: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query historical cohort data for similar cases.
    
    Args:
        discrepancy_type: Type of discrepancy (e.g., "missing_in_list_b", "dose_value_mismatch")
        drug_name: Drug name (optional, for drug-specific queries)
        drug_risk_class: Drug risk class (optional: "high", "medium", "low")
        
    Returns:
        Dict containing:
        - query: Description of cohort query
        - cohort_size: Number of similar patients
        - outcomes: Dict of outcome metrics (readmission, adverse events, etc.)
        - common_reasons: List of common reasons for this discrepancy
    """
    logger.info(
        f"Querying cohort: discrepancy={discrepancy_type}, "
        f"drug={drug_name}, risk={drug_risk_class}"
    )
    
    # Map discrepancy types to cohort queries
    cohort_key = "default"
    
    if discrepancy_type == "missing_in_list_b":
        # Not filled
        if drug_risk_class == "high" or (drug_name and "coagul" in drug_name.lower()):
            cohort_key = "anticoagulant_not_filled"
    
    elif discrepancy_type in ["dose_value_mismatch", "dose_unit_mismatch", "frequency_mismatch"]:
        if drug_risk_class == "high":
            cohort_key = "dose_mismatch_high_risk"
    
    elif discrepancy_type == "fill_gap":
        if drug_name and ("furosemide" in drug_name.lower() or "diuretic" in drug_name.lower()):
            cohort_key = "heart_failure_gap"
    
    result = COHORT_OUTCOMES.get(cohort_key, COHORT_OUTCOMES["default"]).copy()
    
    logger.info(
        f"Cohort query result: {result['cohort_size']} similar patients, "
        f"30d readmission rate: {result['outcomes']['readmission_30d']:.1%}"
    )
    
    return result


def get_similar_patient_outcomes(
    drug_name: str,
    discrepancy_type: str,
    patient_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Get human-readable summary of similar patient outcomes.
    
    Args:
        drug_name: Drug name
        discrepancy_type: Type of discrepancy
        patient_context: Patient context (optional)
        
    Returns:
        str: Human-readable summary
    """
    from medbridge.tools.drug_lookup import query_drug_db
    
    # Get drug risk
    drug_info = query_drug_db(drug_name)
    drug_risk = drug_info.get("risk_class", "medium")
    
    # Query cohort
    cohort_data = query_cohort(discrepancy_type, drug_name, drug_risk)
    
    # Build summary
    summary_parts = [
        f"Similar cases: {cohort_data['cohort_size']} patients with {discrepancy_type} for {drug_name}",
        f"Outcomes: {cohort_data['outcomes']['readmission_30d']:.0%} readmitted within 30 days",
    ]
    
    if "adverse_events" in cohort_data["outcomes"]:
        summary_parts.append(
            f"{cohort_data['outcomes']['adverse_events']:.0%} had adverse events"
        )
    
    summary_parts.append(f"Common reasons: {', '.join(cohort_data['common_reasons'][:2])}")
    
    return "\n".join(summary_parts)
