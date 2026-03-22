"""
MedBridge Ingestion Module

CSV-based data ingestion for discharge summaries and pharmacy claims.
"""

from medbridge.ingestion.csv_loader import (
    load_discharge_summaries,
    load_pharmacy_claims,
    get_patient_discharge,
    get_patient_pharmacy_fills,
)
from medbridge.ingestion.normalizer import (
    normalize_pharmacy_record,
    normalize_pharmacy_batch,
    deduplicate_medications,
)

__all__ = [
    "load_discharge_summaries",
    "load_pharmacy_claims",
    "get_patient_discharge",
    "get_patient_pharmacy_fills",
    "normalize_pharmacy_record",
    "normalize_pharmacy_batch",
    "deduplicate_medications",
]
