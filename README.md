# Study in China FAQ Assistant

Trust-first bilingual FAQ assistant for study-abroad agencies. Built with
Streamlit, Google Gemini, Telegram, and Pydantic.

This repository is a portfolio case study, not a claim of production deployment
or real client usage. It demonstrates a safer FAQ pattern: Gemini classifies the
visitor's question, but the final factual answer comes only from reviewed stored
FAQ records with citations.

## Current Status

The local build is ready to run and inspect. Deterministic tests pass offline,
the Streamlit app boots locally, and English/Russian screenshots are included:

- [English screenshot](assets/app-en.png)
- [Russian screenshot](assets/app-ru.png)

Public deployment, real credentials, and client-specific data remain
user-owned steps.

## Product Purpose

The app helps a small study-abroad agency answer common English/Russian
questions about studying in China while routing uncertain or high-risk questions
to a human. It is designed as a reusable demo of:

- Bilingual FAQ intake.
- Stored, cited answers instead of free-form model advice.
- Clear unsupported and human-confirmation states.
- Optional inquiry handoff to an owner Telegram chat.

## How It Works

- Loads 15 validated English/Russian FAQ records from `faq.json`.
- Loads official source metadata from `sources.json`.
- Uses Gemini only to select matching FAQ IDs from the stored catalog.
- Resolves selected IDs to stored answers, citations, and risk warnings.
- Returns unsupported or temporary-failure states when the classifier output is
  unsafe, unknown, low-confidence, or malformed.
- Optionally sends a consented inquiry to a configured Telegram owner chat.
- Does not write visitor questions or lead history to local files.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [PRIVACY.md](PRIVACY.md) for the
runtime design and data behavior.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   venv/bin/python -m pip install -r requirements.txt
   ```

2. Configure secrets:
   ```bash
   cp .env.example .env
   ```
   Replace the placeholder values in `.env` with real credentials. If you copy
   `.env.example` without editing it, chat and Telegram handoff stay disabled.
   For a deployed Streamlit site, add the same keys to the site's
   secrets/environment settings; local `.env` files are not automatically
   available on the hosted site.

3. Run:
   ```bash
   venv/bin/streamlit run main.py
   ```

Telegram handoff is optional. If Telegram settings are missing, the FAQ chat still works.

## Checks And Evaluation

```bash
venv/bin/python -m pytest -q
venv/bin/python -m compileall -q main.py app tests evals
venv/bin/python -m json.tool faq.json
venv/bin/python -m json.tool sources.json
venv/bin/python -m json.tool evals/cases.json
```

The deterministic tests run offline and do not require Gemini credentials.

Optional live evaluation requires real Gemini configuration and makes live model
calls:

```bash
venv/bin/python evals/run_live.py
```

If `GEMINI_API_KEY` is missing or still a placeholder, the live evaluator exits
nonzero with a clear configuration message before making model calls.

## Deployment

Deployment is intentionally user-owned. Configure real secrets in the hosting
platform, not in the repository:

- `GEMINI_API_KEY` for the FAQ classifier.
- `GEMINI_MODEL` if overriding the default model.
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`, and
  `AGENCY_CONTACT_FALLBACK` only if Telegram handoff is needed.

The demo does not include a production CRM, database, authentication system, or
admin console.

## Project Structure

```
main.py          - Streamlit UI
app/             - configuration, schemas, classifier, resolver, Telegram handoff
faq.json         - reviewed bilingual FAQ records
sources.json     - official source metadata
evals/cases.json - bilingual evaluation contract
tests/           - deterministic unit and integration tests
assets/          - local portfolio screenshots
ARCHITECTURE.md  - runtime and trust-boundary notes
PRIVACY.md       - local data behavior and limitations
```

## Boundaries

- Not legal, visa, or admissions advice.
- No live web search at answer time.
- No free-form model-generated factual answers.
- No guarantee that stored source facts remain current after their review dates.
- No production CRM/database in this demo.
- Deployment and real credentials are user-owned steps.
