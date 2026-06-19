# Study in China FAQ Assistant

Trust-first bilingual FAQ assistant for study-abroad agencies. Built with Streamlit, Google Gemini, and Pydantic.

This is a portfolio case study: Gemini classifies questions, but factual answers come only from reviewed stored FAQ records with citations.

## How It Works

- Loads 15 validated English/Russian FAQ records from `faq.json`.
- Loads official source metadata from `sources.json`.
- Uses Gemini only to select matching FAQ IDs.
- Renders stored answers, citations, verification dates, and risk warnings.
- Optionally sends a consented inquiry to a Telegram owner chat.
- Does not write visitor questions or lead history to local files.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure secrets:
   ```bash
   cp .env.example .env
   ```

3. Run:
   ```bash
   streamlit run main.py
   ```

Telegram handoff is optional. If Telegram settings are missing, the FAQ chat still works.

## Checks

```bash
python -m pytest -q
python -m compileall -q main.py app tests evals
python -m json.tool faq.json
python -m json.tool sources.json
```

## Project Structure

```
main.py          - Streamlit UI
app/             - configuration, schemas, classifier, resolver, Telegram handoff
faq.json         - reviewed bilingual FAQ records
sources.json     - official source metadata
evals/cases.json - bilingual evaluation contract
tests/           - deterministic unit and integration tests
```

## Boundaries

- Not legal, visa, or admissions advice.
- No live web search at answer time.
- No production CRM/database in this demo.
- Deployment and real credentials are user-owned steps.
