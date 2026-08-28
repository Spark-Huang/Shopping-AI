"""Helpers for wiring the safety engine to an OpenAI-compatible endpoint.

The base ``platform/configs/safety/config.yml`` declares models with
``engine: openai``. The safety framework requires ``base_url`` and the API
key to be present in each model's parameters, so we inject them at load time
from environment variables (``SAFETY_BASE_URL`` / ``SAFETY_API_KEY``) before
the safety application is constructed.

``apply_endpoint_overrides`` additionally honours ``CONFIG_OVERRIDE``: if the
override YAML (same directory, e.g. ``config-build.yaml``) lists models with a
``base_url`` under ``parameters``, those values win.
"""

import os
import yaml
import logging

logger = logging.getLogger(__name__)

# Neutral placeholder default; the real gateway URL is injected via
# SAFETY_BASE_URL (see .env.example / compose file).
DEFAULT_BASE_URL = "http://llm-gateway:8000/v1"


def _inject_openai_params(config) -> None:
    """Ensure every model carries base_url/api_key for OpenAI-compatible engines."""
    base_url = os.environ.get("SAFETY_BASE_URL", DEFAULT_BASE_URL)
    api_key = os.environ.get("SAFETY_API_KEY", "EMPTY")
    for model in getattr(config, "models", []):
        engine = getattr(model, "engine", "") or ""
        if "openai" not in str(engine):
            continue
        params = getattr(model, "parameters", None)
        if params is None:
            params = {}
        params.setdefault("base_url", base_url)
        params.setdefault("api_key", api_key)
        model.parameters = params


def apply_endpoint_overrides(config, config_dir: str = "/app/platform/configs"):
    """Apply endpoint overrides to the loaded safety configuration.

    Args:
        config: Loaded safety configuration object to modify.
        config_dir: Directory containing config files
    """
    # Always inject OpenAI-compatible endpoint parameters first.
    _inject_openai_params(config)

    override_file = os.environ.get("CONFIG_OVERRIDE")

    if not override_file:
        logger.info("Using default OpenAI-compatible endpoints for safety configuration")
        return

    # Load the override config file to get the base_url values
    override_path = os.path.join(config_dir, override_file)

    if not os.path.exists(override_path):
        logger.warning(f"Safety override config file not found at {override_path}")
        return

    logger.info(f"Loading safety override config from {override_path}")

    with open(override_path, 'r') as f:
        override_config = yaml.safe_load(f)

    # Extract model name and base_url values from the override config
    if 'models' in override_config:
        for model_config in override_config['models']:
            if 'type' in model_config:
                model_type = model_config['type']
                base_url = model_config.get('parameters', {}).get('base_url')
                model_name = model_config.get('model')

                # Update the corresponding model in the safety config
                for model in config.models:
                    if model.type == model_type:
                        if base_url:
                            model.parameters['base_url'] = base_url
                            logger.info(f"Updated {model_type} base_url to {base_url}")
                        # Also honour a model-name override.
                        if model_name:
                            model.model = model_name
                            logger.info(f"Updated {model_type} model to {model_name}")
                        break

    logger.info("Applied endpoint overrides to safety configuration")
