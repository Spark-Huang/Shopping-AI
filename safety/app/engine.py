from nemoguardrails import RailsConfig, LLMRails
import logging
import os
from pathlib import Path

from .endpoint_overrides import apply_endpoint_overrides

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class ContentSafetyBase:
    async def call_input_safety(self, user_input: str):
        pass

    async def call_output_safety(self, bot_response: str):
        pass


class ContentSafety(ContentSafetyBase):
    def __init__(self, config_path: str):
        # Load the base configuration
        self.config = RailsConfig.from_path(config_path)
        # Keep the tracked configuration vocabulary service-neutral while
        # preserving the runtime key expected by the safety package.
        safety_policy = getattr(self.config, "safety", None)
        if safety_policy and not getattr(self.config, "rails", None):
            self.config.rails = safety_policy

        # Inject environment endpoints and apply an optional explicit override.
        apply_endpoint_overrides(self.config, config_path)

        # Initialize the safety application with the modified configuration.
        self.app = LLMRails(self.config)

    async def call_input_safety(self, user_input: str):
        """Run only the input rails for a user message."""
        options = {"rails": ["input"]}
        messages = [{"role": "user", "content": user_input}]
        return await self.app.generate_async(messages=messages, options=options)

    async def call_output_safety(self, bot_response: str):
        """Run only the output rails for an assistant response."""
        options = {"rails": ["output"]}
        messages = [{"role": "user", "content": ""}, {"role": "assistant", "content": bot_response}]
        return await self.app.generate_async(messages=messages, options=options)


# Load configuration
config_path = Path(
    os.environ.get("SHARED_CONFIG_ROOT", "/app/platform/configs"), "safety"
).as_posix()
_content_safety = ContentSafety(config_path)


class SafetyEngineFactory:
    def create(self) -> ContentSafety:
        return _content_safety
