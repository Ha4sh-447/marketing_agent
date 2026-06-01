"""
LLM wrapper with multi-provider fallback.

Fallback chain per role (tried in order):
  1. OpenRouter primary model
  2. OpenRouter secondary model  (different model, same provider)
  3. Groq                        (completely separate provider, very fast)

On a 429 from any entry the offending (provider, model) is put in a
cooldown (honoring the Retry-After header if present) and the next entry
is tried immediately — the openai SDK's built-in retry is disabled
(max_retries=0) so we never sit idle waiting for a provider that has
already rate-limited us.

On a 401 the client cache is cleared so the next call re-reads the API
key from os.environ (picks up .env changes without a server restart).
"""

import os
import re
import time
import logging
from openai import AsyncOpenAI, RateLimitError, AuthenticationError

from src.config import (
    OPENROUTER_BASE_URL,
    GROQ_BASE_URL,
    PLANNER_MODEL,
    GENERATOR_MODEL,
    EVALUATOR_MODEL,
    PLANNER_MODEL_FALLBACK,
    GENERATOR_MODEL_FALLBACK,
    EVALUATOR_MODEL_FALLBACK,
    PLANNER_GROQ_MODEL,
    GENERATOR_GROQ_MODEL,
    EVALUATOR_GROQ_MODEL,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reasoning-tag stripper
# ---------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_THINK_UNCLOSED_RE = re.compile(r"<think>.*", re.DOTALL)


def _strip_reasoning(text: str) -> str:
    """
    Remove <think>...</think> blocks from reasoning-model output.

    Handles:
      - Complete tags: <think>internal reasoning</think>actual answer
      - Unclosed tags: <think>reasoning that never closes...
      - Multiple think blocks
    """
    text = _THINK_RE.sub("", text)
    text = _THINK_UNCLOSED_RE.sub("", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Client pool  (keyed by provider; cleared on auth failure so it self-heals)
# ---------------------------------------------------------------------------

_clients: dict[str, AsyncOpenAI] = {}


def _get_client(provider: str) -> AsyncOpenAI:
    """
    Return a cached AsyncOpenAI client for `provider`.

    The API key is read fresh from os.environ on every call so that a
    live .env edit + uvicorn hot-reload is picked up without a full
    server restart. If the key changed since the client was built, the
    old client is evicted and a new one is created.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    api_key = (
        os.environ.get("GROQ_API_KEY", "")
        if provider == "groq"
        else os.environ.get("OPENROUTER_API_KEY", "")
    )
    base_url = GROQ_BASE_URL if provider == "groq" else OPENROUTER_BASE_URL

    # Evict cached client if the key has changed
    existing = _clients.get(provider)
    if existing is not None and existing.api_key != api_key:
        logger.info("API key changed for %s — recreating client", provider)
        del _clients[provider]

    if provider not in _clients:
        _clients[provider] = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "no-key-set",
            max_retries=0,  # We manage retries ourselves
        )
        logger.info("Created new client for %s", provider)

    return _clients[provider]


# ---------------------------------------------------------------------------
# Per-model cooldown tracker
# key = "provider:model", value = monotonic time when cooldown expires
# ---------------------------------------------------------------------------

_cooldowns: dict[str, float] = {}
_DEFAULT_COOLDOWN_SECONDS = 60


def _is_cooling(provider: str, model: str) -> bool:
    return time.monotonic() < _cooldowns.get(f"{provider}:{model}", 0)


def _set_cooldown(provider: str, model: str, seconds: int | None = None) -> None:
    cooldown = seconds if seconds and seconds > 0 else _DEFAULT_COOLDOWN_SECONDS
    _cooldowns[f"{provider}:{model}"] = time.monotonic() + cooldown
    logger.warning(
        "Rate-limited on %s/%s — cooling down for %ds",
        provider, model, cooldown,
    )


def _extract_retry_after_seconds(exc: Exception) -> int | None:
    """
    Try to read Retry-After seconds from an API error.
    Supports OpenAI-style response headers, string-encoded metadata,
    and OpenRouter's nested metadata.headers / metadata.retry_after_seconds.
    """
    # 1. Top-level HTTP response headers (standard OpenAI path)
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers:
            retry_after = headers.get("Retry-After") or headers.get("retry-after")
            if retry_after:
                try:
                    return int(float(retry_after))
                except ValueError:
                    pass

    # 2. OpenRouter nested body: error.metadata.retry_after_seconds
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        retry = (
            body.get("error", {})
                .get("metadata", {})
                .get("retry_after_seconds")
        )
        if retry is not None:
            try:
                return int(float(retry))
            except (ValueError, TypeError):
                pass

        # 3. OpenRouter nested body: error.metadata.headers.Retry-After
        nested_headers = (
            body.get("error", {})
                .get("metadata", {})
                .get("headers", {})
        )
        retry_after = nested_headers.get("Retry-After") or nested_headers.get("retry-after")
        if retry_after:
            try:
                return int(float(retry_after))
            except (ValueError, TypeError):
                pass

    # 4. Fallback: parse known patterns in string payloads
    text = str(exc)
    match = re.search(r"retry_after_seconds(?:_raw)?['\"]?:\s*([0-9.]+)", text)
    if match:
        try:
            return int(float(match.group(1)))
        except ValueError:
            return None

    match = re.search(r"Retry-After['\"]?:\s*([0-9.]+)", text, re.IGNORECASE)
    if match:
        try:
            return int(float(match.group(1)))
        except ValueError:
            return None

    return None


# ---------------------------------------------------------------------------
# Fallback chains
# Each entry: (provider, model, extra_headers)
#
# Design principles:
#   PLANNER:   large models (31B-120B) — runs once, quality matters most.
#              Groq slot uses llama-3.3-70b-versatile (dedicated to planner only).
#
#   GENERATOR: medium models (8B-24B) — runs 2-3x per post, throughput matters.
#              Medium models have 3-5x higher free RPM than 70B+.
#              Groq slot uses llama-3.1-8b-instant (separate bucket from planner).
#
#   EVALUATOR: large models (70B-120B) — analytical judgment degrades below 70B.
#              Groq slot uses openai/gpt-oss-120b (separate bucket from planner's
#              llama-3.3-70b-versatile so they don't compete).
#              Medium models kept as absolute last resort only.
#
# Provider diversity per chain: each consecutive entry hits a different
# provider or model-size bucket so their rate limits are independent.
# ---------------------------------------------------------------------------

_OR_HEADERS = {
    "HTTP-Referer": "https://github.com/marketing-agent",
    "X-Title": "Marketing Agent",
}


def _build_chains() -> dict[str, list[tuple[str, str, dict]]]:
    return {
        # ------------------------------------------------------------------
        # PLANNER — once per campaign, quality > speed
        # ------------------------------------------------------------------
        "planner": [
            ("openrouter", PLANNER_MODEL,                             _OR_HEADERS),  # Gemma-4 31B         (OpenRouter)
            ("openrouter", PLANNER_MODEL_FALLBACK,                    _OR_HEADERS),  # GPT-OSS 120B        (OpenRouter, strong reasoning)
            ("groq",       PLANNER_GROQ_MODEL,                        {}),           # Llama-3.3 70B       (Groq — dedicated planner bucket)
            ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free",  _OR_HEADERS),  # Nemotron 120B       (OpenRouter, different upstream)
            ("openrouter", "z-ai/glm-4.5-air:free",                  _OR_HEADERS),  # GLM-4.5 Air MoE     (OpenRouter, different upstream)
            ("openrouter", "openai/gpt-oss-20b:free",                 _OR_HEADERS),  # GPT-OSS 20B         (last resort, still coherent for planning)
        ],

        # ------------------------------------------------------------------
        # GENERATOR — 2-3x per post, prioritise throughput + diversity.
        # Medium models follow copywriting instructions well and have
        # much higher free-tier RPM than 70B+ models.
        # ------------------------------------------------------------------
        "generator": [
            ("groq",       GENERATOR_GROQ_MODEL,                              {}),           # Llama-3.1 8B        (Groq — highest RPM, separate from planner bucket)
            ("openrouter", GENERATOR_MODEL,                                   _OR_HEADERS),  # Mistral-Small 24B   (OpenRouter)
            ("openrouter", GENERATOR_MODEL_FALLBACK,                          _OR_HEADERS),  # Gemma-2 9B          (OpenRouter, very high limits)
            ("openrouter", "nvidia/nemotron-3-nano-30b-a3b:free",             _OR_HEADERS),  # Nemotron Nano 30B   (OpenRouter, NVIDIA upstream)
            ("openrouter", "openai/gpt-oss-20b:free",                         _OR_HEADERS),  # GPT-OSS 20B         (OpenRouter, OpenAI upstream)
            ("openrouter", "z-ai/glm-4.5-air:free",                          _OR_HEADERS),  # GLM-4.5 Air MoE     (OpenRouter, different upstream)
            ("openrouter", "meta-llama/llama-3.2-3b-instruct:free",          _OR_HEADERS),  # Llama-3.2 3B        (last resort)
        ],

        # ------------------------------------------------------------------
        # EVALUATOR — 2-3x per post, large models preferred.
        # Scoring reliability degrades below 70B.
        # Groq slot uses gpt-oss-120b — completely separate rate limit
        # bucket from planner's llama-3.3-70b-versatile.
        # ------------------------------------------------------------------
        "evaluator": [
            ("openrouter", EVALUATOR_MODEL,                           _OR_HEADERS),  # Nemotron 120B       (OpenRouter, best critic)
            ("openrouter", EVALUATOR_MODEL_FALLBACK,                  _OR_HEADERS),  # GPT-OSS 120B        (OpenRouter, strong fallback)
            ("groq",       EVALUATOR_GROQ_MODEL,                      {}),           # GPT-OSS 120B        (Groq — separate bucket from planner)
            ("openrouter", "z-ai/glm-4.5-air:free",                  _OR_HEADERS),  # GLM-4.5 Air MoE     (OpenRouter, different upstream)
            ("openrouter", "openai/gpt-oss-20b:free",                 _OR_HEADERS),  # GPT-OSS 20B         (medium, acceptable for eval)
            ("groq",       PLANNER_GROQ_MODEL,                        {}),           # Llama-3.3 70B       (Groq, shared with planner — true last resort)
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def call_llm(
    system_prompt: str,
    user_prompt: str,
    role: str = "generator",
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    chains = _build_chains()
    chain = chains.get(role, chains["generator"])

    last_err: Exception | None = None

    for provider, model, extra_headers in chain:
        if _is_cooling(provider, model):
            remaining = _cooldowns.get(f"{provider}:{model}", 0) - time.monotonic()
            logger.info(
                "Skipping %s/%s (cooling down, %.0fs left)",
                provider, model, remaining,
            )
            continue

        client = _get_client(provider)
        logger.info("Calling %s/%s for role=%s", provider, model, role)

        try:
            kwargs: dict = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if extra_headers:
                kwargs["extra_headers"] = extra_headers

            resp = await client.chat.completions.create(**kwargs)
            raw_content = resp.choices[0].message.content or ""

            # Strip <think>...</think> reasoning blocks from reasoning models
            content = _strip_reasoning(raw_content)

            if content != raw_content:
                logger.info(
                    "Stripped reasoning tags from %s/%s response "
                    "(%d → %d chars)",
                    provider, model, len(raw_content), len(content),
                )

            logger.info(
                "OK from %s/%s (role=%s, %d chars)",
                provider, model, role, len(content),
            )
            return content

        except RateLimitError as exc:
            retry_after = _extract_retry_after_seconds(exc)
            _set_cooldown(provider, model, retry_after)
            last_err = exc
            logger.warning("429 from %s/%s — trying next in chain", provider, model)
            import asyncio
            await asyncio.sleep(1.5)  # Stagger requests to allow TPM limit buckets to recover
            continue

        except AuthenticationError as exc:
            # Clear cached client so the next call re-reads the key from os.environ.
            _clients.pop(provider, None)
            last_err = exc
            key_preview = (
                os.environ.get("GROQ_API_KEY", "")[:12]
                if provider == "groq"
                else os.environ.get("OPENROUTER_API_KEY", "")[:12]
            )
            logger.error(
                "401 from %s/%s — API key may be wrong or missing "
                "(current key prefix: %s...). Client cache cleared.",
                provider, model, key_preview or "<empty>",
            )
            continue

        except Exception as exc:
            last_err = exc
            logger.warning("Error from %s/%s: %s — trying next", provider, model, exc)
            continue

    raise RuntimeError(
        f"All providers exhausted for role={role}. Last error: {last_err}"
    ) from last_err