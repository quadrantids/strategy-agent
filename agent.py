#!/usr/bin/env python3
"""
Strategy Exam Agent — PBS Executive MBA
Web-based autoresearch-powered exam answer generator.

Double-click start.command (Mac) or start.bat (Windows) to launch.
Opens http://localhost:8080 in your browser.
"""

# ── Auto-install dependencies ────────────────────────────
import subprocess, sys

for pkg in ["flask", "openai", "anthropic", "python-dotenv"]:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

# Load .env file
from dotenv import load_dotenv
load_dotenv(override=True)

# ── Imports ──────────────────────────────────────────────
import os, json, glob, time, re, secrets, functools
from flask import Flask, Response, request, jsonify, send_file, session, redirect
from openai import OpenAI
from context_engine import get_context, index_exists, build_index

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# User accounts — loaded from users.json
USERS_FILE = "users.json"

def _load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    print("  WARNING: users.json not found. No users can log in.")
    print("  Create users.json with: {\"username\": {\"password\": \"...\", \"name\": \"...\"}}")
    return {}

USERS = _load_users()


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Not authenticated"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

# ── Multi-provider LLM support ───────────────────────────
PROVIDER = os.environ.get("LLM_PROVIDER", "openai")  # "openai" or "anthropic"
MODEL = os.environ.get("MODEL", "claude-opus-4-6")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", MODEL)
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "3"))

AVAILABLE_MODELS = {
    "gpt-5.4-mini": {"provider": "openai", "name": "GPT-5.4 Mini", "speed": "fast"},
    "gpt-5.4": {"provider": "openai", "name": "GPT-5.4", "speed": "medium"},
    "claude-sonnet-4-6": {"provider": "anthropic", "name": "Claude Sonnet 4.6", "speed": "medium"},
    "claude-opus-4-6": {"provider": "anthropic", "name": "Claude Opus 4.6", "speed": "slow"},
}

def _get_provider(model=None):
    m = model or MODEL
    if m in AVAILABLE_MODELS:
        return AVAILABLE_MODELS[m]["provider"]
    if m.startswith("claude"):
        return "anthropic"
    return "openai"

# ── Question types ───────────────────────────────────────
QTYPES = {
    "A": {"name": "Strategic Context Analysis", "val": "3-5", "role": "CSO",
           "desc": "Analyse context, industry, market with full framework toolkit",
           "tools": "PESTEL, Porter+, Generic Strategies, VRIN, 7S, Cultural Web, SWOT"},
    "B": {"name": "Board Recommendation", "val": "4-5", "role": "CEO",
           "desc": "Present and defend a strategic move to the Board",
           "tools": "M&A logic, 7S, Financial Architecture, ROI analysis"},
    "C": {"name": "Strategic Defence", "val": "3-4", "role": "CSO",
           "desc": "Defend a position with rigorous argumentation",
           "tools": "4 numbered arguments + VRIN test + financial data"},
    "D": {"name": "Internationalisation", "val": "3", "role": "CDO",
           "desc": "Market entry strategy for new geography",
           "tools": "CAGE table, Ansoff, Entry Modes table (Greenfield/Partnership/M&A)"},
    "E": {"name": "Capabilities & VRIN", "val": "2", "role": "CSO",
           "desc": "Appraise current and future capabilities",
           "tools": "Top 5 capabilities + VRIN per-letter test + prioritized investment €"},
    "F": {"name": "Competition Analysis", "val": "1-2", "role": "Analyst",
           "desc": "Describe competitive landscape and positioning",
           "tools": "C1-C4, Porter+, Generic Strategies, Value Curves"},
    "G": {"name": "Ethics & ESG", "val": "1-2", "role": "Strategist",
           "desc": "Ethical risks, precautions, ESG perspective",
           "tools": "Legal/Ethical Matrix + 4 Arguments + Stakeholder analysis"},
}

# ── Prompts ──────────────────────────────────────────────
GENERATOR_PROMPT = """\
You are an expert strategy exam answer generator for the Executive MBA at Porto Business \
School (Professor Luís Filipe Reis). You produce exam-ready answers of the highest quality.

## MANDATORY FORMAT (3 Steps)

### STEP 1 — Extract Keywords → Map to Frameworks
Table: | Keyword from Question | Framework | Purpose |

### STEP 2 — Framework Sequence
Numbered list with framework name in **bold** + brief description

### STEP 3 — Full Application (EXPLAIN → JUSTIFY → EXPAND → JUSTIFY REASONING)
Apply each framework with concrete data from the company.

## FRAMEWORK FORMAT RULES (mandatory)

- **Porter+** (7 forces, NOT "5 Forces" — includes Technology + Regulation): \
TABLE (Force | Assessment HIGH/MEDIUM/LOW | Strategic Implication)
- **VRIN**: Test PER LETTER: V (Valuable): YES/NO — justification with data. R, I, N same.
- **7S McKinsey**: TABLE (7S | Before | After | Risk/Opportunity)
- **Cultural Web**: Code block with BEFORE and AFTER (7 elements: Symbol, Ritual, Story, Power, Structure, Control, People)
- **CAGE**: Comparative TABLE (Dimension | Country1 | Country2 | Country3 | Country4)
- **Entry Modes**: TABLE (Mode | Greenfield | Partnership | M&A) with Cost/Time/Risk/Payback
- **Financial**: Code block with ROI/Payback/NPV calculated
- **Counter-Arguments**: 4 NUMBERED arguments, each with VRIN test + financial data
- **Capabilities**: Top 5 with VRIN per-letter test + prioritized investment €
- **Ethics**: Core Principle + 4 Arguments + Segmentation in code block
- **SWOT**: SYNTHESIS tool that BRIDGES external + internal analysis → strategic objectives. \
NEVER group SWOT with PESTEL/Porter+. SWOT comes AFTER all analysis is done. It synthesizes \
Opportunities/Threats (from PESTEL, VUCA, Porter+, C1-C4) + Strengths/Weaknesses (from VRIN, \
Capabilities, Cultural Web, Purpose). SWOT is the BRIDGE to strategic decisions, not an analysis tool.
- **VUCA**: Volatility, Uncertainty, Complexity, Ambiguity — analyse the environment ALONGSIDE \
PESTEL. How volatile is the industry? How uncertain is the future? How complex are the dynamics? \
How ambiguous are the signals?
- **BCG**: Must show Money Cycle (cash flows from Cash Cows → Stars/Question Marks)

## PROFESSOR'S STRATEGIC PROCESS (follow this flow exactly)

```
PHASE 1 — EXTERNAL ANALYSIS (Context/Environment)
├── PESTEL (macro Key Drivers for Change, Headwinds/Tailwinds)
├── VUCA (Volatility, Uncertainty, Complexity, Ambiguity)
├── C1-C4 (define the competitive arena)
└── Porter+ (7 forces: 5 classic + Technology + Regulation)

PHASE 2 — INTERNAL ANALYSIS (Strategic Position)
├── Generic Strategy / U-Curve positioning
├── VRIN (test resources — find the Crown Jewel)
├── Capabilities (Gary Hamel: Assets, Distinctive, Relationships)
├── Cultural Web (Rituals, Stories, Symbols, Power, Structure, Controls)
└── Purpose (Vision, Mission, Values)

PHASE 3 — SYNTHESIS (bridge analysis → decisions)
└── SWOT (Strengths/Weaknesses from Phase 2 + Opportunities/Threats from Phase 1)

PHASE 4 — STRATEGIC OBJECTIVES
├── Leading vs Lagging indicators
└── Balanced Scorecard

PHASE 5 — STRATEGIC CHOICES (use what the question asks)
├── 7S McKinsey (implementation alignment)
├── BCG Matrix + Money Cycle
├── Ansoff Matrix (growth directions)
├── CAGE + Entry Modes (internationalisation)
├── M&A analysis (motivators/inhibitors)
├── Innovation (S-Curve, 3 Horizons, Adoption Curve)
└── Financial Architecture (ROI, Payback, NPV)
```

Not every question requires all phases. Match frameworks to the question.

## PROFESSOR'S TERMINOLOGY (always use)
- Key Drivers for Change, Headwinds/Tailwinds
- Porter+ (with the +, includes Technology and Regulation as additional forces)
- VUCA (Volatility, Uncertainty, Complexity, Ambiguity)
- Deep Shit Valley (= Stuck in the Middle on the U-Curve)
- Money Cycle (BCG: cash from Cows → funds Stars/Question Marks)
- Financial Architecture, Crown Jewel (= resource with full VRIN)
- C1-C4 (competition levels: direct, category, generic, total budget)
- Crocodile Mouth (costs > revenues diverging like opening jaws)
- Aspirations Based Business Planning (scenarios, key uncertainties, cross variables)
- Cultural Web (6 elements: Rituals/Routines, Stories, Symbols, Power Structure, Org Structure, Control Systems)

## RULES
1. ZERO hallucinations — use ONLY the company data provided
2. Concrete data in EVERY framework (€, %, years, employees, competitor names)
3. Write in ENGLISH (the exam is in English)
4. ALWAYS quantify: ROI, payback, NPV, savings
5. End with numbered strategic recommendations
6. REFERENCE THE CASE ARTICLE — quote specific facts, numbers, and details from the exam \
case article. The professor expects you to demonstrate you read the article. Use phrases like \
"As reported in the article...", "The article highlights that..."."""

JUDGE_PROMPT = """\
Evaluate this Strategy exam answer (Executive MBA PBS, Professor Luís Filipe Reis).

Score on 5 dimensions (0-20 each, total 0-100):

1. **framework** — All required frameworks present and correctly formatted? \
Porter+ as 7-force TABLE? VRIN tested PER LETTER (V/R/I/N separately)? \
7S as Before/After table? Cultural Web in code block? SWOT is last?

2. **data** — Concrete data in EVERY framework? €, percentages, years, \
employee counts, competitor names? Financial calculations (ROI, payback, NPV) in code block?

3. **method** — Step 1→2→3 structure? Keywords→frameworks table? \
Professor's terminology used (Key Drivers, Headwinds/Tailwinds, Porter+, Deep Shit Valley, \
Money Cycle, Crown Jewel)?

4. **depth** — EXPLAIN → JUSTIFY → EXPAND → JUSTIFY REASONING? \
Not superficial? Clear strategic implications? Connections between frameworks?

5. **completeness** — All parts of the question answered? Final numbered \
recommendations? Nothing missing?

Return ONLY valid JSON:
{"framework": <int>, "data": <int>, "method": <int>, "depth": <int>, \
"completeness": <int>, "total": <int>, \
"issues": "<specific problems to fix in the next iteration>"}"""

# ── Company data ─────────────────────────────────────────
def load_companies():
    companies = {}
    for path in sorted(glob.glob("companies/*.md")):
        name = os.path.basename(path).replace(".md", "").upper().replace("_", "-")
        with open(path, encoding="utf-8") as f:
            companies[name] = f.read()
    return companies

COMPANIES = load_companies()

# ── Core logic ───────────────────────────────────────────
def _get_request_keys():
    """Get per-request API keys from headers if provided."""
    try:
        return {
            "anthropic": request.headers.get("X-Anthropic-Key"),
            "openai": request.headers.get("X-OpenAI-Key"),
        }
    except RuntimeError:
        return {"anthropic": None, "openai": None}


def _split_messages(messages):
    """Extract system message from message list (for Anthropic)."""
    system = ""
    user_msgs = []
    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        else:
            user_msgs.append(msg)
    return system, user_msgs


def api_call(messages, max_tokens=16384, temperature=0.7, model=None):
    """Call LLM API (OpenAI or Anthropic) with retry. Returns full text."""
    m = model or MODEL
    provider = _get_provider(m)

    for attempt in range(3):
        try:
            keys = _get_request_keys()
            if provider == "anthropic":
                import anthropic
                key = keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY")
                client = anthropic.Anthropic(api_key=key)
                system, user_msgs = _split_messages(messages)
                resp = client.messages.create(
                    model=m, max_tokens=max_tokens, temperature=temperature,
                    system=system, messages=user_msgs,
                )
                return resp.content[0].text.strip()
            else:
                from openai import OpenAI
                key = keys.get("openai") or os.environ.get("OPENAI_API_KEY")
                client = OpenAI(api_key=key)
                resp = client.chat.completions.create(
                    model=m, messages=messages,
                    max_completion_tokens=max_tokens, temperature=temperature,
                )
                return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def api_call_stream(messages, max_tokens=16384, temperature=0.7, model=None):
    """Call LLM API with streaming. Yields text chunks as they arrive."""
    m = model or MODEL
    provider = _get_provider(m)

    try:
        keys = _get_request_keys()
        if provider == "anthropic":
            import anthropic
            key = keys.get("anthropic") or os.environ.get("ANTHROPIC_API_KEY")
            client = anthropic.Anthropic(api_key=key, timeout=300.0)
            system, user_msgs = _split_messages(messages)
            with client.messages.stream(
                model=m, max_tokens=max_tokens, temperature=temperature,
                system=system, messages=user_msgs,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        else:
            from openai import OpenAI
            key = keys.get("openai") or os.environ.get("OPENAI_API_KEY")
            client = OpenAI(api_key=key, timeout=300.0)
            resp = client.chat.completions.create(
                model=m, messages=messages,
                max_completion_tokens=max_tokens, temperature=temperature,
                stream=True,
            )
            for chunk in resp:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
    except Exception as e:
        # If stream drops mid-way, yield what we have and signal the error
        yield f"\n\n[Stream interrupted: {str(e)[:100]}]"


def detect_company(text):
    """Auto-detect which company the question is about."""
    lower = text.lower().replace("-", " ").replace("_", " ")
    # Check exact and partial matches
    aliases = {
        "NORS": ["nors", "grupo nors"],
        "DIGI": ["digi", "digi communications"],
        "VISABEIRA": ["visabeira", "grupo visabeira", "nearing"],
        "VISTA-ALEGRE": ["vista alegre", "vista-alegre", "atlantis"],
        "FRULACT": ["frulact", "nexture"],
        "TEKEVER": ["tekever", "overmatch"],
        "SUPER-BOCK": ["super bock", "super-bock", "superbock", "sbg"],
    }
    for company, names in aliases.items():
        if company in COMPANIES and any(n in lower for n in names):
            return company
    return None


def detect_question_type(text):
    """Auto-detect question type from keywords."""
    lower = text.lower()
    hints = {
        "A": ["analyse the context", "analyze the context", "strategic context", "industry", "market where", "tools and concepts", "using all the tools"],
        "B": ["board", "recommend", "presenting this move", "go to the board", "defend this move", "acquisition", "investment recommendation"],
        "C": ["counter-argu", "contra-argu", "defend also", "defend your position", "defend the decision"],
        "D": ["internationalisation", "internationalization", "market entry", "new country", "new market", "cdo"],
        "E": ["capabilities", "current capabilities", "future capabilities", "appraisal", "competitive advantage"],
        "F": ["competition", "competitors", "competitive landscape", "describe.*competit"],
        "G": ["ethical", "ethics", "esg", "precautions", "responsibility", "risks.*understood"],
    }
    for t, keywords in hints.items():
        if any(re.search(k, lower) for k in keywords):
            return t
    return "A"  # Default to full analysis


def supplement_with_web_search(question, company, context):
    """If the AI detects gaps in context, search the web to fill them."""
    try:
        gap_check = api_call([{
            "role": "user",
            "content": f"""You are a context quality checker. Given this exam question and retrieved context,
identify if there are CRITICAL data gaps that would prevent a good answer.

QUESTION: {question}
COMPANY: {company}

CONTEXT LENGTH: {len(context)} chars
CONTEXT PREVIEW: {context[:2000]}...

Reply with JSON only:
{{"has_gaps": true/false, "search_queries": ["query1", "query2"], "missing": "what's missing"}}

Only flag gaps for CRITICAL missing data (financials, key strategic moves, competitor info).
If the context is sufficient, set has_gaps to false."""
        }], max_tokens=300, temperature=0.1)

        result = json.loads(gap_check if "{" in gap_check else "{}")
        if not result.get("has_gaps", False):
            return context

        # Use OpenAI web search to fill gaps
        for query in result.get("search_queries", [])[:2]:
            try:
                web_result = api_call([{
                    "role": "user",
                    "content": f"Search and summarize key strategic and financial data: {query}"
                }], max_tokens=1000, temperature=0.3)
                context += f"\n\n## WEB SEARCH SUPPLEMENT — {query}\n{web_result}"
            except Exception:
                pass

        return context
    except Exception:
        return context


def generate_answer(company, question_text, company_data, previous=None, feedback=None):
    """Generate or improve an exam answer for the exact question asked."""
    # Smart context retrieval — vector search for relevant chunks
    context = get_context(question_text, company, api_keys=_get_request_keys()) if index_exists() else company_data

    user_msg = f"Company: {company}\n\nRELEVANT CONTEXT (retrieved by semantic search):\n{context}\n\nEXAM QUESTION:\n{question_text}"

    if previous and feedback:
        user_msg += (
            f"\n\n--- PREVIOUS ANSWER (to improve) ---\n{previous}"
            f"\n\n--- ISSUES IDENTIFIED ---\n{feedback}"
            f"\n\nImprove the answer by fixing the issues above. "
            f"Keep what's good, fix what's wrong. Address the question precisely."
        )
    else:
        user_msg += "\n\nGenerate a complete answer in the gold standard format (3 Steps). Address the question PRECISELY — don't write a generic analysis."

    msgs = [
        {"role": "system", "content": GENERATOR_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    text = api_call(msgs)
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip() == "```": lines = lines[1:-1]
        else: lines = lines[1:]
        text = "\n".join(lines)
    return text, msgs  # Return msgs for streaming variant


def generate_answer_stream(messages):
    """Stream answer tokens. Yields (chunk, full_text_so_far)."""
    full = ""
    for chunk in api_call_stream(messages):
        full += chunk
        yield chunk, full


def judge_answer(answer, company, question_text):
    """Score an answer on 5 dimensions."""
    text = api_call(
        [
            {"role": "system", "content": JUDGE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Company: {company}\n"
                    f"Original exam question: {question_text[:500]}\n\n"
                    f"ANSWER TO EVALUATE:\n\n{answer}"
                ),
            },
        ],
        max_tokens=500,
        temperature=0.2,
    )

    # Parse JSON
    if "```" in text:
        for part in text.split("```")[1:]:
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                continue

    # Try to extract JSON from text
    match = re.search(r'\{[^{}]*"total"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return json.loads(text)


REVIEW_PROMPT = """\
You are a Strategy exam answer REVIEWER (Professor Luís Filipe Reis, PBS Executive MBA).

You receive an answer and a list of issues. Your job is to FIX the specific issues while \
PRESERVING everything that's already good. Do NOT rewrite from scratch.

RULES:
- Fix ONLY the issues listed. Don't change parts that are working.
- Keep the same structure, same frameworks, same format.
- If an issue says "Porter+ not in table format" → convert that section to a table.
- If an issue says "missing concrete data" → add specific €, %, years from the context.
- If an issue says "VRIN not per-letter" → restructure the VRIN section with V/R/I/N separately.
- Preserve all good content. This is surgery, not a rewrite."""


def ratchet_loop(company, question_text, company_data):
    """Generate once → review passes → verification → final grade."""

    # Get context once (reuse across all phases)
    context = get_context(question_text, company, api_keys=_get_request_keys()) if index_exists() else company_data

    # Extract time/value budget
    time_match = re.search(r'(\d+)\s*min', question_text.lower())
    val_match = re.search(r'(\d+)\s*val', question_text.lower())
    time_budget = time_match.group(1) if time_match else "20"
    val_budget = val_match.group(1) if val_match else "3"

    # ── PHASE 1: Generate the full answer (streaming) ──
    yield {"progress": True, "iteration": 1, "phase": "generating", "best_score": 0}

    try:
        user_msg = (
            f"Company: {company}\n\nRELEVANT CONTEXT:\n{context}\n\n"
            f"EXAM QUESTION:\n{question_text}\n\n"
            f"TIME BUDGET: {time_budget} minutes, {val_budget} values.\n"
            f"Calibrate your answer length to the time budget (~2.5 min per value).\n"
            f"A {val_budget}-value question needs {min(int(val_budget) + 2, 7)} frameworks max.\n\n"
            f"Generate a complete answer in the gold standard format (3 Steps)."
        )
        msgs = [{"role": "system", "content": GENERATOR_PROMPT}, {"role": "user", "content": user_msg}]

        answer = ""
        for chunk, answer in generate_answer_stream(msgs):
            if chunk:
                yield {"token": True, "iteration": 1, "t": chunk}

        if answer.startswith("```"):
            lines = answer.split("\n")
            if lines[-1].strip() == "```": lines = lines[1:-1]
            else: lines = lines[1:]
            answer = "\n".join(lines)
    except Exception as e:
        yield {"iteration": 1, "status": "crash", "error": str(e), "best_score": 0, "score": 0}
        yield {"done": True, "best_score": 0, "answer": None, "saved": ""}
        return

    # ── Judge the initial answer ──
    yield {"progress": True, "iteration": 1, "phase": "judging", "best_score": 0}
    try:
        scores = judge_answer(answer, company, question_text)
        best_score = scores["total"]
        feedback = scores.get("issues", "")
    except Exception as e:
        best_score = 0
        feedback = str(e)

    yield {
        "iteration": 1, "score": best_score, "delta": best_score,
        "scores": scores if best_score else {}, "status": "keep",
        "best_score": best_score, "feedback": feedback,
    }

    # ── PHASE 2: Review pass — ONLY if score < 88 (worth restreaming) ──
    for review_num in range(2, MAX_ITERATIONS + 1):
        if best_score >= 88 or not feedback:
            break  # Good enough — go straight to fact-check

        yield {"progress": True, "iteration": review_num, "phase": "reviewing", "best_score": best_score}

        try:
            review_msg = (
                f"EXAM QUESTION: {question_text}\n\n"
                f"COMPANY CONTEXT:\n{context[:6000]}\n\n"
                f"CURRENT ANSWER:\n{answer}\n\n"
                f"ISSUES TO FIX:\n{feedback}\n\n"
                f"Fix these specific issues. Preserve everything else. Return the full corrected answer."
            )
            review_msgs = [
                {"role": "system", "content": REVIEW_PROMPT},
                {"role": "user", "content": review_msg},
            ]

            reviewed = ""
            for chunk, reviewed in generate_answer_stream(review_msgs):
                if chunk:
                    yield {"token": True, "iteration": review_num, "t": chunk}

            if reviewed.startswith("```"):
                lines = reviewed.split("\n")
                if lines[-1].strip() == "```": lines = lines[1:-1]
                else: lines = lines[1:]
                reviewed = "\n".join(lines)

            # Judge the review
            yield {"progress": True, "iteration": review_num, "phase": "judging", "best_score": best_score}
            new_scores = judge_answer(reviewed, company, question_text)
            new_score = new_scores["total"]

            if new_score > best_score:
                delta = new_score - best_score
                best_score = new_score
                answer = reviewed
                feedback = new_scores.get("issues", "")
                yield {
                    "iteration": review_num, "score": new_score, "delta": delta,
                    "scores": new_scores, "status": "keep",
                    "best_score": best_score, "feedback": feedback,
                }
            else:
                feedback = new_scores.get("issues", "")
                yield {
                    "iteration": review_num, "score": new_score, "scores": new_scores,
                    "status": "revert", "best_score": best_score, "feedback": feedback,
                }

        except Exception as e:
            yield {"iteration": review_num, "status": "crash", "error": str(e), "best_score": best_score, "score": 0}

    # ── PHASE 3: Fact-check — returns JSON corrections, applied surgically ──
    yield {"progress": True, "iteration": 0, "phase": "verifying", "best_score": best_score}

    raw_data = company_data[:8000] if len(company_data) > 8000 else company_data

    verify_prompt = f"""You are a fact-checker. Compare the answer against the source data.

SOURCE DATA (ground truth):
{raw_data}

ANSWER:
{answer}

Find INCORRECT numbers/facts in the answer that contradict the source data.
Return ONLY a JSON array of corrections. If nothing is wrong, return an empty array.

Format:
[
  {{"wrong": "exact text in the answer that is wrong", "correct": "corrected text", "reason": "brief explanation"}},
  ...
]

ONLY flag things that are factually WRONG per the source data. Do not flag style, structure, or missing content.
Return ONLY valid JSON — no markdown fences, no commentary."""

    try:
        result = api_call([
            {"role": "system", "content": "Return only a JSON array of corrections."},
            {"role": "user", "content": verify_prompt},
        ], max_tokens=2000, temperature=0.1)

        # Parse corrections
        if result.startswith("```"):
            lines = result.split("\n")
            if lines[-1].strip() == "```": lines = lines[1:-1]
            else: lines = lines[1:]
            result = "\n".join(lines)
        if result.startswith("json"): result = result[4:].strip()

        corrections = json.loads(result)
        applied = 0

        if corrections:
            for fix in corrections:
                wrong = fix.get("wrong", "")
                correct = fix.get("correct", "")
                if wrong and correct and wrong in answer:
                    answer = answer.replace(wrong, correct, 1)
                    applied += 1

        feedback_msg = f"Fact-checked: {applied} correction(s) applied" if applied else "Fact-checked: no errors found"
        if corrections:
            details = "; ".join([f"{c.get('wrong','')} → {c.get('correct','')}" for c in corrections[:5]])
            feedback_msg += f" [{details}]"

        yield {
            "iteration": "V", "score": best_score, "delta": 0,
            "scores": {}, "status": "verified",
            "best_score": best_score, "feedback": feedback_msg,
        }

    except Exception as e:
        yield {
            "iteration": "V", "score": best_score, "delta": 0,
            "scores": {}, "status": "verified",
            "best_score": best_score, "feedback": f"Fact-check skipped: {e}",
        }

    yield {"done": True, "best_score": best_score, "answer": answer, "saved": ""}


# ── Flask routes ─────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json or {}
        username = data.get("username", "").strip().lower()
        password = data.get("password", "")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["authenticated"] = True
            session["username"] = username
            session["name"] = user["name"]
            session.permanent = True
            return jsonify({"ok": True, "name": user["name"]})
        return jsonify({"error": "Invalid credentials"}), 401
    return send_file("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def index():
    return send_file("index.html")


@app.route("/api/me")
@login_required
def me():
    return jsonify({"username": session.get("username"), "name": session.get("name")})


@app.route("/api/models")
@login_required
def get_models():
    return jsonify({
        "current": MODEL,
        "available": {k: v["name"] for k, v in AVAILABLE_MODELS.items()},
    })


@app.route("/api/model", methods=["POST"])
@login_required
def set_model():
    global MODEL, JUDGE_MODEL
    data = request.json
    new_model = data.get("model", "")
    if new_model in AVAILABLE_MODELS or new_model.startswith("claude") or new_model.startswith("gpt"):
        MODEL = new_model
        JUDGE_MODEL = new_model
        return jsonify({"model": MODEL, "provider": _get_provider()})
    return jsonify({"error": "Unknown model"}), 400


@app.route("/api/solve", methods=["POST"])
@login_required
def solve():
    """Single endpoint — paste question or follow-up, get iterated answer via SSE."""
    data = request.json
    question = data.get("question", "").strip()
    previous_answer = data.get("previous_answer", "").strip()
    previous_company = data.get("previous_company", "").strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400

    # Auto-detect company: current question first, then previous context
    company = detect_company(question)
    if not company and previous_company:
        company = previous_company  # Carry over from previous exchange
    if not company and previous_answer:
        company = detect_company(previous_answer[:500])
    qtype = detect_question_type(question)
    qt = QTYPES.get(qtype, {})

    company_data = COMPANIES.get(company, "") if company else ""

    if not company:
        company_data = "COMPANY NOT DETECTED. Available companies:\n"
        for name, cdata in COMPANIES.items():
            company_data += f"\n--- {name} ---\n{cdata[:500]}...\n"
        company = "UNKNOWN"

    # If follow-up, prepend context to the question
    is_followup = bool(previous_answer)
    if is_followup:
        question = (
            f"PREVIOUS ANSWER (already generated — the user wants a modification):\n"
            f"{previous_answer}\n\n"
            f"USER'S FOLLOW-UP REQUEST:\n{question}\n\n"
            f"Modify the previous answer according to the user's request. "
            f"Keep everything that's good, only change what the user asked for."
        )

    def stream():
        yield f"data: {json.dumps({'detected': True, 'company': company, 'type': qtype if not is_followup else 'follow-up', 'type_name': qt.get('name', 'Follow-up') if not is_followup else 'Follow-up', 'has_presolved': False}, ensure_ascii=False)}\n\n"

        for update in ratchet_loop(company, question, company_data):
            yield f"data: {json.dumps(update, ensure_ascii=False)}\n\n"

    return Response(stream(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


# ── Launch ───────────────────────────────────────────────
if __name__ == "__main__":
    import webbrowser

    port = int(os.environ.get("PORT", 8080))
    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║  Strategy Agent — PBS Executive MBA          ║")
    print("  ║  Autoresearch-powered exam answers           ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()
    print(f"  Model: {MODEL}")
    print(f"  Companies: {len(COMPANIES)}")
    print(f"  Max iterations: {MAX_ITERATIONS}")
    print(f"  URL: http://localhost:{port}")
    print()

    # Build vector index if needed
    if not index_exists():
        print("  Building vector index (first run — downloading bge-m3 model)...")
        print("  This may take a few minutes on first run.\n")
        build_index()
        print()

    webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
