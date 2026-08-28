
"""Runtime compatibility fixes for safety-check LLM calls.

The safety package makes two assumptions about the
OpenAI-compatible gateway used by this deployment that do not hold:

1. ``nemoguardrails.library.content_safety.actions`` hard-codes
   ``llm_params={"temperature": 1e-20, ...}``. ``1e-20`` is not a
   spec-normalised float and the model provider behind the gateway
   rejects such requests outright with ``[400] Provider returned error``.
   The exception surfaces as an ``LLMCallException``, turning every
   call into an HTTP 500, forcing the orchestrator into fail-open behaviour.

2. The non-streaming client (``nemoguardrails.llm.clients.openai_compatible
   .OpenAICompatibleClient._build_payload``) *omits* the ``stream`` key when
   streaming is disabled. The gateway treats a missing ``stream`` key as
   ``stream=true`` and answers ``text/event-stream``, which the JSON-parsing
   non-streaming client cannot decode ("Provider returned non-JSON response
   (status=200, content-type='text/event-stream')").

3. The stock safety tasks cap completions at ``max_tokens: 50``
   (prompts.yml). Reasoning-style models spend hidden reasoning tokens from
   that same budget, so a verdict needing some thought emits no visible
   output at all and the gateway answers 502 "provider returned an empty
   response". Calls carrying the near-zero temperature signature also get
   their completion budget raised to ``MIN_COMPLETION_TOKENS`` (default 512).

``config.py`` loads this module automatically before the app starts serving
traffic.

Why the temperature wrapper patches ``nemoguardrails.actions.llm.utils.llm_call``
(the import source) rather than only ``content_safety.actions.llm_call``
(the importer): during initialisation the ``ActionDispatcher`` re-executes
every library action file through ``importlib.util.spec_from_file_location``
*without* registering it in ``sys.modules``. Each re-executed copy of
``content_safety/actions.py`` re-imports ``llm_call`` from
``nemoguardrails.actions.llm.utils`` and silently restores the original
binding in its own globals -- undoing a patch applied only to the previously
imported module instance. Patching the source module attribute means every
later import (including those fresh copies) resolves to the wrapper. For
belt-and-braces we also rewrite the binding on the already-imported
``content_safety.actions`` instance.

Ordinary temperatures such as topic-safety's ``0.01`` pass through
unchanged; prompts, stop tokens, max tokens and caching behaviour are
untouched. Streaming requests (``payload["stream"] is True``) are likewise
untouched -- only requests that would otherwise omit the ``stream`` key get
an explicit ``"stream": false`` so the gateway answers application/json.
"""

import logging
import os

import nemoguardrails.llm.clients.openai_compatible as _og_client_module
import nemoguardrails.actions.llm.utils as _llm_utils
from nemoguardrails.library.content_safety import (
    actions as _cs_actions,
)

logger = logging.getLogger(__name__)

# Replacement value for non-normalised near-zero temperatures. 0.0 is the
# closest spec-valid value and keeps classification deterministic.
SAFE_TEMPERATURE = float(os.environ.get("CONTENT_SAFETY_TEMPERATURE", "0.0"))

# The stock content-safety tasks render ``max_tokens: 50`` from prompts.yml.
# Reasoning-style models spend hidden reasoning tokens out of that same
# completion budget, so a safety verdict that needs a little thought can burn
# all 50 tokens before emitting any visible JSON -- the gateway then sees an
# empty usable output and answers 502. When we detect a stock classification
# call (via the near-zero temperature signature below) we also raise the
# budget to this floor. Output semantics are unchanged: the task prompt
# instructs the model to emit only the verdict JSON.
MIN_COMPLETION_TOKENS = int(os.environ.get("CONTENT_SAFETY_MAX_TOKENS_FLOOR", "512"))

# Any temperature whose magnitude falls below this threshold is treated as a
# "deterministic" request that the framework code expressed as 1e-20.
_NEAR_ZERO_THRESHOLD = 1e-6

# Marker attribute used to keep repeated safety engine constructions from nesting
# the wrappers multiple times (the shim must stay idempotent).
_PATCH_MARKER = "_content_safety_compat_applied"


def _normalise_temperature(kwargs: dict) -> dict:
    """Return kwargs with a gateway-safe temperature substituted if needed."""
    params = kwargs.get("llm_params")
    if not isinstance(params, dict) or "temperature" not in params:
        return kwargs

    try:
        temp = float(params["temperature"])
    except (TypeError, ValueError):
        return kwargs

    if abs(temp) >= _NEAR_ZERO_THRESHOLD:
        return kwargs

    rewritten = dict(params)
    rewritten["temperature"] = SAFE_TEMPERATURE
    try:
        budget = int(params.get("max_tokens") or 0)
    except (TypeError, ValueError):
        budget = 0
    if 0 < budget < MIN_COMPLETION_TOKENS:
        rewritten["max_tokens"] = MIN_COMPLETION_TOKENS
    patched = dict(kwargs)
    patched["llm_params"] = rewritten
    logger.info(
        "safety_compat | rewrote non-normalised temperature "
        "%r -> %r (max_tokens %r -> %r) for OpenAI-compatible gateway",
        params["temperature"],
        SAFE_TEMPERATURE,
        params.get("max_tokens"),
        rewritten.get("max_tokens"),
    )
    return patched


def _make_wrapper(original):
    """Build an idempotent async wrapper around the given ``llm_call``."""

    async def _patched_llm_call(*args, **kwargs):
        """Delegate to the real ``llm_call`` with normalised parameters."""
        return await original(*args, **_normalise_temperature(kwargs))

    setattr(_patched_llm_call, _PATCH_MARKER, True)
    return _patched_llm_call


def _apply_temperature_fix() -> None:
    """Install the ``llm_call`` temperature wrappers."""
    # 1) Source of truth: any module that imports ``llm_call`` later (the
    #    ActionDispatcher re-executes library action files outside
    #    ``sys.modules``) must resolve the wrapper.
    source_target = getattr(_llm_utils, "llm_call", None)
    if source_target is not None and not getattr(source_target, _PATCH_MARKER, False):
        _llm_utils.llm_call = _make_wrapper(source_target)
        logger.info(
            "safety_compat | active: near-zero temperatures are "
            "rewritten to %s in nemoguardrails.actions.llm.utils.llm_call",
            SAFE_TEMPERATURE,
        )
    elif getattr(source_target, _PATCH_MARKER, False):
        logger.info("safety_compat | already applied, skipping")

    # 2) Belt-and-braces: the already-imported safety actions module,
    #    in case it is not re-executed by the action dispatcher.
    cs_target = getattr(_cs_actions, "llm_call", None)
    if cs_target is not None and not getattr(cs_target, _PATCH_MARKER, False):
        _cs_actions.llm_call = (
            _llm_utils.llm_call
            if getattr(_llm_utils.llm_call, _PATCH_MARKER, False)
            else _make_wrapper(cs_target)
        )


def _apply_stream_default_fix() -> None:
    """Make non-streaming requests explicit about ``stream=false``.

    ``OpenAICompatibleClient.chat_completion`` passes ``stream=False`` as a
    keyword argument, but ``_build_payload`` declares it as a named parameter
    and then only writes ``payload["stream"]`` when it is true -- so the JSON
    payload silently omits the key. Gateways that default a missing
    ``stream`` to true answer with SSE, which the non-streaming client cannot
    parse. We wrap ``_build_payload`` to set an explicit ``"stream": False``
    whenever the caller did not ask for streaming.
    """
    original_build = getattr(_og_client_module.OpenAICompatibleClient, "_build_payload", None)
    if original_build is None or getattr(original_build, _PATCH_MARKER, False):
        return

    def _patched_build_payload(self, model, messages, *, stop=None, stream=False, **kwargs):
        """Delegate with an explicit ``stream`` key for non-streaming calls."""
        payload = original_build(self, model, messages, stop=stop, stream=stream, **kwargs)
        if not stream:
            payload["stream"] = False
        return payload

    setattr(_patched_build_payload, _PATCH_MARKER, True)
    _og_client_module.OpenAICompatibleClient._build_payload = _patched_build_payload
    logger.info("safety_compat | explicit stream=false added to non-streaming safety requests")


def _apply() -> None:
    """Install all compatibility patches (idempotent)."""
    _apply_temperature_fix()
    _apply_stream_default_fix()


_apply()
