# Strategy Agent — Installation & Development Guide

## What This Is

AI-powered Strategy exam agent for PBS Executive MBA (Professor Luís Filipe Reis).
Web UI at localhost:8080. Paste exam questions, get iterated answers with vector search RAG.

## INSTALLATION — READ THIS CAREFULLY

When a user asks to install/setup/run this project, follow these steps EXACTLY.

### Step 1: Find a Compatible Python

**REQUIRED: Python 3.10, 3.11, 3.12, or 3.13 — 64-bit.**

Python 3.14 and 32-bit versions are NOT compatible with fastembed/onnxruntime.

Check what's available:
```bash
# Windows
py --list
py -3.12 --version
py -3.13 --version
py -3.11 --version
python --version

# Mac/Linux
python3 --version
python3.12 --version
```

If no compatible Python is found, install Python 3.12 64-bit:
- Windows: https://www.python.org/downloads/release/python-3129/ — download "Windows installer (64-bit)" — CHECK "Add to PATH"
- Mac: `brew install python@3.12` or download from python.org

**CRITICAL: DO NOT proceed with Python 3.14 or 32-bit Python. The vector search will fail.**

### Step 2: Create Virtual Environment (recommended)

```bash
# Use the compatible Python found in Step 1
python3.12 -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install flask openai anthropic python-dotenv qdrant-client fastembed
```

**ALL of these are REQUIRED. Do NOT skip any package.** If fastembed fails, you have the wrong Python version — go back to Step 1.

### Step 4: Create .env File

Ask the user for their Anthropic API key. Create `.env`:
```
ANTHROPIC_API_KEY=sk-ant-api03-THEIR_KEY_HERE
MODEL=claude-opus-4-6
```

If they don't have a key, tell them to get one at https://console.anthropic.com/settings/keys

### Step 5: Run

```bash
python agent.py
```

Browser opens at http://localhost:8080.

On Windows, if there are Unicode errors, set:
```bash
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python agent.py
```

## CRITICAL RULES — DO NOT VIOLATE

**PHILOSOPHY: Fix problems, don't work around them by removing features.**

If ANY dependency fails to install or ANY component doesn't work:
1. **Diagnose the root cause** (wrong Python version? network blocked? PATH issue? permissions?)
2. **Fix the root cause** (install correct Python, configure proxy, fix PATH, run as admin)
3. **NEVER remove features to work around an installation problem**

Specific rules:

1. **NEVER remove or skip vector search (fastembed, qdrant-client).** This is the core differentiator. Without it, this is just a basic prompt wrapper. If it fails, FIX IT.
2. **NEVER patch agent.py to remove imports, skip features, or add fallbacks.** The code works. The environment needs fixing, not the code.
3. **NEVER fall back to "just inject all text into the prompt."** That's the cop-out we explicitly don't want.
4. **If pip fails**, try: `python -m pip install`, or `pip install --user`, or use a venv, or fix the PATH.
5. **If fastembed won't install**, the Python version is wrong. Find or install Python 3.10-3.13 64-bit. Don't skip it.
6. **If network blocks HuggingFace**, try: `pip install --index-url https://pypi.org/simple/`, or ask user to connect to phone hotspot.
7. **If onnxruntime fails**, it's 32-bit Python. Install 64-bit.
8. **If git is not installed**, install it: `winget install Git.Git` (Windows) or `brew install git` (Mac).
9. **If anything else fails**, tell the user what went wrong and how to fix it. Don't silently degrade the system.
10. **The vector_db/ directory is pre-built.** It should NOT need rebuilding. If index_exists() returns True, do NOT rebuild.
11. **The embedding model (~600MB) downloads on first QUERY, not on startup.** This is normal. Tell the user to wait ~2 minutes on their first question.

## Architecture

```
Question → detect company → vector search (Qdrant, multilingual-e5-large)
  → 3 collections searched: article + company research + class notes
  → AI curator selects relevant chunks (GPT-5.4-mini)
  → Claude Opus generates answer (streaming)
  → Judge scores on 5 dimensions
  → Review if score < 88
  → Fact-check (surgical JSON corrections)
  → Final answer
```

## Key Files

- `agent.py` — Flask web app, ratchet loop, multi-model support
- `context_engine.py` — Qdrant vector search + AI curation
- `index.html` — Chat UI
- `companies/` — Deep research on 7 companies (~700 lines each)
- `articles/` — Exam case articles (the professor's handouts)
- `class_notes.txt` — 84 pages of professor's frameworks
- `vector_db/` — Pre-built Qdrant index (DO NOT DELETE)
- `.env` — API key (not in git)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `fastembed` won't install | Wrong Python version. Use 3.10-3.13 64-bit |
| `onnxruntime` wheel not found | Same — need 64-bit Python 3.10-3.13 |
| `index_exists()` returns False | Check vector_db/ directory exists with collection/ subdirs |
| Unicode errors on Windows | Set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` |
| Port 8080 in use | `PORT=8081 python agent.py` |
| API key invalid | Check .env file, no extra spaces or quotes around the key |
