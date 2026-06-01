# 📊 Clinical Marketing Rating & Evaluation Guide

This guide details the exact objective scoring rubrics, point deduction checklists, and validation strategies used by the **Evaluator Agent** to review generated social media copy. 

By employing an **Objective Checklist Auditing System** rather than letting the LLM assign arbitrary subjective numbers, we eliminate "AI self-bias" (where models automatically rubber-stamp generic AI writing).

---

## 🎯 Target Optimization Standard
To complete successfully and exit the generation pipeline, a post must pass the **clinical quality standard**:
1. **Overall Score**: Must be **above 7.5 / 10** (`overall_score >= 7.5`).
2. **Individual Parameters**: **Every single** scoring criterion must be **above 7.0 / 10** (`score >= 7`).

If any criteria fall short, the post is flagged as **"Needs Polish"** and automatically sent back to the Generator for another round of guided optimization (up to 5 attempts).

---

## 🔍 Core Scoring Parameters & Deduction Rubrics

Every parameter starts with a perfect score of **10/10**. Specific, concrete deductions are applied by the Evaluator during auditing:

### 1. Brand Voice Alignment (`threshold: 7`)
*Ensures the post sounds authentic to the company and references genuine scraped product details rather than generic marketing speak.*
* **Deduction -3 pts**: Uses generic claims or platitudes that could fit any competitor in the space.
* **Deduction -2 pts**: Fails to reference at least one real product name, concrete feature, or metric from the scraped website data.
* **Deduction -2 pts**: Adopts a generic corporate "hype" tone rather than the actual website copy's voice guidelines.

### 2. Platform Fit (`threshold: 7`)
*Enforces platform conventions, layouts, and optimal length limits.*
* **Deduction -3 pts**: Lacks clean paragraph breaks or spacing (essential for scrollability on LinkedIn).
* **Deduction -2 pts**: Length violates platform standards:
  * **LinkedIn**: 1000–2000 characters (thought-leadership style).
  * **Twitter / X**: Under 280 characters (punchy hooks).
  * **Instagram**: 150–300 character caption (storytelling style).
* **Deduction -2 pts**: Hashtags are mixed inline in the post body rather than cleanly grouped in the dedicated hashtags block at the end.

### 3. Engagement Potential (`threshold: 7`)
*Measures how effectively the post hooks scrollers and retains attention.*
* **Deduction -3 pts**: Starts with a cliché, lazy question (e.g., *"What if you could..."*, *"Are you tired of..."*, *"In today's fast-paced world..."*).
* **Deduction -2 pts**: The call-to-action (CTA) is plain and uninspiring (e.g., just *"visit our website"* without context).
* **Deduction -2 pts**: Sentences are overly dense, academic, or hard to skim.

### 4. Human-Like Quality (`threshold: 7`)
*Eliminates the "AI fingerprint" and guarantees copy sounds genuinely human-written.*
* **Deduction -4 pts**: Contains ANY typical AI buzzword or transitional cliché:
  * *Banned Words*: `revolutionary`, `game-changer`, `cutting-edge`, `unlock potential`, `transformative`, `elevate`, `leverage`, `seamless`, `holistic`, `innovative`.
* **Deduction -3 pts**: Uses vague, empty preambles or transitions (e.g., *"Let's dive in"*, *"In the digital landscape"*).
* **Deduction -2 pts**: Uses more than 2 emojis (emoji spam is a massive AI tell).

### 5. Value Clarity (`threshold: 7`)
*Ensures the reader understands the product's primary utility and why it matters.*
* **Deduction -3 pts**: A first-time reader cannot easily explain what the product does in one simple sentence.
* **Deduction -2 pts**: Mentions benefits but omits the actual mechanism or proof point of *how* the value is achieved.

### 6. CTA Effectiveness (`threshold: 7`)
*Gauges the strength and motivational layout of the action step.*
* **Deduction -3 pts**: CTA is missing entirely, or is buried in the middle of a paragraph instead of being placed cleanly at the very end.
* **Deduction -2 pts**: CTA lacks motivating urgency or relevant value (e.g., missing a low-friction hook like *"try free"* or *"book a 10-min demo"*).

### 7. Format Compliance (`threshold: 7`)
*Ensures post text is pristine, clean, and ready for immediate copying and pasting.*
* **Deduction -5 pts**: Contains raw `<think>` tags, system preambles (e.g., *"Here is your post:"*), meta-commentaries, or raw markdown bold blocks (`**`).

---

## 🛡️ Preventing AI Self-Bias & Enforcing Iteration

To guarantee quality, the pipeline implements **Attempt 1 Polish Enforcer**:
* **The Refinement Loop**: By design, the first generation is almost never perfect. On **Attempt 1**, the Evaluator will *always* flag at least two specific polishing targets and force-fail at least one parameter below `7.0`. 
* **The Result**: The pipeline is guaranteed to trigger a second iteration, utilizing the Generator's guided-revision capability to refine the draft into a highly polished, authentic piece of copy.

---

## 📈 Quality Grade Interpretations

In the frontend results panel, scores are categorized into high-fidelity rating badges:
* **🥇 Excellent** (`overall_score >= 8.5`): Exceptionally creative copy, highly factual, perfect platform structure, completely indistinguishable from high-end copywriter work.
* **🥈 Good** (`overall_score >= 7.5`): High-quality, clean, compliant copy that effectively matches the brand reference.
* **🥉 Needs Polish** (`overall_score < 7.5`): Retained some cliché words or structural issues; sent back for refinement.
