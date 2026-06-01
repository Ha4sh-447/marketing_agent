import os
from dotenv import load_dotenv

load_dotenv(override=True)


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ---------------------------------------------------------------------------
# PLANNER — runs once per campaign. Needs strong structured JSON reasoning.
# Large models preferred. Quality > speed.
# ---------------------------------------------------------------------------
PLANNER_MODEL          = os.getenv("PLANNER_MODEL",          "google/gemma-4-31b-it:free")
PLANNER_MODEL_FALLBACK = os.getenv("PLANNER_MODEL_FALLBACK", "openai/gpt-oss-120b:free")   # 117B MoE, strong reasoning
PLANNER_GROQ_MODEL     = os.getenv("PLANNER_GROQ_MODEL",     "llama-3.3-70b-versatile")    # 70B — dedicated to planner only

# ---------------------------------------------------------------------------
# GENERATOR — runs 2-3x per post. Needs creativity + instruction-following.
# Medium models (8B-24B) sufficient for copywriting, 3-5x higher free RPM.
# ---------------------------------------------------------------------------
GENERATOR_MODEL          = os.getenv("GENERATOR_MODEL",          "mistralai/mistral-small-3.2-24b-instruct:free")
GENERATOR_MODEL_FALLBACK = os.getenv("GENERATOR_MODEL_FALLBACK", "google/gemma-2-9b-it:free")
GENERATOR_GROQ_MODEL     = os.getenv("GENERATOR_GROQ_MODEL",     "llama-3.1-8b-instant")   # Highest RPM on Groq, separate bucket from planner

# ---------------------------------------------------------------------------
# EVALUATOR — runs 2-3x per post. Needs analytical critical judgment.
# Large models preferred (70B+). Medium models as last resort only.
# ---------------------------------------------------------------------------
EVALUATOR_MODEL          = os.getenv("EVALUATOR_MODEL",          "nvidia/nemotron-3-super-120b-a12b:free")  # 120B, best critic
EVALUATOR_MODEL_FALLBACK = os.getenv("EVALUATOR_MODEL_FALLBACK", "openai/gpt-oss-120b:free")               # 117B MoE, strong fallback
EVALUATOR_GROQ_MODEL     = os.getenv("EVALUATOR_GROQ_MODEL",     "openai/gpt-oss-120b")                    # 120B on Groq — separate bucket from planner (70B)

SITE_URL  = os.getenv("SITE_URL",  "http://localhost:8000")
SITE_NAME = os.getenv("SITE_NAME", "Marketing Agent")

MAX_SCRAPE_PAGES     = int(os.getenv("MAX_SCRAPE_PAGES",     "8"))
MAX_RETRIES_PER_POST = int(os.getenv("MAX_RETRIES_PER_POST", "5"))

DB_PATH = os.getenv("DB_PATH", "data/marketing.db")