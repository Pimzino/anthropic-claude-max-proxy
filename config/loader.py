"""Configuration loader for LLMux

Loads configuration from multiple sources with the following priority:
1. Environment variables (highest priority)
2. .env file
3. Hardcoded defaults (lowest priority)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, List
from dotenv import load_dotenv

# Set up logger for config loader
logger = logging.getLogger(__name__)


class ConfigLoader:
    """Handles loading configuration from various sources"""

    def __init__(self, env_path: Optional[str] = None):
        """Initialize the config loader

        Args:
            env_path: Optional path to .env file.
                     Defaults to '.env' in the current directory.
        """
        self.env_path = Path(env_path) if env_path else Path(".env")
        self._load_env_file()

    def _load_env_file(self):
        """Load environment variables from .env file if it exists"""
        if self.env_path.exists():
            load_dotenv(dotenv_path=self.env_path)
            logger.debug(f"Loaded environment variables from {self.env_path}")
        else:
            logger.debug(f".env file not found at {self.env_path}, using environment variables and defaults only")

    def get(self, env_var: str, default: Any) -> Any:
        """Get a configuration value with priority: env > default

        Args:
            env_var: Environment variable name to check
            default: Default value if not found in environment

        Returns:
            The configuration value from environment or default
        """
        # Check environment variable
        env_value = os.getenv(env_var)
        if env_value is not None:
            # Try to parse as appropriate type
            if isinstance(default, bool):
                return env_value.lower() in ('true', '1', 'yes')
            elif isinstance(default, int):
                try:
                    return int(env_value)
                except ValueError:
                    logger.warning(f"Failed to parse {env_var}={env_value} as int, using default: {default}")
                    return default
            elif isinstance(default, float):
                try:
                    return float(env_value)
                except ValueError:
                    logger.warning(f"Failed to parse {env_var}={env_value} as float, using default: {default}")
                    return default
            return env_value

        # Return default
        # Expand home directory if it's a path
        if isinstance(default, str) and default.startswith("~/"):
            return str(Path(default).expanduser())
        return default


# Create a global instance
_config_loader = None

def get_config_loader() -> ConfigLoader:
    """Get or create the global ConfigLoader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def load_custom_models(models_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load custom models from models.json file

    Args:
        models_path: Optional path to models.json file.
                    Defaults to 'models.json' in the project root directory.

    Returns:
        List of custom model configurations. Returns empty list if file doesn't exist
        or if there's an error loading it.
    """
    if models_path:
        path = Path(models_path)
    else:
        # Use absolute path relative to project root
        # __file__ is config/loader.py, so parent.parent is the project root
        config_dir = Path(__file__).parent  # config/ directory
        project_root = config_dir.parent    # project root
        path = project_root / "models.json"

    # Resolve to absolute path for consistent logging
    path = path.resolve()

    if not path.exists():
        logger.debug(f"Custom models file not found: {path}")
        return []

    try:
        with open(path, 'r') as f:
            data = json.load(f)

        custom_models = data.get("custom_models", [])

        if not isinstance(custom_models, list):
            logger.warning(f"Invalid custom_models format in {path}: expected list, got {type(custom_models)}")
            return []

        # Validate each model has required fields
        validated_models = []
        for idx, model in enumerate(custom_models):
            if not isinstance(model, dict):
                logger.warning(f"Skipping invalid model at index {idx}: not a dictionary")
                continue

            # Check required fields
            required_fields = ["id", "base_url", "api_key"]
            missing_fields = [field for field in required_fields if field not in model]

            if missing_fields:
                logger.warning(f"Skipping model at index {idx}: missing required fields {missing_fields}")
                continue

            # Set defaults for optional fields
            model.setdefault("context_length", 200000)
            model.setdefault("max_completion_tokens", 4096)
            model.setdefault("supports_reasoning", False)
            model.setdefault("owned_by", "custom")

            validated_models.append(model)

        if validated_models:
            model_ids = [m['id'] for m in validated_models]
            logger.info(f"Loaded {len(validated_models)} custom model(s) from {path}: {model_ids}")
        else:
            logger.warning(f"No valid custom models found in {path}")
        return validated_models

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {path}: {e}")
        return []
    except IOError as e:
        logger.error(f"Failed to read {path}: {e}")
        return []
