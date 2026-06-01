# Marketing Agent

A robust, multi-agent system designed for automated marketing content generation. This project implements advanced architectural concepts including the **Actor-Critic pattern** for high-quality content generation and evaluation, and the **Harness Engineering pattern** to provide an evaluation and testing framework for robust LLM interactions.

## Architecture

The system uses a multi-tier fallback architecture (OpenRouter -> Groq) to ensure high availability and prevent rate-limiting stalls. It coordinates different AI agent roles to deliver a polished marketing campaign:

- **Planner Agent**: Analyzes the campaign requirements, sets the strategy, and breaks down the task into structured JSON reasoning.
- **Generator Agent (Actor)**: Follows the planner's instructions to creatively draft the marketing copy and content. 
- **Evaluator Agent (Critic)**: Reviews the generated content against the initial plan and marketing constraints, providing feedback or approving the content. 

This **Actor-Critic pattern** ensures that all generated copy is reviewed and refined before finalization, significantly increasing the reliability and quality of the output. The **Harness Engineering pattern** is utilized to systematically evaluate the agents against expected behaviors and metrics, providing structured guardrails and benchmarking.

## Features
- Multi-Agent Pipeline (Planner -> Generator -> Evaluator)
- Automated API Key Synchronization & Self-Healing
- Multi-tier LLM Provider Fallbacks (OpenRouter, Groq, Mistral, NVIDIA NIM)
- Per-Model Cooldown Tracking for Rate Limits
- FastAPI Backend & Web Interface
- SQLite/PostgreSQL Database Integration

## Setup Instructions

### 1. Prerequisites
- Python 3.10+
- Node.js (for frontend)
- Docker (optional, for deployment)

### 2. Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Ha4sh-447/marketing_agent.git
   cd marketing_agent
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Setup environment variables:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and provide your API keys for OpenRouter, Groq, Mistral, and/or NVIDIA.

### 3. Running the Application

**Backend (FastAPI)**
```bash
uvicorn main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

Configure your models and fallbacks in `.env`. The project supports fallback chains to avoid rate limits:
- Primary models are typically OpenRouter (e.g., `google/gemma-2-27b-it:free`)
- Fallback models can be Groq models (e.g., `llama-3.3-70b-versatile`) or other providers.

See `.env.example` for a complete list of required and optional configuration variables.
