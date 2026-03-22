"""
Drug Lookup Tool

Provides drug information including risk classification, interactions, and adverse events.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# Drug risk classifications (simplified for V1)
# TODO: Replace with actual RxNorm + OpenFDA API calls
DRUG_RISK_DATABASE = {
    # High-risk medications (narrow therapeutic index, critical for outcomes)
    "warfarin": {"risk_class": "high", "reason": "Anticoagulant with narrow therapeutic index"},
    "insulin": {"risk_class": "high", "reason": "Critical for glucose control, risk of hypoglycemia"},
    "digoxin": {"risk_class": "high", "reason": "Narrow therapeutic index, cardiac medication"},
    "phenytoin": {"risk_class": "high", "reason": "Antiepileptic with narrow therapeutic index"},
    "lithium": {"risk_class": "high", "reason": "Mood stabilizer with narrow therapeutic index"},
    "methotrexate": {"risk_class": "high", "reason": "Immunosuppressant, requires monitoring"},
    "enoxaparin": {"risk_class": "high", "reason": "Anticoagulant, bleeding risk"},
    "rivaroxaban": {"risk_class": "high", "reason": "Anticoagulant, bleeding risk"},
    "apixaban": {"risk_class": "high", "reason": "Anticoagulant, bleeding risk"},
    
    # Medium-risk medications (important for symptom control)
    "furosemide": {"risk_class": "medium", "reason": "Diuretic, electrolyte imbalance risk"},
    "lisinopril": {"risk_class": "medium", "reason": "ACE inhibitor for blood pressure"},
    "metoprolol": {"risk_class": "medium", "reason": "Beta blocker for heart rate/BP"},
    "atorvastatin": {"risk_class": "medium", "reason": "Statin for cholesterol"},
    "metformin": {"risk_class": "medium", "reason": "Diabetes medication"},
    "levothyroxine": {"risk_class": "medium", "reason": "Thyroid hormone replacement"},
    "prednisone": {"risk_class": "medium", "reason": "Corticosteroid, requires tapering"},
    "pantoprazole": {"risk_class": "medium", "reason": "Proton pump inhibitor"},
    "citalopram": {"risk_class": "medium", "reason": "SSRI antidepressant"},
    "sertraline": {"risk_class": "medium", "reason": "SSRI antidepressant"},
    
    # Low-risk medications (symptom relief, less critical)
    "acetaminophen": {"risk_class": "low", "reason": "Pain reliever, generally safe"},
    "ibuprofen": {"risk_class": "low", "reason": "NSAID for pain/inflammation"},
    "loratadine": {"risk_class": "low", "reason": "Antihistamine for allergies"},
    "omeprazole": {"risk_class": "low", "reason": "OTC acid reducer"},
    "vitamin d": {"risk_class": "low", "reason": "Vitamin supplement"},
    "calcium": {"risk_class": "low", "reason": "Mineral supplement"},
    "multivitamin": {"risk_class": "low", "reason": "Vitamin supplement"},
}


def query_drug_db(drug_name: str, rxnorm_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Query drug database for risk classification and clinical information.
    
    Args:
        drug_name: Drug name to look up
        rxnorm_code: RxNorm code (optional, for more precise lookup)
        
    Returns:
        Dict containing drug information:
        - risk_class: "high" | "medium" | "low"
        - reason: Clinical rationale for risk classification
        - adverse_events: List of common adverse events (TODO)
        - interactions: List of drug interactions (TODO)
    """
    logger.info(f"Looking up drug: {drug_name} (RxNorm: {rxnorm_code})")
    
    # Normalize drug name for lookup
    drug_key = drug_name.lower().strip()
    
    # Check database
    if drug_key in DRUG_RISK_DATABASE:
        result = DRUG_RISK_DATABASE[drug_key].copy()
        result["drug_name"] = drug_name
        result["found"] = True
        logger.info(f"Found {drug_name}: risk_class={result['risk_class']}")
        return result
    
    # Default for unknown drugs
    logger.warning(f"Drug not found in database: {drug_name}, using default medium risk")
    return {
        "drug_name": drug_name,
        "risk_class": "medium",
        "reason": "Unknown drug, assuming medium risk",
        "found": False
    }


def get_drug_risk_score(drug_name: str, rxnorm_code: Optional[str] = None) -> float:
    """
    Get numeric risk score for a drug (0-3 scale).
    
    Args:
        drug_name: Drug name
        rxnorm_code: RxNorm code (optional)
        
    Returns:
        float: Risk score (0.0 = minimal, 3.0 = critical)
    """
    drug_info = query_drug_db(drug_name, rxnorm_code)
    
    risk_class = drug_info.get("risk_class", "medium")
    
    if risk_class == "high":
        return 3.0
    elif risk_class == "medium":
        return 2.0
    else:  # low
        return 1.0
