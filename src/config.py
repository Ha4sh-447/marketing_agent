import os
from dotenv import load_dotenv

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Provider credentials
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")

# ---------------------------------------------------------------------------
# PLANNER — runs once per campaign. Needs strong structured JSON reasoning.
# Large models preferred. Quality > speed.
# ---------------------------------------------------------------------------
PLANNER_MODEL          = os.getenv("PLANNER_MODEL",          "google/gemma-4-31b-it:free")
PLANNER_MODEL_FALLBACK = os.getenv("PLANNER_MODEL_FALLBACK", "openai/gpt-oss-120b:free")

# ---------------------------------------------------------------------------
# GENERATOR — runs 2-3x per post. Needs creativity + instruction-following.
# Mistral direct API (primary), OpenRouter free-tier (fallback).
# ---------------------------------------------------------------------------
GENERATOR_MISTRAL_MODEL  = os.getenv("GENERATOR_MISTRAL_MODEL",  "mistral-large-latest")
GENERATOR_MODEL          = os.getenv("GENERATOR_MODEL",          "nvidia/nemotron-3-nano-30b-a3b:free")
GENERATOR_MODEL_FALLBACK = os.getenv("GENERATOR_MODEL_FALLBACK", "google/gemma-2-9b-it:free")

# ---------------------------------------------------------------------------
# EVALUATOR — runs 2-3x per post. Needs analytical critical judgment.
# Large models preferred (70B+). Medium models as last resort only.
# ---------------------------------------------------------------------------
EVALUATOR_MODEL          = os.getenv("EVALUATOR_MODEL",          "nvidia/nemotron-3-nano-30b-a3b:free")
EVALUATOR_MODEL_FALLBACK = os.getenv("EVALUATOR_MODEL_FALLBACK", "google/gemma-2-9b-it:free")

# ---------------------------------------------------------------------------
# Groq fallback models (separate provider, separate rate limits)
# ---------------------------------------------------------------------------
PLANNER_GROQ_MODEL   = os.getenv("PLANNER_GROQ_MODEL",   "llama-3.3-70b-versatile")
GENERATOR_GROQ_MODEL = os.getenv("GENERATOR_GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
EVALUATOR_GROQ_MODEL = os.getenv("EVALUATOR_GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# ---------------------------------------------------------------------------
# App settings
# ---------------------------------------------------------------------------
SITE_URL  = os.getenv("SITE_URL",  "http://localhost:8000")
SITE_NAME = os.getenv("SITE_NAME", "Marketing Agent")

MAX_SCRAPE_PAGES     = int(os.getenv("MAX_SCRAPE_PAGES",     "8"))
MAX_RETRIES_PER_POST = int(os.getenv("MAX_RETRIES_PER_POST", "5"))

DB_PATH = os.getenv("DB_PATH", "data/marketing.db")