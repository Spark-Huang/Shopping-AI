import logging
import os
import re
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)
_LOCAL_RULE_CACHE = None


def _local_unsafe_regex() -> re.Pattern[str]:
        """Return the mandatory shared deny pattern set."""
        global _LOCAL_RULE_CACHE
        if _LOCAL_RULE_CACHE is not None:
            return _LOCAL_RULE_CACHE
    
        shared_config_root = os.environ.get("SHARED_CONFIG_ROOT")
        try:
            if shared_config_root:
                patterns_file = Path(shared_config_root) / "orchestrator" / "unsafe_patterns.yaml"
                patterns_text = patterns_file.read_text(encoding="utf-8")
            else:
                config_root = Path(__file__).resolve().parents[3] / "platform" / "configs"
                patterns_file = config_root / "orchestrator" / "unsafe_patterns.yaml"
                patterns_text = patterns_file.read_text(encoding="utf-8")
            payload = yaml.safe_load(patterns_text) or {}
            patterns = payload.get("patterns", [])
            if not isinstance(patterns, list) or not patterns:
                raise ValueError("patterns must be a non-empty list")
            compiled = re.compile(
                "|".join(str(pattern) for pattern in patterns), re.IGNORECASE
            )
        except (OSError, ValueError, yaml.YAMLError, re.error) as exc:
            logger.error("Could not load mandatory unsafe patterns: %s", exc)
            raise
    
        _LOCAL_RULE_CACHE = compiled
        return compiled


def _matches_local_unsafe_rules(text: str) -> bool:
        """Return True when text hits the always-on local danger baseline."""
        if not text:
            return False
        return bool(_local_unsafe_regex().search(text))
