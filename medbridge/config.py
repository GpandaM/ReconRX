"""
MedBridge Configuration Module

Pydantic-based settings management with environment variable support.
All configuration is loaded from .env file or environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    Environment variables can be prefixed with MEDBRIDGE_ or used directly.
    Example: MEDBRIDGE_REDIS_HOST or REDIS_HOST
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = Field(default="MedBridge", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    environment: str = Field(default="development", description="Environment: development, staging, production")
    
    # Data paths
    data_input_dir: str = Field(default="data/input", description="Input data directory")
    data_eval_dir: str = Field(default="data/eval", description="Evaluation data directory")
    discharge_csv: str = Field(default="data/input/discharge_8000.csv", description="Discharge summary CSV path")
    pharmacy_csv: str = Field(default="data/input/pharmacy_claims_simulated.csv", description="Pharmacy claims CSV path")
    
    # Data cleaning
    anchor_year: int = Field(default=0, description="Number of years to subtract from all dates (e.g., 100 means subtract 100 years)")
    anchor_charttime: str = Field(default="2024-03-01", description="Anchor charttime for data cleaning")

    # Redis configuration (Long-Term and Short-Term Memory)
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_decode_responses: bool = Field(default=True, description="Decode Redis responses to strings")
    
    # Redis TTL settings (in seconds)
    redis_ttl_short_term: int = Field(default=604800, description="Short-term memory TTL (7 days)")
    redis_ttl_long_term: int = Field(default=7776000, description="Long-term memory TTL (90 days)")
    redis_ttl_run_context: int = Field(default=2592000, description="Run context TTL (30 days)")
    redis_ttl_episodic_cache: int = Field(default=86400, description="Episodic cache TTL (24 hours)")
    
    # ChromaDB configuration (Semantic Memory)
    chromadb_host: str = Field(default="localhost", description="ChromaDB host")
    chromadb_port: int = Field(default=8200, description="ChromaDB port")
    chromadb_collection_guidelines: str = Field(default="clinical_guidelines", description="Guidelines collection name")
    chromadb_collection_drugs: str = Field(default="drug_knowledge", description="Drug knowledge collection name")
    chromadb_persist_dir: str = Field(default="data/chromadb", description="ChromaDB persistence directory")
    
    # LLM Router configuration
    llm_primary_provider: str = Field(default="ollama", description="Primary LLM provider: ollama, openai_compat")
    llm_fallback_provider: Optional[str] = Field(default=None, description="Fallback LLM provider")
    
    # Ollama configuration
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama base URL")
    ollama_model: str = Field(default="qwen3.5:4b", description="Ollama model name")
    ollama_timeout: int = Field(default=300, description="Ollama request timeout (seconds)")
    
    # OpenAI-compatible provider configuration (vLLM, TGI, LiteLLM, etc.)
    openai_compat_base_url: Optional[str] = Field(default=None, description="OpenAI-compatible API base URL")
    openai_compat_api_key: Optional[str] = Field(default="dummy", description="API key for OpenAI-compatible endpoint")
    openai_compat_model: str = Field(default="meta-llama/Llama-3.2-3B-Instruct", description="Model name")
    openai_compat_timeout: int = Field(default=120, description="Request timeout (seconds)")
    
    # LLM generation defaults
    llm_temperature: float = Field(default=0.1, description="LLM temperature (lower = more deterministic)")
    llm_max_tokens: int = Field(default=2048, description="Maximum tokens to generate")
    llm_top_p: float = Field(default=0.9, description="Nucleus sampling parameter")
    
    # Agent configuration
    agent_max_react_iterations: int = Field(default=5, description="Maximum ReAct loop iterations")
    agent_working_memory_max_steps: int = Field(default=20, description="Maximum steps in working memory")
    agent_chat_history_window: int = Field(default=20, description="Number of recent messages to keep in chat context")
    
    # Extraction Agent configuration
    extraction_timeout: int = Field(default=60, description="Extraction timeout (seconds)")
    extraction_retry_attempts: int = Field(default=3, description="Number of retry attempts for extraction")
    
    # Reconciliation Agent configuration
    reconciliation_fuzzy_threshold: float = Field(default=0.85, description="Fuzzy matching threshold (0-1)")
    reconciliation_fill_gap_threshold_days: int = Field(default=7, description="Days threshold for fill gap alert")
    
    # Clinical Reasoning Agent configuration
    clinical_urgency_max_score: float = Field(default=10.0, description="Maximum urgency score")
    clinical_time_decay_factor: float = Field(default=0.1, description="Time decay factor for urgency")
    
    # Drug database configuration
    rxnorm_api_url: str = Field(default="https://rxnav.nlm.nih.gov/REST", description="RxNorm API base URL")
    openfda_api_url: str = Field(default="https://api.fda.gov/drug", description="OpenFDA API base URL")
    drug_api_timeout: int = Field(default=10, description="Drug API timeout (seconds)")
    
    # PySpark configuration (Episodic Memory)
    spark_app_name: str = Field(default="MedBridge-Cohort", description="Spark application name")
    spark_master: str = Field(default="local[*]", description="Spark master URL")
    spark_driver_memory: str = Field(default="2g", description="Spark driver memory")
    spark_executor_memory: str = Field(default="2g", description="Spark executor memory")
    
    # Celery configuration
    celery_broker_url: str = Field(default="redis://localhost:6379/1", description="Celery broker URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/1", description="Celery result backend")
    celery_task_serializer: str = Field(default="json", description="Task serializer")
    celery_result_serializer: str = Field(default="json", description="Result serializer")
    celery_accept_content: list[str] = Field(default=["json"], description="Accepted content types")
    celery_timezone: str = Field(default="UTC", description="Celery timezone")
    
    # FastAPI configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_reload: bool = Field(default=True, description="Auto-reload on code changes")
    api_workers: int = Field(default=1, description="Number of API workers")
    
    # Streamlit configuration
    streamlit_port: int = Field(default=8501, description="Streamlit port")
    
    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    log_format: str = Field(default="json", description="Log format: json or text")
    log_file: Optional[str] = Field(default=None, description="Log file path (None = stdout only)")
    
    # Evaluation configuration
    eval_gold_extraction_path: str = Field(default="data/eval/extraction_gold.json", description="Gold standard extraction data")
    eval_gold_discrepancy_path: str = Field(default="data/eval/discrepancy_gold.json", description="Gold standard discrepancy data")
    eval_sample_size: int = Field(default=50, description="Sample size for evaluation")
    
    # Alert thresholds
    alert_threshold_critical: float = Field(default=8.0, description="Critical alert threshold")
    alert_threshold_high: float = Field(default=6.0, description="High alert threshold")
    alert_threshold_medium: float = Field(default=4.0, description="Medium alert threshold")
    alert_threshold_low: float = Field(default=2.0, description="Low alert threshold")
    
    @property
    def redis_url(self) -> str:
        """Construct Redis URL from components."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    @property
    def chromadb_url(self) -> str:
        """Construct ChromaDB URL from components."""
        return f"http://{self.chromadb_host}:{self.chromadb_port}"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the global settings instance.
    
    Returns:
        Settings: The application settings
    """
    return settings
