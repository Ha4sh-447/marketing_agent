import os
from dotenv import load_dotenv

load_dotenv(override=True)


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# OpenRouter primary models (free tier)
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "google/gemma-4-31b-it:free")
GENERATOR_MODEL = os.getenv("GENERATOR_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

# OpenRouter secondary fallback (different free model)
PLANNER_MODEL_FALLBACK = os.getenv("PLANNER_MODEL_FALLBACK", "meta-llama/llama-3.2-3b-instruct:free")
GENERATOR_MODEL_FALLBACK = os.getenv("GENERATOR_MODEL_FALLBACK", "moonshotai/kimi-k2.6:free")
EVALUATOR_MODEL_FALLBACK = os.getenv("EVALUATOR_MODEL_FALLBACK", "qwen/qwen3-next-80b-a3b-instruct:free")

# Groq fallback models (fast, free, no-credit-card required)
PLANNER_GROQ_MODEL = os.getenv("PLANNER_GROQ_MODEL", "llama-3.1-8b-instant")
GENERATOR_GROQ_MODEL = os.getenv("GENERATOR_GROQ_MODEL", "llama-3.3-70b-versatile")
EVALUATOR_GROQ_MODEL = os.getenv("EVALUATOR_GROQ_MODEL", "llama-3.3-70b-versatile")

SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
SITE_NAME = os.getenv("SITE_NAME", "Marketing Agent")

MAX_SCRAPE_PAGES = int(os.getenv("MAX_SCRAPE_PAGES", "8"))
MAX_RETRIES_PER_POST = int(os.getenv("MAX_RETRIES_PER_POST", "5"))

DB_PATH = os.getenv("DB_PATH", "data/marketing.db")
