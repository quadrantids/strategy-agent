#!/bin/bash
# Strategy Agent — Double-click to start (Mac)
cd "$(dirname "$0")"
echo ""
echo "  Starting Strategy Agent..."
echo ""
python3 -m pip install flask openai qdrant-client fastembed -q 2>/dev/null
python3 agent.py
