@echo off
echo.
echo   Starting Strategy Agent...
echo.
python -m pip install flask openai qdrant-client fastembed -q 2>nul
python agent.py
pause
