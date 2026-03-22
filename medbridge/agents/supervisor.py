"""
Supervisor Agent

Deterministic orchestrator that routes patient processing through the agent pipeline.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List
from numpy import str_
import pandas as pd


from medbridge.agents.extraction_agent import ExtractionAgent
from medbridge.agents.reconciliation_agent import ReconciliationAgent
from medbridge.agents.clinical_agent import ClinicalReasoningAgent
from medbridge.models.agent_state import RunContext, SupervisorState, RunStatus
from medbridge.models.medication import CanonicalMedication
from medbridge.models.discrepancy import Discrepancy, UrgencyScore
from medbridge.ingestion.csv_loader import get_loader
from medbridge.ingestion.normalizer import normalize_pharmacy_batch
from medbridge.memory.long_term import get_long_term_memory
from medbridge.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SupervisorResult:
    """Result of supervisor pipeline execution."""
    
    def __init__(
        self,
        thread_id: str,
        patient_id: str,
        state: SupervisorState,
        list_a: Optional[List[CanonicalMedication]] = None,
        list_b: Optional[List[CanonicalMedication]] = None,
        list_c: Optional[List[CanonicalMedication]] = None,
        discrepancies: Optional[List[Discrepancy]] = None,
        urgency_scores: Optional[List[UrgencyScore]] = None,
    ):
        self.thread_id = thread_id
        self.patient_id = patient_id
        self.state = state
        self.list_a = list_a or []
        self.list_b = list_b or []
        self.list_c = list_c or []
        self.discrepancies = discrepancies or []
        self.urgency_scores = urgency_scores or []
    
    def __repr__(self) -> str:
        return (
            f"SupervisorResult(thread_id='{self.thread_id}', "
            f"patient_id='{self.patient_id}', "
            f"list_a={len(self.list_a)}, list_b={len(self.list_b)}, list_c={len(self.list_c)}, "
            f"discrepancies={len(self.discrepancies)}, urgency_scores={len(self.urgency_scores)})"
        )


class Supervisor:
    """
    Supervisor Agent - Deterministic Orchestrator.
    
    Routes patient processing through the agent pipeline:
    1. Extraction Agent → List A (discharge meds)
    2. Load Pharmacy Data → List B (pharmacy fills)
    3. Load Self-Report → List C (patient self-report)
    4. Reconciliation Agent → Discrepancies
    5. Clinical Reasoning Agent → Urgency scores
    
    Design: Pure Python orchestration (no LLM). Predictable and testable.
    """
    
    def __init__(self):
        """Initialize Supervisor."""
        self.name = "supervisor"
        self.logger = logging.getLogger(f"medbridge.agents.{self.name}")
        
        # Initialize agents
        self.extraction_agent = ExtractionAgent()
        self.reconciliation_agent = ReconciliationAgent()
        self.clinical_agent = ClinicalReasoningAgent()
        
        # Initialize memory
        self.memory = get_long_term_memory()
        
        self.logger.info("Initialized Supervisor with all agents")
    
    def process_patient(
        self,
        patient_id: str,
        charttime: datetime = None,
        trigger: str = "api",
    ) -> SupervisorResult:
        """
        Process a patient through the full pipeline.
        
        Args:
            patient_id: Patient subject ID
            trigger: What triggered this pipeline (api, celery, manual)
            charttime: Specific discharge date to process (overrides discharge_index)
            
        Returns:
            SupervisorResult: Pipeline execution result
        """
        start_time = time.time()
        charttime_str = pd.Timestamp(charttime).isoformat()
        
        # Create pipeline thread ID
        thread_id = f"proc-{patient_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        # Initialize supervisor state
        state = SupervisorState(
            thread_id=thread_id,
            patient_id=patient_id,
            trigger=trigger,
            status=RunStatus.RUNNING
        )
        
        self.logger.info(
            f"[SupervisorState] INITIALIZED | "
            f"thread_id={thread_id} | "
            f"patient_id={patient_id} | "
            f"trigger={trigger} | "
            f"status={state.status}"
        )
        
        # Supervisor's own run context
        sup_ctx = RunContext(
            thread_id=thread_id,
            agent_name="supervisor",
            patient_id=patient_id,
            metadata={
                "trigger": trigger,
                "charttime": str(charttime) if charttime else None
            }
        )
        sup_ctx.mark_running()
        
        self.logger.info(
            f"Starting patient processing pipeline: patient={patient_id}, "
            f"thread={thread_id}, trigger={trigger}, charttime={charttime}"
        )
        
        try:
            loader = get_loader()

            # If charttime is provided, use it to get specific discharge
            if charttime is not None:
                self.logger.info(f"Using charttime to fetch discharge: {charttime}")
                current_discharge = loader.get_discharge_by_charttime(patient_id, charttime)

                if not current_discharge:
                    raise ValueError(
                        f"No discharge found for patient {patient_id} with charttime {charttime}"
                    )
            
            # Phase 1: Extraction (List A)
            self.logger.info("[SupervisorState] Starting Phase 1: Extraction")
            list_a = self._run_extraction_phase(
                patient_id, thread_id, sup_ctx.run_id, state, current_discharge
            )
            
            # Store List A in memory
            self.memory.store_discharge_meds(f"{patient_id}-{charttime_str}", list_a)
            
            self.logger.info(
                f"[SupervisorState] Phase 1 Complete | "
                f"extraction_completed={state.extraction_completed} | "
                f"list_a_count={state.list_a_count}"
            )
            
            # Phase 2: Load pharmacy data (List B)
            self.logger.info("[SupervisorState] Starting Phase 2: Load Pharmacy Data")
            list_b = self._load_pharmacy_data(patient_id, charttime, state)
            
            # Store List B in memory
            self.memory.store_pharmacy_meds(f"{patient_id}-{charttime_str}", list_b)
            
            self.logger.info(
                f"[SupervisorState] Phase 2 Complete | "
                f"list_b_count={state.list_b_count}"
            )
            
            # Phase 3: List C (patient self-report) - load from memory if exists
            self.logger.info("[SupervisorState] Phase 3: Load List C (self-report)")
            list_c = self.memory.get_reported_meds(f"{patient_id}-{charttime_str}")
            state.list_c_count = len(list_c)
            self.logger.info(
                f"[SupervisorState] Phase 3 Complete | "
                f"list_c_count={state.list_c_count}"
            )
            
            # Phase 4: Reconciliation
            self.logger.info("[SupervisorState] Starting Phase 4: Reconciliation")
            
            
            discrepancies = self._run_reconciliation_phase(
                patient_id, thread_id, sup_ctx.run_id, state,
                charttime_str
            )
            self.logger.info(
                f"[SupervisorState] Phase 4 Complete | "
                f"reconciliation_completed={state.reconciliation_completed} | "
                f"discrepancy_count={state.discrepancy_count}"
            )
            
            # Phase 5: Clinical Reasoning
            self.logger.info("[SupervisorState] Starting Phase 5: Clinical Reasoning")
            urgency_scores = self._run_clinical_phase(
                patient_id, thread_id, sup_ctx.run_id, state, discrepancies
            )
            self.logger.info(
                f"[SupervisorState] Phase 5 Complete | "
                f"clinical_completed={state.clinical_completed}"
            )
            
            # Mark complete
            total_latency = (time.time() - start_time) * 1000
            state.status = RunStatus.COMPLETED
            state.completed_at = datetime.utcnow()
            sup_ctx.mark_completed(latency_ms=total_latency)
            
            self.logger.info(
                f"[SupervisorState] COMPLETED | "
                f"thread_id={thread_id} | "
                f"patient_id={patient_id} | "
                f"status={state.status} | "
                f"extraction_completed={state.extraction_completed} | "
                f"list_a={state.list_a_count} | "
                f"list_b={state.list_b_count} | "
                f"list_c={state.list_c_count} | "
                f"discrepancies={state.discrepancy_count} | "
                f"total_latency={total_latency:.0f}ms"
            )
            
            self.logger.info(
                f"Pipeline completed: patient={patient_id}, thread={thread_id}, "
                # f"list_a={len(list_a)}, list_b={len(list_b)}, "
                f"discrepancies={len(discrepancies)}, "
                f"latency={total_latency:.0f}ms"
            )
            
            return SupervisorResult(
                thread_id=thread_id,
                patient_id=patient_id,
                state=state,
                # list_a=list_a,
                list_b=list_b,
                list_c=list_c,
                discrepancies=discrepancies,
                urgency_scores=urgency_scores
            )
            
        except Exception as e:
            self.logger.error(f"Pipeline failed for patient {patient_id}: {e}", exc_info=True)
            
            state.status = RunStatus.FAILED
            state.error = str(e)
            state.completed_at = datetime.utcnow()
            sup_ctx.mark_failed(str(e))
            
            self.logger.error(
                f"[SupervisorState] FAILED | "
                f"thread_id={thread_id} | "
                f"patient_id={patient_id} | "
                f"status={state.status} | "
                f"error={str(e)}"
            )
            
            raise
    
    def _run_extraction_phase(
        self,
        patient_id: str,
        thread_id: str,
        parent_run_id: str,
        state: SupervisorState,
        discharge_context
    ) -> List[CanonicalMedication]:
        """
        Run extraction phase (List A).
        
        Args:
            patient_id: Patient subject ID
            thread_id: Pipeline thread ID
            parent_run_id: Supervisor run ID
            state: Supervisor state to update
            discharge_context: DischargeContext to extract from
            
        Returns:
            List[CanonicalMedication]: Extracted medications
        """
        self.logger.info(f"Phase 1: Extraction for patient {patient_id}")
        
        if not discharge_context:
            self.logger.error(f"No discharge context provided for patient {patient_id}")
            state.list_a_count = 0
            state.extraction_completed = True
            return []
        
        # Create run context for extraction
        ext_ctx = RunContext(
            thread_id=thread_id,
            parent_run_id=parent_run_id,
            agent_name="extraction",
            patient_id=patient_id
        )
        ext_ctx.mark_running()
        
        # Run extraction agent
        try:
            list_a = self.extraction_agent.run(discharge_context, context=ext_ctx)
            
            # Update state
            state.extraction_completed = True
            state.extraction_run_id = ext_ctx.run_id
            state.list_a_count = len(list_a)
            
            self.logger.info(
                f"[SupervisorState] Extraction phase updated | "
                f"extraction_completed={state.extraction_completed} | "
                f"extraction_run_id={state.extraction_run_id[:8]}... | "
                f"list_a_count={state.list_a_count}"
            )
            self.logger.info(f"Extraction completed: {len(list_a)} medications extracted")
            print("\n\n", list_a, "\n\n")

            return list_a
            
        except Exception as e:
            self.logger.error(f"Extraction phase failed: {e}")
            state.extraction_completed = False
            raise
    
    def _load_pharmacy_data(
        self,
        patient_id: str,
        charttime: datetime,
        state: SupervisorState
    ) -> List[CanonicalMedication]:
        """
        Load pharmacy data (List B).
        
        Args:
            patient_id: Patient subject ID
            charttime: Discharge charttime (datetime)
            state: Supervisor state to update
            
        Returns:
            List[CanonicalMedication]: Pharmacy medications
        """
        self.logger.info(f"Phase 2: Loading pharmacy data for patient {patient_id}")
        
        loader = get_loader()
        # start_date = charttime - timedelta(days=1)
        end_date = charttime + timedelta(days=3)  # 3 days after discharge
        # end_date = pd.Timestamp(datetime.utcnow()).normalize()
        pharmacy_df = loader.get_fills_btw_dates(patient_id, start_date=charttime, end_date=end_date)
        
        if pharmacy_df.empty:
            self.logger.warning(f"No pharmacy data found for patient {patient_id}")
            state.list_b_count = 0
            return []
        
        # Normalize pharmacy data
        list_b = normalize_pharmacy_batch(pharmacy_df)
        
        # Update state
        state.list_b_count = len(list_b)
        
        self.logger.info(
            f"[SupervisorState] Pharmacy phase updated | "
            f"list_b_count={state.list_b_count}"
        )
        self.logger.info(f"Pharmacy data loaded: {len(list_b)} medications")
        print("\n\n", list_b, "\n\n")
        return list_b
    
    def _run_reconciliation_phase(
        self,
        patient_id: str,
        thread_id: str,
        parent_run_id: str,
        state: SupervisorState,
        discharge_date: Optional[str_] = None
    ) -> List[Discrepancy]:
        """
        Run reconciliation phase.
        
        Args:
            patient_id: Patient subject ID
            thread_id: Pipeline thread ID
            parent_run_id: Supervisor run ID
            state: Supervisor state to update
            discharge_date: Current discharge date
            
        Returns:
            List[Discrepancy]: Identified discrepancies
        """
        self.logger.info(f"Phase 4: Reconciliation for patient {patient_id}")
        
        # Create run context for reconciliation
        recon_ctx = RunContext(
            thread_id=thread_id,
            parent_run_id=parent_run_id,
            agent_name="reconciliation",
            patient_id=patient_id,
            metadata={
                "discharge_date": str(discharge_date) if discharge_date else None,
            }
        )
        recon_ctx.mark_running()
        
        # Run reconciliation agent
        try:
            discrepancies = self.reconciliation_agent.run(
                patient_id=patient_id,
                discharge_date=discharge_date,
                context=recon_ctx
            )
            
            # Update state
            state.reconciliation_completed = True
            state.reconciliation_run_id = recon_ctx.run_id
            state.discrepancy_count = len(discrepancies)
            
            self.logger.info(
                f"[SupervisorState] Reconciliation phase updated | "
                f"reconciliation_completed={state.reconciliation_completed} | "
                f"reconciliation_run_id={state.reconciliation_run_id[:8]}... | "
                f"discrepancy_count={state.discrepancy_count}"
            )
            self.logger.info(f"Reconciliation completed: {len(discrepancies)} discrepancies found")
            
            return discrepancies
            
        except Exception as e:
            self.logger.error(f"Reconciliation phase failed: {e}")
            state.reconciliation_completed = False
            raise
    
    def _run_clinical_phase(
        self,
        patient_id: str,
        thread_id: str,
        parent_run_id: str,
        state: SupervisorState,
        discrepancies: List[Discrepancy]
    ) -> List[UrgencyScore]:
        """
        Run clinical reasoning phase.
        
        Args:
            patient_id: Patient subject ID
            thread_id: Pipeline thread ID
            parent_run_id: Supervisor run ID
            state: Supervisor state to update
            discrepancies: Discrepancies to assess
            
        Returns:
            List[UrgencyScore]: Urgency scores
        """
        self.logger.info(f"Phase 5: Clinical Reasoning for patient {patient_id}")
        
        # Create run context for clinical reasoning
        clin_ctx = RunContext(
            thread_id=thread_id,
            parent_run_id=parent_run_id,
            agent_name="clinical",
            patient_id=patient_id
        )
        clin_ctx.mark_running()
        
        # Run clinical agent
        try:
            urgency_scores = self.clinical_agent.run(
                patient_id=patient_id,
                discrepancies=discrepancies,
                patient_context={},
                context=clin_ctx
            )
            
            # Update state
            state.clinical_completed = True
            state.clinical_run_id = clin_ctx.run_id
            
            self.logger.info(
                f"[SupervisorState] Clinical phase updated | "
                f"clinical_completed={state.clinical_completed} | "
                f"clinical_run_id={state.clinical_run_id[:8]}... | "
                f"urgency_scores={len(urgency_scores)}"
            )
            self.logger.info(f"Clinical reasoning completed: {len(urgency_scores)} scores calculated")
            
            return urgency_scores
            
        except Exception as e:
            self.logger.error(f"Clinical phase failed: {e}")
            state.clinical_completed = False
            raise
    
    def process_all_patient_discharges(
        self,
        patient_id: str,
        trigger: str = "api"
    ) -> List[SupervisorResult]:
        """
        Process ALL discharges for a patient.
        
        This processes each discharge separately with its own discharge period,
        allowing proper temporal segmentation of pharmacy fills.
        
        Args:
            patient_id: Patient subject ID
            trigger: What triggered this pipeline
            
        Returns:
            List[SupervisorResult]: Results for each discharge
        """
        loader = get_loader()
        all_discharges = loader.get_all_patient_discharges(patient_id)
        
        if not all_discharges:
            self.logger.error(f"No discharges found for patient {patient_id}")
            return []
        
        self.logger.info(
            f"Processing all {len(all_discharges)} discharges for patient {patient_id}"
        )
        
        results = []
        for i in range(len(all_discharges)):
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Processing discharge {i+1}/{len(all_discharges)}")
            self.logger.info(f"{'='*60}")
            
            try:
                result = self.process_patient(
                    patient_id=patient_id,
                    trigger=trigger,
                    discharge_index=i
                )
                results.append(result)
                
            except Exception as e:
                self.logger.error(f"Failed to process discharge {i+1}: {e}")
                continue
        
        self.logger.info(
            f"\nProcessed {len(results)}/{len(all_discharges)} discharges successfully"
        )
        
        return results
