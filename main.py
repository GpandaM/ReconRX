"""
MedBridge CLI Entry Point

Run agent pipelines from the command line.

Usage:
    python main.py supervisor --patient-id 10048001
    python main.py extraction --patient-id 11185694
    python main.py memory
    python main.py all
"""

import argparse
import logging
import sys
from datetime import datetime

import pandas as pd

from medbridge.config import get_settings
from medbridge.models.medication import CanonicalMedication, MedSource
from medbridge.agents import Supervisor, ExtractionAgent
from medbridge.ingestion.csv_loader import get_loader
from medbridge.memory import get_long_term_memory


def setup_logging(log_level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )
    return logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual pipeline runners
# ---------------------------------------------------------------------------

def run_supervisor(patient_id: str, charttime_str: str, logger: logging.Logger) -> None:
    """Run the full Supervisor pipeline for a single patient."""
    logger.info("=" * 60)
    logger.info("PIPELINE: Full Supervisor")
    logger.info("=" * 60)

    charttime = pd.to_datetime(charttime_str).normalize()
    logger.info(f"Patient:   {patient_id}")
    logger.info(f"Charttime: {charttime}")

    supervisor = Supervisor()
    result = supervisor.process_patient(
        patient_id=patient_id,
        charttime=charttime,
        trigger="cli",
    )

    logger.info("\n" + "=" * 60)
    logger.info("RESULTS")
    logger.info("=" * 60)
    logger.info(f"Thread ID:  {result.thread_id}")
    logger.info(f"Patient ID: {result.patient_id}")
    logger.info(f"Status:     {result.state.status}")
    logger.info(f"List A (Discharge):   {len(result.list_a)} medications")
    logger.info(f"List B (Pharmacy):    {len(result.list_b)} medications")
    logger.info(f"List C (Self-report): {len(result.list_c)} medications")
    logger.info(f"Discrepancies:        {len(result.discrepancies)}")
    logger.info(f"Urgency Scores:       {len(result.urgency_scores)}")

    if result.list_a:
        logger.info("\n--- List A (Extracted from Discharge) ---")
        for i, med in enumerate(result.list_a[:5], 1):
            logger.info(
                f"{i}. {med.drug_name} {med.dose or ''} "
                f"{med.route or ''} {med.frequency or ''}"
                f"{med.date or ''}"
            )
        if len(result.list_a) > 5:
            logger.info(f"... and {len(result.list_a) - 5} more")

    if result.list_b:
        logger.info("\n--- List B (Pharmacy Claims) ---")
        for i, med in enumerate(result.list_b[:5], 1):
            logger.info(
                f"{i}. {med.drug_name} {med.dose or ''} "
                f"(RxNorm: {med.rxnorm_code}, NDC: {med.ndc})"
                f"{med.date or ''}"
            )
        if len(result.list_b) > 5:
            logger.info(f"... and {len(result.list_b) - 5} more")

    if result.discrepancies:
        logger.info("\n--- Discrepancies ---")
        for i, disc in enumerate(result.discrepancies[:5], 1):
            logger.info(
                f"{i}. {disc.drug_name} - {disc.discrepancy_type} | "
                f"Urgency: {disc.urgency_score:.1f} ({disc.urgency_level})"
            )
        if len(result.discrepancies) > 5:
            logger.info(f"... and {len(result.discrepancies) - 5} more")

    if result.urgency_scores:
        logger.info("\n--- Urgency Distribution ---")
        critical = sum(1 for s in result.urgency_scores if s.level == "critical")
        high     = sum(1 for s in result.urgency_scores if s.level == "high")
        medium   = sum(1 for s in result.urgency_scores if s.level == "medium")
        low      = sum(1 for s in result.urgency_scores if s.level == "low")
        logger.info(f"Critical: {critical}, High: {high}, Medium: {medium}, Low: {low}")

    logger.info("\n--- Pipeline State ---")
    logger.info(f"Extraction completed:     {result.state.extraction_completed}")
    logger.info(f"Reconciliation completed: {result.state.reconciliation_completed}")
    logger.info(f"Clinical completed:       {result.state.clinical_completed}")
    logger.info(f"Started at:               {result.state.started_at}")
    logger.info(f"Completed at:             {result.state.completed_at}")

    logger.info("\n" + "=" * 60)
    logger.info("SUPERVISOR PIPELINE COMPLETED")
    logger.info("=" * 60)


def run_extraction(patient_id: str, charttime_str: str, logger: logging.Logger) -> None:
    """Run the Extraction Agent for a single patient."""
    logger.info("=" * 60)
    logger.info("PIPELINE: Extraction Agent")
    logger.info("=" * 60)

    loader = get_loader()
    discharge_context = loader.get_discharge_by_charttime(patient_id, charttime_str)
    if not discharge_context:
        logger.error(f"No discharge context found for patient {patient_id}")
        return

    logger.info(f"Discharge context: {discharge_context}")

    extraction_agent = ExtractionAgent()
    result = extraction_agent.run(discharge_context=discharge_context)
    logger.info(f"Result: {result}")

    logger.info("\n" + "=" * 60)
    logger.info("EXTRACTION PIPELINE COMPLETED")
    logger.info("=" * 60)


def run_memory(logger: logging.Logger) -> None:
    """Run the Memory Layer (Redis) smoke test."""
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE: Memory Layer (Redis)")
    logger.info("=" * 60)

    memory = get_long_term_memory()

    logger.info("\n--- Health Check ---")
    is_healthy = memory.health_check()
    logger.info(f"Redis health check: {'PASS' if is_healthy else 'FAIL'}")

    if not is_healthy:
        logger.error("Redis is not accessible — skipping remaining memory checks")
        return

    logger.info("\n--- Basic Operations ---")
    test_key = "test:memory:key"
    test_value = {"test": "data", "timestamp": str(datetime.utcnow())}

    logger.info(f"Set:    {'PASS' if memory.set(test_key, test_value, ttl=60) else 'FAIL'}")
    logger.info(f"Exists: {'PASS' if memory.exists(test_key) else 'FAIL'}")
    logger.info(f"Get:    {'PASS' if memory.get(test_key) == test_value else 'FAIL'}")
    logger.info(f"Delete: {'PASS' if memory.delete(test_key) else 'FAIL'}")
    logger.info(f"Gone:   {'PASS' if not memory.exists(test_key) else 'FAIL'}")

    logger.info("\n--- Medication List Storage ---")
    pid = "test_patient_123"
    test_meds = [
        CanonicalMedication(
            source=MedSource.SIMULATED,
            drug_name="Aspirin",
            dose="81mg",
            route="PO",
            frequency="DAILY",
            rxnorm_code="1191",
            subject_id=pid,
        ),
        CanonicalMedication(
            source=MedSource.SIMULATED,
            drug_name="Lisinopril",
            dose="10mg",
            route="PO",
            frequency="BID",
            rxnorm_code="104383",
            subject_id=pid,
        ),
    ]

    for label, store_fn, get_fn in [
        ("List A (discharge)", memory.store_discharge_meds, memory.get_discharge_meds),
        ("List B (pharmacy)",  memory.store_pharmacy_meds,  memory.get_pharmacy_meds),
        ("List C (reported)",  memory.store_reported_meds,  memory.get_reported_meds),
    ]:
        stored = store_fn(pid, test_meds)
        retrieved = get_fn(pid)
        logger.info(
            f"Store {label}: {'PASS' if stored else 'FAIL'}  |  "
            f"Retrieve: {'PASS' if len(retrieved) == 2 else 'FAIL'} ({len(retrieved)} meds)"
        )

    for suffix in ("discharge_meds", "pharmacy_meds", "reported_meds"):
        memory.delete(f"patient:{pid}:{suffix}")

    logger.info("\n" + "=" * 60)
    logger.info("MEMORY PIPELINE COMPLETED")
    logger.info("=" * 60)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser(settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medbridge",
        description="MedBridge — medication reconciliation pipeline CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- supervisor ---
    sup = subparsers.add_parser("supervisor", help="Run the full Supervisor pipeline")
    sup.add_argument(
        "--patient-id",
        default="10048001",
        help="Patient subject_id to process",
    )
    sup.add_argument(
        "--charttime",
        default=settings.anchor_charttime,
        help="Charttime string (YYYY-MM-DD or full ISO timestamp)",
    )

    # --- extraction ---
    ext = subparsers.add_parser("extraction", help="Run the Extraction Agent only")
    ext.add_argument(
        "--patient-id",
        default="11185694",
        help="Patient subject_id to process",
    )
    ext.add_argument(
        "--charttime",
        default=settings.anchor_charttime,
        help="Charttime string (YYYY-MM-DD or full ISO timestamp)",
    )

    # --- memory ---
    subparsers.add_parser("memory", help="Smoke-test the Redis memory layer")

    # --- all ---
    all_p = subparsers.add_parser("all", help="Run supervisor + memory checks")
    all_p.add_argument(
        "--patient-id",
        default="10048001",
        help="Patient subject_id for the supervisor run",
    )
    all_p.add_argument(
        "--charttime",
        default=settings.anchor_charttime,
        help="Charttime string for the supervisor run",
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    settings = get_settings()
    parser = build_parser(settings)
    args = parser.parse_args()

    logger = setup_logging(args.log_level)
    logger.info(f"MedBridge CLI — command: {args.command}")

    try:
        if args.command == "supervisor":
            run_supervisor(args.patient_id, args.charttime, logger)

        elif args.command == "extraction":
            run_extraction(args.patient_id, args.charttime, logger)

        elif args.command == "memory":
            run_memory(logger)

        elif args.command == "all":
            run_supervisor(args.patient_id, args.charttime, logger)
            run_memory(logger)

    except Exception as exc:
        logger.error(f"Pipeline failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
