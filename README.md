# Scholarship FAQ — Study in China

A conversational FAQ chatbot for Russian students asking about scholarships and studying in China. Built with Streamlit + Google Gemini.

Learning project.

## How It Works

The bot loads a structured knowledge base (`faq.json`) and a system prompt (`prompt.md`), injects the full FAQ into every Gemini request as a system instruction, and answers questions in Russian via a Streamlit chat interface. If it can't find an answer, it says so and logs the question to `unknown_data.txt` for future knowledge base improvements.

## Setup

1. Create a `.env` file:
   ```
   GEMINI_API_KEY=your_key_here
   ```

2. Activate the virtual environment and install dependencies:
   ```bash
   python -m venv myvenv
   source myvenv/bin/activate
   pip install google-genai python-dotenv streamlit
   ```

3. Run:
   ```bash
   streamlit run main.py
   ```

## Project Structure

```
faq.json          — knowledge base (14 topics, Q&A pairs in Russian)
prompt.md         — system instructions defining the AI persona
main.py           — Streamlit app
unknown_data.txt  — auto-generated log of unanswered questions
```

## Roadmap

- [x] Gemini API integration
- [x] Streamlit chat UI
- [ ] Deploy to Streamlit Cloud
