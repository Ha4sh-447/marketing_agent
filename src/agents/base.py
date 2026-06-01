"""
LLM wrapper with multi-provider support and robust rate limiting.

Provider priority: OpenRouter (primary) → Groq → NVIDIA (fallback)

Rate-limiting strategy
──────────────────────
1. Pre-request throttle — minimum interval per provider avoids 429s proactively.
2. 429 handling — parse Retry-After, sleep, retry same model once, then fall
   through to the next entry in the chain.
3. Per-model cooldown — after a second 429 the model is shelved for the
   Retry-After period (or 60 s default) and skipped on subsequent calls.
4. Auth healing — on 401 the cached client is evicted so the next call
   re-reads the API key from os.environ (picks up .env changes).
"""

import os
import re
import time
import random
import asyncio
import logging
from openai import AsyncOpenAI, RateLimitError, AuthenticationError

from src.config import (
    OPENROUTER_BASE_URL,
    NVIDIA_BASE_URL,
    GROQ_BASE_URL,
    MISTRAL_BASE_URL,
    SITE_URL,
    SITE_NAME,
    PLANNER_MODEL,
    GENERATOR_MODEL,
    EVALUATOR_MODEL,
    PLANNER_MODEL_FALLBACK,
    GENERATOR_MODEL_FALLBACK,
    EVALUATOR_MODEL_FALLBACK,
    GENERATOR_MISTRAL_MODEL,
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

    Safety: if stripping unclosed tags would erase everything, fall back
    to extracting content from inside the think block instead.
    """
    # 1. Strip properly closed <think>…</think> blocks
    text = _THINK_RE.sub("", text)

    # 2. Handle unclosed <think> — but don't nuke the entire output
    if _THINK_UNCLOSED_RE.search(text):
        candidate = _THINK_UNCLOSED_RE.sub("", text).strip()
        if candidate:
            text = candidate
        else:
            inner = re.sub(r"^<think>\s*", "", text, flags=re.DOTALL).strip()
            if inner:
                logger.warning(
                    "Unclosed <think> covers entire output (%d chars). "
                    "Recovering content from inside the tag.",
                    len(text),
                )
                text = inner
            else:
                logger.warning(
                    "Unclosed <think> with no recoverable content (%d chars).",
                    len(text),
                )
                text = ""

    return text.strip()


# ---------------------------------------------------------------------------
# Client pool  (keyed by provider; cleared on auth failure so it self-heals)
# ---------------------------------------------------------------------------

_clients: dict[str, AsyncOpenAI] = {}

_PROVIDER_CONFIG = {
    "openrouter": ("OPENROUTER_API_KEY", OPENROUTER_BASE_URL),
    "mistral":    ("MISTRAL_API_KEY",    MISTRAL_BASE_URL),
    "nvidia":     ("NVIDIA_API_KEY",     NVIDIA_BASE_URL),
    "groq":       ("GROQ_API_KEY",       GROQ_BASE_URL),
}


def _get_client(provider: str) -> AsyncOpenAI:
    """
    Return a cached AsyncOpenAI client for *provider*.

    API key is read fresh from os.environ on every call so that a live
    .env edit + uvicorn hot-reload is picked up without a restart.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)

    if provider not in _PROVIDER_CONFIG:
        raise ValueError(f"Unknown provider: {provider}")

    key_env, base_url = _PROVIDER_CONFIG[provider]
    api_key = os.environ.get(key_env, "")

    # Evict cached client if the key has changed
    existing = _clients.get(provider)
    if existing is not None and existing.api_key != api_key:
        logger.info("API key changed for %s — recreating client", provider)
        del _clients[provider]

    if provider not in _clients:
        _clients[provider] = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "no-key-set",
            max_retries=0,
        )
        logger.info("Created new client for %s", provider)

    return _clients[provider]


# ---------------------------------------------------------------------------
# Pre-request throttle (per-provider minimum interval)
# ---------------------------------------------------------------------------

_provider_locks: dict[str, asyncio.Lock] = {}
_last_request_at: dict[str, float] = {}

# Conservative intervals — stay well under free-tier RPM limits
_MIN_INTERVAL: dict[str, float] = {
    "openrouter": 4.0,   # ~15 RPM  (free limit ≈ 20 RPM)
    "mistral":    1.0,   # ~60 RPM  (paid API, generous limits)
    "groq":       3.0,   # ~20 RPM  (free limit ≈ 30 RPM)
    "nvidia":     5.0,   # ~12 RPM  (conservative)
}


async def _throttle(provider: str) -> None:
    """Wait so consecutive requests to *provider* are spaced apart."""
    if provider not in _provider_locks:
        _provider_locks[provider] = asyncio.Lock()

    async with _provider_locks[provider]:
        now = time.monotonic()
        last = _last_request_at.get(provider, 0)
        interval = _MIN_INTERVAL.get(provider, 4.0)
        jitter = random.uniform(0.0, 0.5)
        wait = interval + jitter - (now - last)
        if wait > 0:
            logger.debug("Throttling %s: waiting %.1fs", provider, wait)
            await asyncio.sleep(wait)
        _last_request_at[provider] = time.monotonic()


# ---------------------------------------------------------------------------
# Per-model cooldown tracker
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


def _extract_retry_after(exc: Exception) -> int | None:
    """Parse Retry-After seconds from a 429 error."""
    # 1. HTTP response header
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
        if headers:
            val = headers.get("Retry-After") or headers.get("retry-after")
            if val:
                try:
                    return int(float(val))
                except ValueError:
                    pass

    # 2. Nested body metadata
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        retry = (
            body.get("error", {}).get("metadata", {}).get("retry_after_seconds")
        )
        if retry is not None:
            try:
                return int(float(retry))
            except (ValueError, TypeError):
                pass

    # 3. Regex fallback on string representation
    text = str(exc)
    match = re.search(r"retry.after[_\-]?seconds['\"]?\s*[:=]\s*([0-9.]+)", text, re.I)
    if match:
        try:
            return int(float(match.group(1)))
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# OpenRouter headers  (helps with free-tier priority)
# ---------------------------------------------------------------------------

def _openrouter_headers() -> dict[str, str]:
    return {
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }


# ---------------------------------------------------------------------------
# Fallback chains
# ---------------------------------------------------------------------------

def _build_chains() -> dict[str, list[tuple[str, str, dict]]]:
    or_h = _openrouter_headers()
    return {
        # PLANNER — runs once, quality > speed
        "planner": [
            ("openrouter", PLANNER_MODEL,          or_h),
            ("openrouter", PLANNER_MODEL_FALLBACK,  or_h),
            ("groq",       PLANNER_GROQ_MODEL,      {}),
            ("nvidia",     "google/gemma-4-31b-it",             {}),
            ("nvidia",     "meta/llama-3.3-70b-instruct",       {}),
        ],
        # GENERATOR — Mistral direct API primary, fast + great copywriting
        "generator": [
            ("mistral",    GENERATOR_MISTRAL_MODEL,     {}),  # Mistral Large (paid, fast)
            ("openrouter", GENERATOR_MODEL,          or_h),
            ("openrouter", GENERATOR_MODEL_FALLBACK,  or_h),
            ("groq",       GENERATOR_GROQ_MODEL,      {}),
            ("nvidia",     "google/gemma-4-31b-it",             {}),
        ],
        # EVALUATOR — structured checklist scoring; fast models sufficient
        "evaluator": [
            ("openrouter", EVALUATOR_MODEL,          or_h),
            ("openrouter", EVALUATOR_MODEL_FALLBACK,  or_h),
            ("groq",       EVALUATOR_GROQ_MODEL,      {}),
            ("nvidia",     "google/gemma-4-31b-it",              {}),
            ("nvidia",     "meta/llama-3.1-8b-instruct",         {}),
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
        # ── Skip models in cooldown ──────────────────────────────────
        if _is_cooling(provider, model):
            remaining = _cooldowns.get(f"{provider}:{model}", 0) - time.monotonic()
            logger.info(
                "Skipping %s/%s (cooling down, %.0fs left)",
                provider, model, remaining,
            )
            continue

        # ── Pre-request throttle ─────────────────────────────────────
        await _throttle(provider)

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

            # Strip reasoning tags
            content = _strip_reasoning(raw_content)

            if content != raw_content:
                logger.info(
                    "Stripped reasoning tags from %s/%s response "
                    "(%d → %d chars)",
                    provider, model, len(raw_content), len(content),
                )

            if not content:
                logger.warning(
                    "EMPTY response from %s/%s (role=%s) after stripping "
                    "reasoning tags. Raw length was %d chars. "
                    "Raw preview: %.200s",
                    provider, model, role, len(raw_content),
                    raw_content[:200],
                )
                continue

            logger.info(
                "OK from %s/%s (role=%s, %d chars)",
                provider, model, role, len(content),
            )
            return content

        except RateLimitError as exc:
            retry_after = _extract_retry_after(exc)
            wait_secs = retry_after if retry_after and retry_after > 0 else 15

            logger.warning(
                "429 from %s/%s — waiting %ds then retrying once",
                provider, model, wait_secs,
            )
            await asyncio.sleep(wait_secs + random.uniform(0.5, 2.0))

            # ── One retry on the same model ──────────────────────────
            try:
                await _throttle(provider)
                resp = await client.chat.completions.create(**kwargs)
                raw_content = resp.choices[0].message.content or ""
                content = _strip_reasoning(raw_content)
                if content:
                    logger.info(
                        "OK from %s/%s on retry (role=%s, %d chars)",
                        provider, model, role, len(content),
                    )
                    return content
                logger.warning("Empty response on retry from %s/%s", provider, model)
            except RateLimitError as exc2:
                retry_after2 = _extract_retry_after(exc2)
                _set_cooldown(provider, model, retry_after2)
                last_err = exc2
                logger.warning("429 again from %s/%s — cooling down, trying next", provider, model)
                continue
            except Exception as exc2:
                last_err = exc2
                logger.warning("Error on retry from %s/%s: %s", provider, model, exc2)
                continue

            last_err = exc
            continue

        except AuthenticationError as exc:
            _clients.pop(provider, None)
            last_err = exc
            key_name = _PROVIDER_CONFIG.get(provider, ("?",))[0]
            key_preview = os.environ.get(key_name, "")[:12]
            logger.error(
                "401 from %s/%s — API key may be wrong (%s: %s...). "
                "Client cache cleared.",
                provider, model, key_name, key_preview or "<empty>",
            )
            continue

        except Exception as exc:
            last_err = exc
            logger.warning("Error from %s/%s: %s — trying next", provider, model, exc)
            continue

    raise RuntimeError(
        f"All providers exhausted for role={role}. Last error: {last_err}"
    ) from last_err