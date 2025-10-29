"""Configuration loader for Anthropic Claude Max Proxy

Loads configuration from multiple sources with the following priority:
1. Environment variables (highest priority)
2. config.json file
3. Hardcoded defaults (lowest priority)
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, List

# Set up logger for config loader
logger = logging.getLogger(__name__)


class ConfigLoader:
    """Handles loading configuration from various sources"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the config loader

        Args:
            config_path: Optional path to config.json file.
                        Defaults to 'config.json' in the current directory.
        """
        self.config_path = Path(config_path) if config_path else Path("config.json")
        self.config_data = self._load_config_file()

    def _load_config_file(self) -> Dict[str, Any]:
        """Load configuration from JSON file if it exists"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load {self.config_path}: {e}")
                return {}
        return {}

    def get(self, env_var: str, config_path: str, default: Any) -> Any:
        """Get a configuration value with priority: env > config.json > default

        Args:
            env_var: Environment variable name to check
            config_path: Dot-separated path in config.json (e.g., "server.port")
            default: Default value if not found elsewhere

        Returns:
            The configuration value from the highest priority source
        """
        # 1. Check environment variable
        env_value = os.getenv(env_var)
        if env_value is not None:
            # Try to parse as appropriate type
            if isinstance(default, bool):
                return env_value.lower() in ('true', '1', 'yes')
            elif isinstance(default, int):
                try:
                    return int(env_value)
                except ValueError:
                    pass
            elif isinstance(default, float):
                try:
                    return float(env_value)
                except ValueError:
                    pass
            return env_value

        # 2. Check config.json
        if self.config_data:
            value = self._get_nested_value(self.config_data, config_path)
            if value is not None:
                # Expand home directory if it's a path
                if isinstance(value, str) and value.startswith("~/"):
                    return str(Path(value).expanduser())
                return value

        # 3. Return default
        # Expand home directory if it's a path
        if isinstance(default, str) and default.startswith("~/"):
            return str(Path(default).expanduser())
        return default

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get a value from nested dictionary using dot notation

        Args:
            data: The dictionary to search
            path: Dot-separated path (e.g., "server.port")

        Returns:
            The value if found, None otherwise
        """
        keys = path.split('.')
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def get_all_config(self) -> Dict[str, Any]:
        """Get the entire loaded configuration"""
        return self.config_data.copy()


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
                    Defaults to 'models.json' in the current directory.

    Returns:
        List of custom model configurations. Returns empty list if file doesn't exist
        or if there's an error loading it.
    """
    path = Path(models_path) if models_path else Path("models.json")

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

        logger.info(f"Loaded {len(validated_models)} custom model(s) from {path}")
        return validated_models

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {path}: {e}")
        return []
    except IOError as e:
        logger.error(f"Failed to read {path}: {e}")
        return []