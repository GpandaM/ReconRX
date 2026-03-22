"""
Guidelines Search Tool

Searches clinical guidelines for medication management protocols.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# Simplified guidelines database (V1)
# TODO: Replace with ChromaDB vector search
CLINICAL_GUIDELINES = {
    "anticoagulant_management": {
        "title": "Anticoagulant Management Post-Discharge",
        "content": """
        High-risk medications requiring close monitoring:
        - Warfarin: INR monitoring within 3-5 days post-discharge
        - DOACs (rivaroxaban, apixaban): Ensure patient understands dosing schedule
        - Enoxaparin: Bridge therapy, typically 5-7 days
        
        Critical actions:
        - Verify prescription filled within 24 hours
        - Patient education on bleeding signs
        - Drug interaction screening
        """,
        "keywords": ["warfarin", "rivaroxaban", "apixaban", "enoxaparin", "anticoagulant", "blood thinner"]
    },
    "diabetes_management": {
        "title": "Diabetes Medication Reconciliation",
        "content": """
        Insulin and oral hypoglycemics require careful reconciliation:
        - Insulin: Dose changes common during hospitalization, verify outpatient dose
        - Metformin: May be held during admission, ensure restarted appropriately
        - Sulfonylureas: Risk of hypoglycemia if dose not adjusted
        
        Critical actions:
        - Verify home dose vs discharge dose
        - Check for medication gaps (risk of hyperglycemia)
        - Patient education on hypoglycemia signs
        """,
        "keywords": ["insulin", "metformin", "glipizide", "glyburide", "diabetes", "glucose"]
    },
    "heart_failure_management": {
        "title": "Heart Failure Medication Adherence",
        "content": """
        Core HF medications (guideline-directed medical therapy):
        - Diuretics (furosemide, torsemide): Critical for volume management
        - ACE-I/ARB (lisinopril, losartan): Mortality benefit
        - Beta blockers (metoprolol, carvedilol): Mortality benefit
        - Aldosterone antagonists (spironolactone): For advanced HF
        
        Critical actions:
        - Ensure all GDMT medications filled within 3 days
        - Dose adjustments common, verify outpatient regimen
        - Monitor for medication gaps (risk of decompensation)
        """,
        "keywords": ["furosemide", "torsemide", "lisinopril", "losartan", "metoprolol", "carvedilol", "spironolactone", "heart failure", "hf"]
    },
    "default_reconciliation": {
        "title": "General Medication Reconciliation Protocol",
        "content": """
        Standard approach for all medication discrepancies:
        1. Verify prescription accuracy (dose, frequency, route)
        2. Check pharmacy fill status within 7 days
        3. Patient education on new medications
        4. Assess for drug interactions
        5. Monitor for adverse events
        
        Urgency factors:
        - Medication class (high-risk > medium > low)
        - Time since discharge (longer = more urgent)
        - Patient comorbidities
        - Previous non-adherence history
        """,
        "keywords": ["general", "default", "reconciliation", "medication"]
    }
}


def query_guidelines(query: str, drug_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Search clinical guidelines for medication management protocols.
    
    Args:
        query: Search query (e.g., "anticoagulant management", "dose mismatch protocol")
        drug_name: Drug name to search for (optional)
        
    Returns:
        Dict containing:
        - title: Guideline title
        - content: Guideline content
        - relevance_score: How relevant this guideline is (0-1)
    """
    logger.info(f"Searching guidelines: query='{query}', drug='{drug_name}'")
    
    query_lower = query.lower()
    drug_lower = drug_name.lower() if drug_name else ""
    
    # Find best matching guideline
    best_match = None
    best_score = 0.0
    
    for guideline_id, guideline in CLINICAL_GUIDELINES.items():
        score = 0.0
        
        # Check if query matches keywords
        for keyword in guideline["keywords"]:
            if keyword in query_lower or keyword in drug_lower:
                score += 1.0
        
        # Check if drug name matches
        if drug_lower and drug_lower in guideline["content"].lower():
            score += 2.0
        
        if score > best_score:
            best_score = score
            best_match = guideline
    
    # Default to general reconciliation if no match
    if not best_match or best_score == 0:
        best_match = CLINICAL_GUIDELINES["default_reconciliation"]
        best_score = 0.5
    
    result = {
        "title": best_match["title"],
        "content": best_match["content"],
        "relevance_score": min(best_score / 3.0, 1.0)  # Normalize to 0-1
    }
    
    logger.info(f"Found guideline: {result['title']} (relevance: {result['relevance_score']:.2f})")
    
    return result


def search_guidelines_by_drug(drug_name: str) -> Dict[str, Any]:
    """
    Search guidelines specific to a drug.
    
    Args:
        drug_name: Drug name
        
    Returns:
        Dict containing guideline information
    """
    return query_guidelines(query=f"{drug_name} management", drug_name=drug_name)
