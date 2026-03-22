"""
Parse Discharge Tool

Extracts specific sections from discharge summary text using regex patterns.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Common section headers in discharge summaries
SECTION_PATTERNS = {
    "Discharge Medications": [
        r"Discharge Medications?:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"Medications? on Discharge:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"DISCHARGE MEDICATIONS?:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
    ],
    "Medications on Admission": [
        r"Medications? on Admission:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"Admission Medications?:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"ADMISSION MEDICATIONS?:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
    ],
    "Discharge Diagnosis": [
        r"Discharge Diagnos[ie]s:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"DISCHARGE DIAGNOS[IE]S:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
    ],
    "History of Present Illness": [
        r"History of Present Illness:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"HPI:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"HISTORY OF PRESENT ILLNESS:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
    ],
    "Discharge Instructions": [
        r"Discharge Instructions?:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
        r"DISCHARGE INSTRUCTIONS?:?\s*\n(.*?)(?=\n\s*\n[A-Z][a-z]+:|\Z)",
    ],
}


def extract_section(text: str, section: str) -> Optional[str]:
    """
    Extract a specific section from discharge summary text.
    
    Uses regex patterns to find section headers and extract the content
    until the next section or end of document.
    
    Args:
        text: Full discharge summary text
        section: Section name to extract (e.g., "Discharge Medications")
        
    Returns:
        str: Extracted section text, or None if section not found
        
    Examples:
        >>> text = "Discharge Medications:\\n1. Furosemide 40 mg PO DAILY\\n\\nDischarge Diagnosis:\\nHeart Failure"
        >>> extract_section(text, "Discharge Medications")
        "1. Furosemide 40 mg PO DAILY"
    """
    if section not in SECTION_PATTERNS:
        logger.warning(f"Unknown section: {section}. Available sections: {list(SECTION_PATTERNS.keys())}")
        return None
    
    patterns = SECTION_PATTERNS[section]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            extracted = match.group(1).strip()
            logger.info(f"Extracted section '{section}' ({len(extracted)} characters)")
            return extracted
    
    logger.warning(f"Section '{section}' not found in discharge text")
    return None


def extract_all_sections(text: str) -> dict[str, Optional[str]]:
    """
    Extract all known sections from discharge summary text.
    
    Args:
        text: Full discharge summary text
        
    Returns:
        dict: Dictionary mapping section names to extracted text
    """
    sections = {}
    for section_name in SECTION_PATTERNS.keys():
        sections[section_name] = extract_section(text, section_name)
    
    found_count = sum(1 for v in sections.values() if v is not None)
    logger.info(f"Extracted {found_count}/{len(sections)} sections from discharge text")
    
    return sections


def clean_medication_text(text: str) -> str:
    """
    Clean medication section text for better parsing.
    
    Removes extra whitespace, normalizes line breaks, etc.
    
    Args:
        text: Raw medication section text
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Normalize line breaks around numbered lists
    text = re.sub(r'\s*(\d+\.)\s*', r'\n\1 ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def extract_medication_lines(text: str) -> list[str]:
    """
    Extract individual medication lines from medication section text.
    
    Handles numbered lists, bullet points, and plain text.
    
    Args:
        text: Medication section text
        
    Returns:
        list[str]: List of individual medication lines
    """
    if not text:
        return []
    
    lines = []
    
    # Try to split by numbered list items (1., 2., etc.)
    numbered_pattern = r'(\d+\.\s+[^\n]+)'
    matches = re.findall(numbered_pattern, text)
    
    if matches:
        lines = [m.strip() for m in matches]
        logger.info(f"Extracted {len(lines)} medication lines (numbered list)")
        return lines
    
    # Try to split by bullet points
    bullet_pattern = r'([•\-\*]\s+[^\n]+)'
    matches = re.findall(bullet_pattern, text)
    
    if matches:
        lines = [m.strip() for m in matches]
        logger.info(f"Extracted {len(lines)} medication lines (bullet list)")
        return lines
    
    # Fallback: split by newlines
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    logger.info(f"Extracted {len(lines)} medication lines (newline split)")
    
    return lines
