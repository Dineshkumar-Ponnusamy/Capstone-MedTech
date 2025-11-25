"""
Configuration management for the Medical Device Compliance Reviewer.
Loads configuration from config.yaml and environment variables.
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    """Configuration manager for the application."""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize configuration from YAML file and environment variables."""
        self.config_path = config_path
        self._config = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file and environment variables."""
        try:
            # Load YAML config
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
                logger.info(f"Configuration loaded from {self.config_path}")
            else:
                logger.warning(f"Config file not found: {self.config_path}")
                self._config = self._get_default_config()
            
            # Override with environment variables
            self._apply_env_overrides()
            
            logger.info("Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "gemini": {
                "model": "gemini-1.5-flash",
                "temperature": 0.2,
                "max_output_tokens": 4096
            },
            "agents": {
                "max_chunk_size": 8000,
                "parallel_execution": True,
                "timeout_seconds": 60
            },
            "compliance": {
                "human_review_threshold": 0.7,
                "regulatory_standards": [
                    "FDA 21 CFR Part 820",
                    "ISO 13485",
                    "ISO 14971",
                    "ISO 62304",
                    "IEC 62304"
                ]
            },
            "logging": {
                "level": "INFO",
                "file": "logs/compliance_review.log"
            },
            "human_loop": {
                "approval_required": True,
                "default_deadline_hours": 24
            }
        }
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # Gemini API key
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self._config.setdefault("gemini", {})["api_key"] = api_key
            logger.info("Gemini API key loaded from environment")
        
        # Model override
        model = os.getenv("GEMINI_MODEL")
        if model:
            self._config.setdefault("gemini", {})["model"] = model
        
        # Temperature override
        temperature = os.getenv("GEMINI_TEMPERATURE")
        if temperature:
            try:
                self._config.setdefault("gemini", {})["temperature"] = float(temperature)
            except ValueError:
                logger.warning(f"Invalid temperature value: {temperature}")
        
        # Logging level override
        log_level = os.getenv("LOG_LEVEL")
        if log_level:
            self._config.setdefault("logging", {})["level"] = log_level.upper()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_gemini_config(self) -> Dict[str, Any]:
        """Get Gemini configuration."""
        return self.get("gemini", {})
    
    def get_agents_config(self) -> Dict[str, Any]:
        """Get agents configuration."""
        return self.get("agents", {})
    
    def get_compliance_config(self) -> Dict[str, Any]:
        """Get compliance configuration."""
        return self.get("compliance", {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get("logging", {})
    
    def validate_config(self) -> bool:
        """Validate required configuration values."""
        required_keys = [
            "gemini.model",
            "agents.max_chunk_size",
            "agents.timeout_seconds"
        ]
        
        missing_keys = []
        for key in required_keys:
            if self.get(key) is None:
                missing_keys.append(key)
        
        if missing_keys:
            logger.error(f"Missing required configuration: {missing_keys}")
            return False
        
        # Validate Gemini API key
        if not self.get("gemini.api_key"):
            logger.warning("Gemini API key not configured")
            return False
        
        return True


# Global configuration instance
config = Config()