"""Shared LLM request extras.

`chat_template_kwargs` is a vLLM-only extension used to toggle Qwen3-style
thinking mode. Hosted OpenAI-compatible gateways (openai-next, zhipu, ...)
reject it with HTTP 400, so it is only sent when LLM_VLLM_THINKING_KWARGS=1.
"""

import os


def no_thinking_extra_body() -> dict:
    """vLLM-only payload disabling model thinking; empty on hosted gateways."""
    if os.environ.get("LLM_VLLM_THINKING_KWARGS"):
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}
