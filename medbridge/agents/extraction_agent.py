"""
Extraction Agent

Extracts structured medication data from discharge summary text using LLM.
"""

import logging
import time
import json
from typing import List, Optional

from medbridge.agents.base_agent import BaseAgent
from medbridge.models.medication import CanonicalMedication, MedSource, DoseForm, Frequency
from medbridge.models.patient import DischargeContext
from medbridge.models.agent_state import RunContext, AgentStep
from medbridge.tools.parse_discharge import extract_section
from medbridge.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ExtractionAgent(BaseAgent):
    """
    Extraction Agent for List A (discharge medications).
    
    Uses LLM with structured output to extract medications from
    unstructured discharge summary text.
    
    Design: Single-shot LLM call with JSON mode. No ReAct loop needed.
    """
    
    def __init__(self):
        """Initialize Extraction Agent."""
        super().__init__(name="extraction")
    
    def run(
        self,
        discharge_context: DischargeContext,
        context: Optional[RunContext] = None
    ) -> List[CanonicalMedication]:
        """
        Extract medications from discharge summary.
        
        Args:
            discharge_context: Discharge context with full text
            context: Run context for traceability (optional)
            
        Returns:
            List[CanonicalMedication]: Extracted medications (List A)
        """
        start_time = time.time()
        steps = []
        
        try:
            # Step 1: Extract medication section using regex
            step_start = time.time()
            med_section = extract_section(
                discharge_context.full_text,
                section="Discharge Medications"
            )
            
            if not med_section:
                self.logger.warning(
                    f"No 'Discharge Medications' section found for patient {discharge_context.subject_id}"
                )
                # Try alternative section name
                med_section = extract_section(
                    discharge_context.full_text,
                    section="Medications on Admission"
                )
            
            if not med_section:
                self.logger.error(
                    f"No medication section found for patient {discharge_context.subject_id}"
                )
                return []
            
            step = AgentStep(
                step_number=1,
                action="extract_section",
                input_data={"section": "Discharge Medications"},
                output_data={"text_length": len(med_section)},
                latency_ms=(time.time() - step_start) * 1000
            )
            steps.append(step)
            self.logger.info(
                f"[AgentStep] Step 1: extract_section | "
                f"latency={step.latency_ms:.0f}ms | "
                f"output_length={len(med_section)} chars"
            )
            
            # Step 2: LLM extraction with structured output
            step_start = time.time()
            prompt = self.load_prompt("extraction.txt", med_section=med_section)
            
            response = self.llm.generate(
                prompt=prompt,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                json_mode=True
            )
            
            step = AgentStep(
                step_number=2,
                action="llm_extraction",
                input_data={"prompt_length": len(prompt)},
                output_data={
                    "tokens_used": response.tokens_used,
                    "model": response.model
                },
                latency_ms=response.latency_ms
            )
            steps.append(step)
            self.logger.info(
                f"[AgentStep] Step 2: llm_extraction | "
                f"latency={step.latency_ms:.0f}ms | "
                f"tokens={response.tokens_used} | "
                f"model={response.model}"
            )
            
            # Step 3: Parse and normalize medications
            step_start = time.time()
            medications = self._parse_llm_response(
                response,
                discharge_context.subject_id,
                discharge_context.storetime or discharge_context.charttime
            )
            
            step = AgentStep(
                step_number=3,
                action="parse_normalize",
                input_data={"raw_response_length": len(response.text)},
                output_data={"medication_count": len(medications)},
                latency_ms=(time.time() - step_start) * 1000
            )
            steps.append(step)
            self.logger.info(
                f"[AgentStep] Step 3: parse_normalize | "
                f"latency={step.latency_ms:.0f}ms | "
                f"medications_extracted={len(medications)}"
            )
            
            total_latency = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"Extracted {len(medications)} medications for patient {discharge_context.subject_id} "
                f"in {total_latency:.0f}ms"
            )
            
            # Update run context if provided
            if context:
                context.mark_completed(
                    latency_ms=total_latency,
                    tokens_used=response.tokens_used
                )
            
            return medications
            
        except Exception as e:
            self.logger.error(f"Extraction failed for patient {discharge_context.subject_id}: {e}", exc_info=True)
            
            if context:
                context.mark_failed(str(e))
            
            raise
    
    def _parse_llm_response(
        self,
        response,
        subject_id: str,
        date
    ) -> List[CanonicalMedication]:
        """
        Parse LLM response and convert to CanonicalMedication objects.
        
        Args:
            response: LLM response with structured output
            subject_id: Patient subject ID
            date: Discharge date (pandas Timestamp or datetime)
            
        Returns:
            List[CanonicalMedication]: Parsed medications
        """
        medications = []
        
        # Get structured output
        if not response.structured_output:
            self.logger.error("No structured output from LLM")
            return []
        
        raw_meds = response.structured_output.get("medications", [])
        
        for raw_med in raw_meds:
            try:
                # Parse dose - clean it first
                dose_raw = raw_med.get("dose")
                dose_clean = self._clean_dose(dose_raw)
                dose_value, dose_unit = self._parse_dose(dose_clean)
                
                # Parse frequency
                frequency = self._parse_frequency(raw_med.get("frequency"))
                
                # Convert date to datetime if it's a pandas Timestamp
                date_clean = self._convert_date(date)
                
                # Create canonical medication
                med = CanonicalMedication(
                    rxnorm_code=None,  # Will be populated by drug lookup tool later
                    ndc=None,
                    drug_name=raw_med.get("drug_name", "Unknown"),
                    drug_name_normalized=raw_med.get("drug_name", "Unknown").lower(),
                    dose=dose_clean,
                    dose_value=dose_value,
                    dose_unit=dose_unit,
                    dose_form=DoseForm.UNKNOWN,  # LLM doesn't always extract form
                    route=raw_med.get("route"),
                    frequency=frequency,
                    quantity=None,
                    source=MedSource.DISCHARGE,
                    original_text=json.dumps(raw_med),
                    date=date_clean,
                    subject_id=subject_id,
                    confidence=0.9,  # LLM extraction has some uncertainty
                )
                
                medications.append(med)
                
            except Exception as e:
                self.logger.warning(f"Failed to parse medication: {raw_med}. Error: {e}")
                continue
        
        return medications
    
    def _clean_dose(self, dose_str: Optional[str]) -> Optional[str]:
        """
        Clean dose string by removing route and frequency.
        
        Examples:
            "40 mg PO DAILY" → "40 mg"
            "15 mL PO TID" → "15 mL"
            "40 mg" → "40 mg"
        """
        if not dose_str:
            return None
        
        import re
        dose_str = str(dose_str).strip()
        
        # Extract just the numeric value and unit (first occurrence)
        # Pattern: number (with optional decimal) + optional space + unit letters
        match = re.match(r'([\d.]+\s*[a-zA-Z]+)', dose_str)
        if match:
            return match.group(1).strip()
        
        return dose_str
    
    def _parse_dose(self, dose_str: Optional[str]) -> tuple[Optional[float], Optional[str]]:
        """Parse dose string into value and unit."""
        if not dose_str:
            return None, None
        
        import re
        dose_str = str(dose_str).strip()
        
        # Pattern: number (with optional decimal) + optional space + unit letters
        match = re.match(r'([\d.]+)\s*([a-zA-Z]+)', dose_str)
        if match:
            try:
                value = float(match.group(1))
                unit = match.group(2)
                return value, unit
            except ValueError:
                pass
        
        return None, None
    
    def _convert_date(self, date):
        """
        Convert date to datetime object.
        
        Handles pandas Timestamp, datetime, or None.
        """
        if date is None:
            return None
        
        # If it's a pandas Timestamp, convert to datetime
        if hasattr(date, 'to_pydatetime'):
            return date.to_pydatetime()
        
        # If it's already a datetime, return as is
        from datetime import datetime
        if isinstance(date, datetime):
            return date
        
        # Try to parse string
        if isinstance(date, str):
            from datetime import datetime
            try:
                return datetime.fromisoformat(date)
            except:
                pass
        
        return None
    
    def _parse_frequency(self, freq_str: Optional[str]) -> Frequency:
        """Parse frequency string to Frequency enum."""
        if not freq_str:
            return Frequency.UNKNOWN
        
        freq_str = freq_str.upper().strip()
        
        # Direct mapping
        freq_mapping = {
            "DAILY": Frequency.DAILY,
            "QD": Frequency.DAILY,
            "BID": Frequency.BID,
            "TID": Frequency.TID,
            "QID": Frequency.QID,
            "QHS": Frequency.QHS,
            "PRN": Frequency.PRN,
            "WEEKLY": Frequency.WEEKLY,
            "MONTHLY": Frequency.MONTHLY,
        }
        
        return freq_mapping.get(freq_str, Frequency.UNKNOWN)
