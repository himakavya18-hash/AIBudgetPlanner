# AI Budget Planner

A Flask and SQLite budget planner with authentication, income and expense tracking, budgets, savings goals, recurring payments, reports, and Mistral-powered insights.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Open `http://127.0.0.1:5000`. Set `MISTRAL_API_KEY` in `.env` to enable Mistral features; safe rule-based fallbacks work without it. Voice entry uses the browser's speech-recognition interface and sends the transcript to the AI parser.

## Structure

```text
app/
  blueprints/       # auth, dashboard, transactions, goals, ai, reports
  static/css/       # Bootstrap enhancements
  templates/        # page templates grouped by feature
  models.py         # SQLAlchemy models
  config.py         # environment-backed configuration
run.py              # development entry point
```
