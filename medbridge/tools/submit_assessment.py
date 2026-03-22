from typing import Dict

def submit_assessment(urgency_score: float, urgency_level: str, rationale: str, recommended_action: str) -> Dict[str, str]:
    """
    Call this tool when you have enough information to make your final clinical assessment.
    
    Args:
        urgency_score: 0-10 (0=minimal, 10=critical)
        urgency_level: "critical", "high", "medium", "low", or "info"
        rationale: Clinical reasoning for the score
        recommended_action: What should be done regarding the patient
    """
    return {"status": "success", "message": "Assessment recorded."}
