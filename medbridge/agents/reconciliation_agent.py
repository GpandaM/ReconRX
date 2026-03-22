"""
Reconciliation Agent

Compares medication lists and identifies discrepancies.
"""

import logging
import time
from typing import List, Optional
from datetime import datetime


from medbridge.agents.base_agent import BaseAgent
from medbridge.models.discrepancy import Discrepancy
from medbridge.models.agent_state import RunContext, AgentStep
from medbridge.memory.long_term import get_long_term_memory
from medbridge.tools.diff_med_lists import compare_three_lists

logger = logging.getLogger(__name__)


class ReconciliationAgent(BaseAgent):
    """
    Reconciliation Agent for three-list medication comparison.
    
    Design: Primarily deterministic (exact matching on RxNorm codes).
    Uses LLM only for fuzzy matching when needed (future enhancement).
    """
    
    def __init__(self):
        """Initialize Reconciliation Agent."""
        super().__init__(name="reconciliation")
        self.memory = get_long_term_memory()
    
    def run(
        self,
        patient_id: str,
        discharge_date: Optional[str] = None,
        context: Optional[RunContext] = None
    ) -> List[Discrepancy]:
        """
        Reconcile medication lists for a patient for a specific discharge period.
        
        Args:
            patient_id: Patient subject ID
            discharge_date: Current discharge date (charttime)
            context: Run context for traceability (optional)
            
        Returns:
            List[Discrepancy]: Identified discrepancies for this discharge period
        """
        start_time = time.time()
        steps = []
        
        try:
            # Step 1: Load all three lists from memory
            step_start = time.time()
            
            list_a = self.memory.get_discharge_meds(f"{patient_id}-{discharge_date}")
            list_b = self.memory.get_pharmacy_meds(f"{patient_id}-{discharge_date}")
            list_c = self.memory.get_reported_meds(f"{patient_id}-{discharge_date}")
            
            step = AgentStep(
                step_number=1,
                action="load_medication_lists",
                input_data={"patient_id": patient_id},
                output_data={
                    "list_a_count": len(list_a),
                    "list_b_count": len(list_b),
                    "list_c_count": len(list_c)
                },
                latency_ms=(time.time() - step_start) * 1000
            )
            steps.append(step)
            self.logger.info(
                f"[AgentStep] Step 1: load_medication_lists | "
                f"latency={step.latency_ms:.0f}ms | "
                f"list_a={len(list_a)}, list_b={len(list_b)}, list_c={len(list_c)}"
            )
            
            # Step 2: Deterministic comparison
            step_start = time.time()
            
            # Use provided discharge date or infer from List A
            if not discharge_date and list_a and list_a[0].date:
                discharge_date = list_a[0].date

            discrepancies = compare_three_lists(
                list_a=list_a,
                list_b=list_b,
                list_c=list_c,
                patient_id=patient_id,
                discharge_date=discharge_date
            )
            
            step = AgentStep(
                step_number=2,
                action="compare_lists",
                input_data={
                    "list_a_count": len(list_a),
                    "list_b_count": len(list_b),
                    "list_c_count": len(list_c)
                },
                output_data={"discrepancy_count": len(discrepancies)},
                latency_ms=(time.time() - step_start) * 1000
            )
            steps.append(step)
            self.logger.info(
                f"[AgentStep] Step 2: compare_lists | "
                f"latency={step.latency_ms:.0f}ms | "
                f"discrepancies_found={len(discrepancies)}"
            )
            
            # Step 3: Store discrepancies in memory
            step_start = time.time()
            
            discrepancies_dict = [disc.model_dump() for disc in discrepancies]
            self.memory.store_discrepancies(f"{patient_id}-{discharge_date}", discrepancies_dict)
            
            step = AgentStep(
                step_number=3,
                action="store_discrepancies",
                input_data={"discrepancy_count": len(discrepancies)},
                output_data={"stored": True},
                latency_ms=(time.time() - step_start) * 1000
            )
            steps.append(step)
            self.logger.info(
                f"[AgentStep] Step 3: store_discrepancies | "
                f"latency={step.latency_ms:.0f}ms | "
                f"stored={len(discrepancies)} discrepancies"
            )
            
            ## TODO: Step 4: Fuzzy matching with LLM (future enhancement)
            # For unmatched medications, use LLM to detect brand/generic equivalents
            
            total_latency = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"Reconciliation completed for patient {patient_id}: "
                f"{len(discrepancies)} discrepancies found in {total_latency:.0f}ms"
            )
            
            # Update run context if provided
            if context:
                context.mark_completed(latency_ms=total_latency)
            
            return discrepancies
            
        except Exception as e:
            self.logger.error(
                f"Reconciliation failed for patient {patient_id}: {e}",
                exc_info=True
            )
            
            if context:
                context.mark_failed(str(e))
            
            raise
