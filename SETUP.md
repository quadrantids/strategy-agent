# Strategy Agent — Setup Instructions

## Option 1: Using Claude Code (recommended)

You need **Claude Code** (the CLI tool), NOT the regular Claude chat app.

Install Claude Code: https://claude.ai/code

Then open a terminal (Command Prompt or PowerShell on Windows) and run:

```
claude
```

Once Claude Code is running, paste this:

```
I need you to set up a strategy exam agent from GitHub.

Use the terminal (Bash tool) for ALL steps — do NOT create artifacts or write files through the chat.

Steps:
1. Run: git clone https://github.com/quadrantids/strategy-agent.git
   (if git is not installed, download from https://git-scm.com and install it first)
2. Run: cd strategy-agent
3. Create the file strategy-agent/.env with this exact content:
   ANTHROPIC_API_KEY=PASTE_YOUR_KEY_HERE
   MODEL=claude-opus-4-6
4. Run: pip install flask openai anthropic python-dotenv qdrant-client fastembed
   (if pip fails, try: python -m pip install ...)
5. Run: python agent.py
6. Tell me when the browser opens at http://localhost:8080
```

Replace PASTE_YOUR_KEY_HERE with the API key you were given.

---

## Option 2: Manual Setup (Windows)

### Step 1: Install Python
1. Go to https://python.org/downloads
2. Download the latest version
3. Run the installer — **CHECK "Add Python to PATH"** (important!)
4. Click Install

### Step 2: Download the project
1. Go to https://github.com/quadrantids/strategy-agent
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP to your Desktop
4. You should have a folder: `Desktop/strategy-agent-master/`

### Step 3: Add your API key
1. Open the folder `strategy-agent-master`
2. Find the file `.env.example`
3. Copy it and rename the copy to `.env` (just `.env`, no other extension)
4. Right-click `.env` → Open with → Notepad
5. Replace the line `ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY_HERE` with your actual key
6. Save and close

### Step 4: Run
1. Double-click `start.bat`
2. Wait for dependencies to install (first time only, ~1 minute)
3. Your browser opens at http://localhost:8080
4. Paste your exam question and go

---

## On Exam Day

If the app isn't running, open a terminal and run:

```
cd Desktop/strategy-agent-master
python agent.py
```

Then open http://localhost:8080 in your browser.

If it says "module not found", run this first:
```
pip install flask openai anthropic python-dotenv qdrant-client fastembed
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "python not found" | Reinstall Python, check "Add to PATH" |
| "No module named flask" | Run: `pip install flask openai anthropic python-dotenv qdrant-client fastembed` |
| "Invalid API key" | Check `.env` file has correct key, no extra spaces or quotes |
| Port 8080 in use | Close other apps using that port, or edit agent.py line with `PORT` |
| Blank page after loading | Wait 10 seconds — the embedding model loads on first use |
| "git not found" | Install git from https://git-scm.com or download ZIP instead |
