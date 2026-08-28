
"""
Centralized configuration management for the orchestrator.

This module provides a Pydantic-based configuration class that loads
configuration from YAML files with optional override support.
"""

import os
from pathlib import Path
import yaml
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator, validator

logger = logging.getLogger(__name__)


def load_config_with_override(base_config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file with optional override support.
    
    Args:
        base_config_path: Path to the base configuration file
        
    Returns:
        Dictionary containing the merged configuration
        
    Environment Variables:
        CONFIG_OVERRIDE: If set, specifies the override config file name
                        (e.g., "config-local.yaml" or "config-build.yaml")
    """
    # Load base config
    if not os.path.exists(base_config_path):
        logger.error(f"Base config file not found at {base_config_path}")
        raise FileNotFoundError(f"Base config file not found at {base_config_path}")

    with open(base_config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # Check for override config
    override_file = os.environ.get("CONFIG_OVERRIDE")
    if override_file:
        # Construct override path (same directory as base config)
        base_dir = os.path.dirname(base_config_path)
        override_path = os.path.join(base_dir, override_file)
        
        if os.path.exists(override_path):
            logger.info(f"Loading override config from {override_path}")
            with open(override_path, "r") as f:
                override_config = yaml.safe_load(f)
            
            # Merge override config into base config
            config.update(override_config)
            logger.info(f"Config override applied from {override_file}")
        else:
            logger.warning(f"Override config file not found at {override_path}")
    else:
        logger.info("No config override specified, using base config only")
    
    return config


class OrchestratorConfig(BaseModel):
    """Configuration class for the orchestrator application."""
    
    # LLM Configuration
    llm_port: str = Field(..., description="LLM service endpoint URL")
    llm_name: str = Field(..., description="LLM model name")
    small_llm_name: Optional[str] = Field(
        default=None,
        description=(
            "Optional faster/cheaper model for latency-sensitive front-of-pipeline tasks "
            "(planner routing, retrieval extraction). Falls back to llm_name when unset."
        )
    )
    
    # Service Endpoints
    retriever_port: str = Field(..., description="Search service endpoint")
    memory_base_url: str = Field(..., description="Memory service endpoint")
    safety_base_url: str = Field(..., description="Guardsafety service endpoint")
    
    # Prompts
    routing_prompt: str = Field(..., description="System prompt for routing queries to appropriate agents")
    chatter_prompt: str = Field(..., description="System prompt for general conversation")
    
    # Product Configuration
    categories: List[str] = Field(..., description="List of product categories")
    agent_choices: List[str] = Field(..., description="Available agent types")
    
    # Performance Configuration
    memory_length: int = Field(..., description="Maximum memory length for context (summarization trim threshold, in characters)")
    top_k_retrieve: int = Field(..., description="Number of top results to retrieve")
    multimodal: bool = Field(..., description="Whether multimodal features are enabled")
    chatter_max_tokens: Optional[int] = Field(
        default=None,
        description="max_tokens for the chatter LLM call. Falls back to memory_length when unset (legacy behaviour)."
    )
    
    # Safety Configuration
    unsafe_messages: Dict[str, str] = Field(..., description="Language-keyed messages to display for unsafe content")
    
    @model_validator(mode="before")
    @classmethod
    def compat_legacy_names(cls, values):
        aliases = {
            "memory_port": "memory_base_url",
            "safety_port": "safety_base_url",
        }
        for old_name, new_name in aliases.items():
            if old_name in values:
                values.setdefault(new_name, values.pop(old_name))
        return values

    @validator('llm_port', 'retriever_port', 'memory_base_url', 'safety_base_url')
    def validate_urls(cls, v):
        """Validate that URLs are properly formatted."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError(f"URL must start with http:// or https://: {v}")
        return v
    
    @validator('memory_length')
    def validate_memory_length(cls, v):
        """Validate memory length is positive."""
        if v <= 0:
            raise ValueError("memory_length must be positive")
        return v
    
    @validator('chatter_max_tokens')
    def validate_chatter_max_tokens(cls, v):
        """Validate chatter_max_tokens is positive when explicitly set."""
        if v is not None and v <= 0:
            raise ValueError("chatter_max_tokens must be positive when set")
        return v
    
    @validator('top_k_retrieve')
    def validate_top_k(cls, v):
        """Validate top_k_retrieve is positive."""
        if v <= 0:
            raise ValueError("top_k_retrieve must be positive")
        return v
    
    @validator('categories', 'agent_choices')
    def validate_lists_not_empty(cls, v):
        """Validate that lists are not empty."""
        if not v:
            raise ValueError("List cannot be empty")
        return v
    
    class Config:
        """Pydantic configuration."""
        extra = "forbid"  # Prevent additional fields
        validate_assignment = True  # Validate when attributes are set

def load_config(config_path: Optional[str] = None) -> OrchestratorConfig:
    """
    Load configuration from YAML file with optional override support.
    
    Args:
        config_path: Optional path to config file. If None, uses default path.
        
    Returns:
        OrchestratorConfig: The loaded configuration
        
    Raises:
        FileNotFoundError: If config file is not found
        ValueError: If config validation fails
    """
    if config_path is None:
        config_root = Path(os.environ.get("SHARED_CONFIG_ROOT", "/app/platform/configs"))
        config_path = str(config_root / "orchestrator" / "config.yaml")
    
    # Load raw config data with override support
    config_data = load_config_with_override(config_path)
    
    # Inject the real LLM gateway URL from the environment (LLM_BASE_URL in
    # .env / docker-compose) so tracked YAML configs only carry a neutral
    # placeholder endpoint (http://llm-gateway:8000/v1).
    env_llm_port = os.environ.get("LLM_BASE_URL")
    if env_llm_port:
        config_data["llm_port"] = env_llm_port

    # Allow overriding the small-model routing name from the environment too,
    # so tracked YAML files stay neutral (LLM_NAME / SMALL_LLM_NAME in .env).
    if os.environ.get("SMALL_LLM_NAME"):
        config_data["small_llm_name"] = os.environ["SMALL_LLM_NAME"]
    if os.environ.get("LLM_NAME"):
        config_data["llm_name"] = os.environ["LLM_NAME"]
    
    # Create Pydantic config instance
    try:
        return OrchestratorConfig(**config_data)
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {e}")
