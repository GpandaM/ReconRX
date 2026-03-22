"""
CSV Loader Module

Loads discharge summaries and pharmacy claims from CSV files.
Uses pandas for efficient data loading and filtering.
"""

import logging
from pathlib import Path
from typing import Optional, List
import pandas as pd
from datetime import datetime

from medbridge.config import get_settings
from medbridge.models.patient import DischargeContext

logger = logging.getLogger(__name__)
settings = get_settings()

# subject_id = "10048001"

class CSVLoader:
    """
    CSV data loader for MedBridge.
    
    Handles loading and caching of discharge summaries and pharmacy claims.
    """
    
    def __init__(
        self,
        discharge_csv_path: Optional[str] = None,
        pharmacy_csv_path: Optional[str] = None
    ):
        """
        Initialize CSV loader.
        
        Args:
            discharge_csv_path: Path to discharge_8000.csv (defaults to config)
            pharmacy_csv_path: Path to pharmacy_claims_simulated.csv (defaults to config)
        """
        self.discharge_csv_path = Path(discharge_csv_path or settings.discharge_csv)
        self.pharmacy_csv_path = Path(pharmacy_csv_path or settings.pharmacy_csv)
        self.anchor_year = settings.anchor_year
        
        # Lazy-loaded DataFrames
        self._discharge_df: Optional[pd.DataFrame] = None
        self._pharmacy_df: Optional[pd.DataFrame] = None
    
    @property
    def discharge_df(self) -> pd.DataFrame:
        """
        Lazy-load discharge summaries DataFrame.
        
        Returns:
            pd.DataFrame: Discharge summaries data
        """
        if self._discharge_df is None:
            logger.info(f"Loading discharge summaries from {self.discharge_csv_path}")
            self._discharge_df = pd.read_csv(self.discharge_csv_path) #, index_col=0)

            print("\n\n", self._discharge_df.head(), "\n\n")
            
            # Convert date columns to datetime and remove time component
            date_columns = ['charttime', 'storetime']
            for col in date_columns:
                if col in self._discharge_df.columns:
                    self._discharge_df[col] = pd.to_datetime(
                        self._discharge_df[col],
                        errors='coerce'
                    ).dt.normalize()  # Remove time, keep only date
            
                        
            # Anchor dates by adding/subtracting fixed number of years
            # Positive anchor_year = add years (e.g., 38 to shift 1982 -> 2020)
            # Negative anchor_year = subtract years (e.g., -100 to shift 2020 -> 1920)
            # if self.anchor_year != 0 and 'charttime' in self._discharge_df.columns:
            #     # Check min/max years to avoid overflow
            #     min_year = self._discharge_df['charttime'].dt.year.min()
            #     max_year = self._discharge_df['charttime'].dt.year.max()
                
            #     logger.info(
            #         f"Discharge date range before anchoring: {min_year} to {max_year}"
            #     )
                
            #     # Calculate target years
            #     target_min = min_year + self.anchor_year
            #     target_max = max_year + self.anchor_year
                
            #     # Check if operation would cause overflow (pandas year range: ~1677 to ~2262)
            #     if target_min < 1677 or target_max > 2262:
            #         logger.warning(
            #             f"Anchor year {self.anchor_year} would cause overflow "
            #             f"(target range: {target_min} to {target_max}, valid: 1677-2262). "
            #             f"Skipping date anchoring."
            #         )
            #     else:
            #         # Add anchor_year to all date columns
            #         for col in date_columns:
            #             if col in self._discharge_df.columns:
            #                 # Add fixed years using DateOffset to preserve month and day
            #                 self._discharge_df[col] = (
            #                     self._discharge_df[col] + pd.DateOffset(years=self.anchor_year)
            #                 )
            #                 # Remove time component, keep only date
            #                 self._discharge_df[col] = self._discharge_df[col].dt.normalize()
                    
            #         logger.info(
            #             f"Added {self.anchor_year} years to all discharge dates "
            #             f"(month and day preserved). New range: {target_min} to {target_max}"
            #         )
            
            logger.info(f"Loaded {len(self._discharge_df)} discharge summaries")
        
        return self._discharge_df
    
    @property
    def pharmacy_df(self) -> pd.DataFrame:
        """
        Lazy-load pharmacy claims DataFrame.
        
        Returns:
            pd.DataFrame: Pharmacy claims data
        """
        if self._pharmacy_df is None:
            logger.info(f"Loading pharmacy claims from {self.pharmacy_csv_path}")
            self._pharmacy_df = pd.read_csv(self.pharmacy_csv_path)
            
            # Convert date column to datetime and remove time component
            if 'Date' in self._pharmacy_df.columns:
                self._pharmacy_df['Date'] = pd.to_datetime(
                    self._pharmacy_df['Date'],
                    errors='coerce'
                ).dt.normalize()  # Remove time, keep only date
            
            # # Anchor dates by adding/subtracting fixed number of years
            # # Positive anchor_year = add years (e.g., 38 to shift 1982 -> 2020)
            # # Negative anchor_year = subtract years (e.g., -100 to shift 2020 -> 1920)
            # if self.anchor_year != 0 and 'Date' in self._pharmacy_df.columns:
            #     # Check min/max years to avoid overflow
            #     min_year = self._pharmacy_df['Date'].dt.year.min()
            #     max_year = self._pharmacy_df['Date'].dt.year.max()
                
            #     logger.info(
            #         f"Pharmacy date range before anchoring: {min_year} to {max_year}"
            #     )
                
            #     # Calculate target years
            #     target_min = min_year + self.anchor_year
            #     target_max = max_year + self.anchor_year
                
            #     # Check if operation would cause overflow (pandas year range: ~1677 to ~2262)
            #     if target_min < 1677 or target_max > 2262:
            #         logger.warning(
            #             f"Anchor year {self.anchor_year} would cause overflow "
            #             f"(target range: {target_min} to {target_max}, valid: 1677-2262). "
            #             f"Skipping date anchoring."
            #         )
            #     else:
            #         # Add anchor_year to all dates
            #         self._pharmacy_df['Date'] = (
            #             self._pharmacy_df['Date'] + pd.DateOffset(years=self.anchor_year)
            #         )
            #         # Remove time component, keep only date
            #         self._pharmacy_df['Date'] = self._pharmacy_df['Date'].dt.normalize()
                    
            #         logger.info(
            #             f"Added {self.anchor_year} years to all pharmacy dates "
            #             f"(month and day preserved). New range: {target_min} to {target_max}"
            #         )
            
            # Convert RxNorm Code to string (handle leading zeros)
            if 'RxNorm Code' in self._pharmacy_df.columns:
                # Replace NaN with empty string before converting to avoid '000nan'
                self._pharmacy_df['RxNorm Code'] = self._pharmacy_df['RxNorm Code'].fillna('').astype(str)
                # Only apply zfill to non-empty values
                self._pharmacy_df['RxNorm Code'] = self._pharmacy_df['RxNorm Code'].apply(
                    lambda x: x.zfill(6) if x and x != 'nan' else ''
                )
            
            logger.info(f"Loaded {len(self._pharmacy_df)} pharmacy claims")
        
        return self._pharmacy_df
    
    def get_patient_discharge(self, subject_id: str) -> Optional[DischargeContext]:
        """
        Get the most recent discharge summary for a patient.
        
        Args:
            subject_id: Patient subject ID
            
        Returns:
            DischargeContext: Discharge context or None if not found
        """
        patient_discharges = self.discharge_df[
            self.discharge_df['subject_id'].astype(str) == str(subject_id)
        ]
        
        if patient_discharges.empty:
            logger.warning(f"No discharge summary found for patient {subject_id}")
            return None
        
        # Get most recent discharge (highest note_seq or latest storetime)
        if 'charttime' in patient_discharges.columns:
            most_recent = patient_discharges.sort_values('charttime', ascending=False).iloc[0]
        else:
            most_recent = patient_discharges.sort_values('note_seq', ascending=False).iloc[0]
        
        # Convert to DischargeContext
        discharge_context = DischargeContext(
            note_id=most_recent['note_id'],
            subject_id=str(most_recent['subject_id']),
            hadm_id=str(most_recent['hadm_id']),
            note_type=most_recent['note_type'],
            note_seq=int(most_recent['note_seq']),
            charttime=most_recent.get('charttime'),
            storetime=most_recent.get('storetime'),
            full_text=most_recent['text']
        )
        
        logger.info(f"Retrieved discharge summary for patient {subject_id}: {discharge_context.note_id}")
        return discharge_context
    
    def get_all_patient_discharges(self, subject_id: str) -> List[DischargeContext]:
        """
        Get ALL discharge summaries for a patient, sorted by charttime.
        
        Args:
            subject_id: Patient subject ID
            
        Returns:
            List[DischargeContext]: All discharge contexts, sorted by charttime (oldest first)
        """
        patient_discharges = self.discharge_df[
            self.discharge_df['subject_id'].astype(str) == str(subject_id)
        ]
        
        if patient_discharges.empty:
            logger.warning(f"No discharge summaries found for patient {subject_id}")
            return []
        
        # Sort by charttime (oldest first)
        if 'charttime' in patient_discharges.columns:
            patient_discharges = patient_discharges.sort_values('charttime', ascending=True)
        else:
            patient_discharges = patient_discharges.sort_values('note_seq', ascending=True)
        
        # Convert all to DischargeContext
        discharge_contexts = []
        for _, row in patient_discharges.iterrows():
            discharge_context = DischargeContext(
                note_id=row['note_id'],
                subject_id=str(row['subject_id']),
                hadm_id=str(row['hadm_id']),
                note_type=row['note_type'],
                note_seq=int(row['note_seq']),
                charttime=row.get('charttime'),
                storetime=row.get('storetime'),
                full_text=row['text']
            )
            discharge_contexts.append(discharge_context)
        
        logger.info(
            f"Retrieved {len(discharge_contexts)} discharge summaries for patient {subject_id}"
        )
        return discharge_contexts
    
    def get_discharge_by_charttime(
        self,
        subject_id: str,
        charttime: datetime
    ) -> Optional[DischargeContext]:
        """
        Get a specific discharge summary by patient ID and charttime.
        
        Args:
            subject_id: Patient subject ID
            charttime: Discharge charttime (datetime)
            
        Returns:
            DischargeContext: Discharge context or None if not found
        """
        patient_discharges = self.discharge_df[
            self.discharge_df['subject_id'].astype(str) == str(subject_id)
        ]

        print("\n\n", patient_discharges.dtypes, "\n\n")
        print("\n\n", patient_discharges.sort_values(by='charttime', ascending=True).drop_duplicates()[['charttime', 'text']], "\n\n")
        
        if patient_discharges.empty:
            logger.warning(f"No discharge summaries found for patient {subject_id}")
            return None
        
        # Find discharge matching the charttime
        if 'charttime' in patient_discharges.columns:
            matching = patient_discharges[patient_discharges['charttime'] == charttime]
            
            if matching.empty:
                logger.warning(
                    f"No discharge found for patient {subject_id} with charttime {charttime}"
                )
                return None
            if len(matching) > 1:
                logger.warning(
                    f"Multiple discharges found for patient {subject_id} with charttime {charttime}"
                )
                return None
            
            discharge_row = matching.iloc[0]
            logger.info(f"Retrieved discharge for patient {subject_id} at {charttime}: {discharge_row}")
        else:
            logger.error("charttime column not found in discharge data")
            return None
        
        # Convert to DischargeContext
        discharge_context = DischargeContext(
            note_id=discharge_row['note_id'],
            subject_id=str(discharge_row['subject_id']),
            hadm_id=str(discharge_row['hadm_id']),
            note_type=discharge_row['note_type'],
            note_seq=int(discharge_row['note_seq']),
            charttime=discharge_row.get('charttime'),
            storetime=discharge_row.get('storetime'),
            full_text=discharge_row['text']
        )
        
        logger.info(
            f"Retrieved discharge for patient {subject_id} at {charttime}: "
            f"{discharge_context.note_id}"
        )
        return discharge_context
    
    def get_patient_pharmacy_fills(self, subject_id: str) -> pd.DataFrame:
        """
        Get all pharmacy fills for a patient.
        
        Args:
            subject_id: Patient subject ID
            
        Returns:
            pd.DataFrame: Pharmacy fills for the patient
        """
        patient_fills = self.pharmacy_df[
            self.pharmacy_df['subject_id'].astype(str) == str(subject_id)
        ]
        
        logger.info(f"Retrieved {len(patient_fills)} pharmacy fills for patient {subject_id}")
        return patient_fills
    
    def get_fills_btw_dates(self, subject_id: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Get all pharmacy fills for a patient between two dates.
        
        Args:
            subject_id: Patient subject ID
            start_date: Start date (datetime)
            end_date: End date (datetime)
        """

        print("\n\n")
        print("subject_id", subject_id)
        print("start_date", start_date)
        print("end_date", end_date)
        print("\n\n")
        print("\n\n", self.pharmacy_df[
            (self.pharmacy_df['subject_id'].astype(str) == str(subject_id))].sort_values(by='Date', ascending=True)[['Date', 'Case Type']].drop_duplicates(), "\n\n")

        patient_fills = self.pharmacy_df[
            (self.pharmacy_df['subject_id'].astype(str) == str(subject_id))
            & (self.pharmacy_df['Date'] >= start_date)
            & (self.pharmacy_df['Date'] <= end_date)
        ]

        # Sort by date for better readability
        patient_fills = patient_fills.sort_values(by='Date', ascending=True)

        print("\n\n", patient_fills[
            (patient_fills['subject_id'].astype(str) == str(subject_id))].sort_values(by='Date', ascending=True).drop_duplicates(), "\n\n")

        
        logger.info(f"Retrieved {len(patient_fills)} pharmacy fills for patient {subject_id} between {start_date} and {end_date}")
        return patient_fills

    
    def get_common_patient_ids(self) -> List[str]:
        """
        Get list of all unique patient IDs that have both discharge and pharmacy data.
        
        Returns:
            List[str]: List of patient subject IDs
        """
        discharge_patients = set(self.discharge_df['subject_id'].astype(str).unique())
        pharmacy_patients = set(self.pharmacy_df['subject_id'].astype(str).unique())
        
        # Patients with both discharge and pharmacy data
        common_patients = sorted(discharge_patients & pharmacy_patients)
        
        logger.info(
            f"Found {len(common_patients)} patients with both discharge and pharmacy data "
            f"({len(discharge_patients)} with discharge, {len(pharmacy_patients)} with pharmacy)"
        )
        
        return common_patients
    
    def get_discharge_patients(self) -> List[str]:
        """
        Get list of all unique patient IDs in discharge data.
        
        Returns:
            List[str]: List of patient subject IDs
        """
        patients = sorted(self.discharge_df['subject_id'].astype(str).unique())
        logger.info(f"Found {len(patients)} unique patients in discharge data")
        return patients
    
    def get_pharmacy_patients(self) -> List[str]:
        """
        Get list of all unique patient IDs in pharmacy data.
        
        Returns:
            List[str]: List of patient subject IDs
        """
        patients = sorted(self.pharmacy_df['subject_id'].astype(str).unique())
        logger.info(f"Found {len(patients)} unique patients in pharmacy data")
        return patients


# Global loader instance
_loader: Optional[CSVLoader] = None


def get_loader() -> CSVLoader:
    """
    Get the global CSV loader instance (singleton pattern).
    
    Returns:
        CSVLoader: The global loader instance
    """
    global _loader
    if _loader is None:
        _loader = CSVLoader()
    return _loader


# Convenience functions for direct access
def load_discharge_summaries() -> pd.DataFrame:
    """
    Load all discharge summaries.
    
    Returns:
        pd.DataFrame: Discharge summaries data
    """
    return get_loader().discharge_df


def load_pharmacy_claims() -> pd.DataFrame:
    """
    Load all pharmacy claims.
    
    Returns:
        pd.DataFrame: Pharmacy claims data
    """
    return get_loader().pharmacy_df


def get_patient_discharge(subject_id: str) -> Optional[DischargeContext]:
    """
    Get the most recent discharge summary for a patient.
    
    Args:
        subject_id: Patient subject ID
        
    Returns:
        DischargeContext: Discharge context or None if not found
    """
    return get_loader().get_patient_discharge(subject_id)


def get_patient_pharmacy_fills(subject_id: str) -> pd.DataFrame:
    """
    Get all pharmacy fills for a patient.
    
    Args:
        subject_id: Patient subject ID
        
    Returns:
        pd.DataFrame: Pharmacy fills for the patient
    """
    return get_loader().get_patient_pharmacy_fills(subject_id)
