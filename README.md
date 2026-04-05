# Strategy Agent — PBS Executive MBA

AI-powered exam answer generator for the Strategy course (Professor Luís Filipe Reis).

## What it does

Paste an exam question → the agent auto-detects the company, retrieves relevant context (case article + research data + class frameworks), generates an answer using the professor's gold standard format, reviews it, fact-checks numbers, and delivers an exam-ready response.

## Setup (2 minutes)

### 1. Install Python
- **Windows**: Download from [python.org](https://www.python.org/downloads/) — check "Add to PATH" during install
- **Mac**: Already installed, or `brew install python`

### 2. Get an API key
- Go to [Anthropic Console](https://console.anthropic.com/) → API Keys → Create Key
- Or use OpenAI: [platform.openai.com](https://platform.openai.com/api-keys)

### 3. Configure
```bash
cp .env.example .env
# Edit .env and paste your API key
```

### 4. Run
- **Mac**: Double-click `start.command`
- **Windows**: Double-click `start.bat`
- Or from terminal: `python agent.py`

Browser opens at http://localhost:8080. Paste your exam question and go.

## How it works

1. **Vector search** — Finds the most relevant context from 7 company profiles, case articles, and 84 pages of class notes (Qdrant + multilingual-e5-large embeddings)
2. **AI curation** — A fast model selects only the chunks relevant to your specific question
3. **Generation** — Claude Opus generates the answer in the professor's 3-step format (Keywords→Frameworks→Application)
4. **Review** — If score < 88, the answer is improved with targeted fixes
5. **Fact-check** — Every number is cross-referenced against source data

## Companies covered

Vista Alegre · Visabeira · NORS · Frulact · Tekever · DIGI · Super Bock

## Models supported

Switch models in the UI dropdown:
- **Claude Opus 4.6** (recommended for exam day — best quality)
- **Claude Sonnet 4.6** (faster, cheaper)
- **GPT-5.4 Mini** (fast, good for practice)
- **GPT-4o** (strong alternative)

## Exam day tips

1. Select **Claude Opus 4.6** for maximum quality
2. Paste the FULL question including role, time, and values
3. Wait for the answer to stream + fact-check
4. Click "Copy answer" to paste into your exam
5. Use follow-up questions: "expand the VRIN section" or "add more detail on Porter+"
