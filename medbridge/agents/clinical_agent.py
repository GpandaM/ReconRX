"""
Clinical Reasoning Agent

Assesses discrepancies and calculates urgency scores using native LLM tool calling.
"""

import logging
import time
from typing import List, Optional, Dict, Any

from medbridge.agents.base_agent import BaseAgent
from medbridge.agents.react_loop import ReActEngine
from medbridge.models.discrepancy import Discrepancy, UrgencyScore, UrgencyLevel
from medbridge.models.agent_state import RunContext
from medbridge.models.react import ReActTrace
from medbridge.memory.long_term import get_long_term_memory
from medbridge.llm.router import get_llm_router
from medbridge.tools.drug_lookup import query_drug_db, get_drug_risk_score
from medbridge.tools.guidelines_search import query_guidelines, search_guidelines_by_drug
from medbridge.tools.cohort_query import query_cohort, get_similar_patient_outcomes
from medbridge.utils.schema_generator import get_schemas_from_registry
from medbridge.tools.submit_assessment import submit_assessment
from medbridge.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class ClinicalReasoningAgent(BaseAgent):
    """
    Clinical Reasoning Agent for discrepancy triage.
    
    Uses native LLM tool calling to reason about discrepancies and calculate urgency scores
    by leveraging multiple tools.
    """
    
    MAX_ITERATIONS = 5
    
    def __init__(self):
        """Initialize Clinical Reasoning Agent."""
        super().__init__(name="clinical")
        self.memory = get_long_term_memory()
        self.llm = get_llm_router()
        
        # Build tool registry including the final submission tool
        self.tool_registry = {
            "query_drug_db": query_drug_db,
            "get_drug_risk_score": get_drug_risk_score,
            "query_guidelines": query_guidelines,
            "search_guidelines_by_drug": search_guidelines_by_drug,
            "query_cohort": query_cohort,
            "get_similar_patient_outcomes": get_similar_patient_outcomes,
            "submit_assessment": submit_assessment,
        }
        
        self.tool_schemas = get_schemas_from_registry(self.tool_registry)

        print("~"*50)
        print(self.tool_schemas[0])
        print("~"*50)

        # Initialize Native Engine
        self.react_engine = ReActEngine(
            llm=self.llm,
            tool_registry=self.tool_registry,
            tool_schemas=self.tool_schemas
        )
    
    def run(
        self,
        patient_id: str,
        discrepancies: List[Discrepancy],
        patient_context: Optional[Dict[str, Any]] = None,
        context: Optional[RunContext] = None
    ) -> List[UrgencyScore]:
        """Assess discrepancies and calculate urgency scores."""
        start_time = time.time()
        all_traces = []
        
        try:
            if not discrepancies:
                self.logger.info(f"No discrepancies to assess for patient {patient_id}")
                if context:
                    context.mark_completed(latency_ms=0)
                return []
            
            self.logger.info(
                f"Starting clinical assessment for patient {patient_id}: "
                f"{len(discrepancies)} discrepancies"
            )
            
            urgency_scores = []
            
            # Process each discrepancy with native tool loop
            for i, discrepancy in enumerate(discrepancies):
                print("*"*50)
                print(discrepancy.model_dump_json(indent=2))
                print("*"*50)
                self.logger.info(
                    f"\n{'='*60}\n"
                    f"Assessing discrepancy {i+1}/{len(discrepancies)}: "
                    f"{discrepancy.drug_name} - {discrepancy.discrepancy_type}\n"
                    f"{'='*60}"
                )
                
                trace = self._assess_discrepancy_with_react(
                    discrepancy=discrepancy,
                    patient_context=patient_context or {},
                    context=context
                )
                
                all_traces.append(trace)
                
                urgency_score = self._parse_urgency_from_trace(discrepancy, trace)
                urgency_scores.append(urgency_score)
                
                discrepancy.urgency_score = urgency_score.score
                discrepancy.urgency_level = urgency_score.level
                discrepancy.clinical_rationale = urgency_score.rationale
                
                self.logger.info(
                    f"Discrepancy {i+1} assessed: "
                    f"Score={urgency_score.score:.1f}, Level={urgency_score.level}, "
                    f"Steps={len(trace.steps)}, Tokens={trace.total_tokens}"
                )
            
            # Store discrepancies with urgency scores in memory
            discrepancies_dict = [disc.model_dump() for disc in discrepancies]
            self.memory.store_discrepancies(patient_id, discrepancies_dict)
            
            total_latency = (time.time() - start_time) * 1000
            total_tokens = sum(trace.total_tokens for trace in all_traces)
            
            self.logger.info(
                f"\nClinical assessment completed for patient {patient_id}:\n"
                f"  - Discrepancies assessed: {len(urgency_scores)}\n"
                f"  - Total ReAct steps: {sum(len(t.steps) for t in all_traces)}\n"
                f"  - Total tokens: {total_tokens}\n"
                f"  - Total latency: {total_latency:.0f}ms\n"
                f"  - Critical: {sum(1 for s in urgency_scores if s.level == 'critical')}\n"
                f"  - High: {sum(1 for s in urgency_scores if s.level == 'high')}\n"
                f"  - Medium: {sum(1 for s in urgency_scores if s.level == 'medium')}\n"
                f"  - Low: {sum(1 for s in urgency_scores if s.level == 'low')}"
            )
            
            if context:
                context.mark_completed(latency_ms=total_latency, tokens_used=total_tokens)
            
            return urgency_scores
            
        except Exception as e:
            self.logger.error(
                f"Clinical assessment failed for patient {patient_id}: {e}",
                exc_info=True
            )
            if context:
                context.mark_failed(str(e))
            raise
    
    def _assess_discrepancy_with_react(
        self,
        discrepancy: Discrepancy,
        patient_context: Dict[str, Any],
        context: Optional[RunContext]
    ) -> ReActTrace:
        """Assess a single discrepancy using the Native Tool Engine."""
        system_prompt = self._build_system_prompt()
        initial_observation = self._build_initial_observation(discrepancy, patient_context)
        
        react_context = RunContext(
            thread_id=context.thread_id if context else f"thread-{discrepancy.patient_id}",
            parent_run_id=context.run_id if context else None,
            agent_name=f"clinical_react_{discrepancy.discrepancy_id[:8]}",
            patient_id=discrepancy.patient_id
        )
        
        # Removed stop_sequences as the engine no longer requires them
        trace = self.react_engine.execute(
            system_prompt=system_prompt,
            initial_observation=initial_observation,
            context=react_context,
            max_iterations=self.MAX_ITERATIONS
        )
        
        return trace
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for native tool usage."""
        return """You are a clinical reasoning agent assessing medication discrepancies.
Your goal is to determine the urgency level and recommended action for each discrepancy.

Reasoning process:
1. Understand the discrepancy type and medication.
2. Use your available tools to look up drug risk classification, search relevant clinical guidelines, and consider similar patient outcomes.
3. Calculate an urgency score based on:
   - Drug risk (high-risk drugs = higher urgency)
   - Discrepancy type (missing meds > dose mismatches > reporting issues)
   - Time factors (longer gaps = higher urgency)
   - Patient context (comorbidities, age)
4. CRITICAL INSTRUCTION: You MUST NOT output your final assessment as plain text. When you are ready to submit your final answer, you are strictly required to call the `submit_assessment` tool."""
    
    def _build_initial_observation(
        self,
        discrepancy: Discrepancy,
        patient_context: Dict[str, Any]
    ) -> str:
        """Build initial observation for ReAct loop."""
        obs_parts = [
            f"DISCREPANCY ASSESSMENT TASK",
            f"",
            f"Patient ID: {discrepancy.patient_id}",
            f"Drug: {discrepancy.drug_name}",
            f"RxNorm Code: {discrepancy.rxnorm_code or 'Unknown'}",
            f"Discrepancy Type: {discrepancy.discrepancy_type}",
            f"",
            f"List Presence:",
            f"  - List A (Discharge): {discrepancy.in_list_a}",
            f"  - List B (Pharmacy): {discrepancy.in_list_b}",
            f"  - List C (Self-report): {discrepancy.in_list_c}",
            f"",
        ]
        
        if discrepancy.list_a_details:
            obs_parts.append(f"List A Details: {discrepancy.list_a_details}")
        if discrepancy.list_b_details:
            obs_parts.append(f"List B Details: {discrepancy.list_b_details}")
        if discrepancy.list_c_details:
            obs_parts.append(f"List C Details: {discrepancy.list_c_details}")
        
        if discrepancy.days_since_discharge is not None:
            obs_parts.append(f"")
            obs_parts.append(f"Days since discharge: {discrepancy.days_since_discharge}")
        
        if discrepancy.fill_gap_days is not None:
            obs_parts.append(f"Fill gap: {discrepancy.fill_gap_days} days")
        
        if patient_context:
            obs_parts.append(f"")
            obs_parts.append(f"Patient Context: {patient_context}")
        
        obs_parts.append(f"")
        obs_parts.append(f"Your task: Assess the clinical urgency of this discrepancy.")
        
        return "\n".join(obs_parts)
    
    def _parse_urgency_from_trace(
        self,
        discrepancy: Discrepancy,
        trace: ReActTrace
    ) -> UrgencyScore:
        """Parse urgency score from the submit_assessment tool call."""
        print("!"*50)
        print(trace.steps)
        print("!"*50)
        # Look for the specific submit_assessment tool call in the final steps
        if trace.steps and trace.steps[-1].action == "submit_assessment":
            action_input = trace.steps[-1].action_input
            
            try:
                score = float(action_input.get("urgency_score", 5.0))
                level = action_input.get("urgency_level", "medium")
                rationale = action_input.get("rationale", trace.final_output)
                recommended_action = action_input.get("recommended_action", "Follow up with patient")
                
                if level not in ["critical", "high", "medium", "low", "info"]:
                    level = self._score_to_level(score)
                
                return UrgencyScore(
                    discrepancy_id=discrepancy.discrepancy_id,
                    score=min(max(score, 0.0), 10.0),
                    level=UrgencyLevel(level),
                    drug_risk_score=self._extract_drug_risk_from_trace(trace),
                    discrepancy_type_score=self._get_discrepancy_type_score(discrepancy.discrepancy_type),
                    time_decay_score=self._calculate_time_score(discrepancy),
                    patient_context_score=1.0,
                    rationale=rationale,
                    recommended_action=recommended_action
                )
                
            except Exception as e:
                logger.warning(f"Failed to parse structured urgency output: {e}")
        
        if trace.final_output and "Assessment submitted" in trace.final_output:
             self.logger.info("Extracting assessment from plain text instead of tool call.")
        
        logger.info("Using fallback heuristic scoring")
        return self._heuristic_urgency_score(discrepancy, trace)
    
    def _score_to_level(self, score: float) -> str:
        """Convert numeric score to urgency level."""
        if score >= settings.alert_threshold_critical: return "critical"
        elif score >= settings.alert_threshold_high: return "high"
        elif score >= settings.alert_threshold_medium: return "medium"
        elif score >= settings.alert_threshold_low: return "low"
        else: return "info"
    
    def _extract_drug_risk_from_trace(self, trace: ReActTrace) -> float:
        """Extract drug risk score from trace steps."""
        for step in trace.steps:
            if step.action in ["query_drug_db", "get_drug_risk_score"]:
                if "high" in step.observation.lower(): return 3.0
                elif "low" in step.observation.lower(): return 1.0
                else: return 2.0
        return 2.0
    
    def _get_discrepancy_type_score(self, discrepancy_type: str) -> float:
        """Get base score for discrepancy type."""
        weights = {
            "missing_in_list_b": 3.0, "dose_value_mismatch": 2.8, "route_mismatch": 2.8,
            "frequency_mismatch": 2.5, "fill_gap": 2.5, "dose_unit_mismatch": 2.5,
            "missing_in_list_a": 2.0, "dose_form_mismatch": 1.8, "missing_in_list_c": 1.5,
            "quantity_mismatch": 1.5,
        }
        return weights.get(discrepancy_type, 2.0)
    
    def _calculate_time_score(self, discrepancy: Discrepancy) -> float:
        """Calculate time-based urgency component."""
        if discrepancy.fill_gap_days is not None:
            gap = discrepancy.fill_gap_days
            if gap <= 7: return 0.5
            elif gap <= 14: return 1.0
            elif gap <= 30: return 1.5
            else: return 2.0
        
        if discrepancy.days_since_discharge is not None:
            days = discrepancy.days_since_discharge
            if days <= 3: return 0.5
            elif days <= 7: return 1.0
            elif days <= 14: return 1.5
            else: return 2.0
        
        return 1.0
    
    def _heuristic_urgency_score(
        self,
        discrepancy: Discrepancy,
        trace: ReActTrace
    ) -> UrgencyScore:
        """Fallback heuristic urgency scoring."""
        drug_risk_score = self._extract_drug_risk_from_trace(trace)
        discrepancy_type_score = self._get_discrepancy_type_score(discrepancy.discrepancy_type)
        time_decay_score = self._calculate_time_score(discrepancy)
        patient_context_score = 1.0
        
        total_score = min(
            drug_risk_score + discrepancy_type_score + time_decay_score + patient_context_score,
            10.0
        )
        
        level = self._score_to_level(total_score)
        
        rationale_parts = [
            f"Drug risk: {drug_risk_score:.1f}/3.0",
            f"Discrepancy type: {discrepancy_type_score:.1f}/3.0",
            f"Time factor: {time_decay_score:.1f}/2.0",
        ]
        
        if trace.steps:
            rationale_parts.append(f"ReAct reasoning: {len(trace.steps)} steps completed")
        
        rationale = "; ".join(rationale_parts)
        
        if level == "critical": action = "IMMEDIATE: Contact patient and prescriber within 1 hour"
        elif level == "high": action = "URGENT: Contact patient within 24 hours"
        elif level == "medium": action = "MODERATE: Follow up within 72 hours"
        elif level == "low": action = "LOW: Monitor, no immediate action required"
        else: action = "INFO: Document in chart"
        
        return UrgencyScore(
            discrepancy_id=discrepancy.discrepancy_id,
            score=total_score,
            level=UrgencyLevel(level),
            drug_risk_score=drug_risk_score,
            discrepancy_type_score=discrepancy_type_score,
            time_decay_score=time_decay_score,
            patient_context_score=patient_context_score,
            rationale=rationale,
            recommended_action=action
        )
