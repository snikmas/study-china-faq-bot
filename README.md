# Scholarship FAQ — Study in China

A conversational FAQ chatbot for Russian students asking about scholarships and studying in China. Powered by Google Gemini.

Learning project. CLI now, Streamlit UI coming next.

## How It Works

The bot loads a structured knowledge base (`faq.json`) and a system prompt (`prompt.md`), injects them into every Gemini request, and answers user questions in Russian. If it can't find an answer, it says so and logs the question to `unknown_data.txt` for future knowledge base improvements.

## Setup

1. Create a `.env` file:
   ```
   GOOGLE_API_KEY=your_key_here
   ```

2. Activate the virtual environment and install dependencies:
   ```bash
   python -m venv myvenv
   source myvenv/bin/activate
   pip install google-genai python-dotenv streamlit
   ```

3. Run:
   ```bash
   python main.py
   ```

Type `0` to exit.

## Project Structure

```
faq.json          — knowledge base (14 topics, Q&A pairs)
prompt.md         — system instructions for the AI persona
main.py           — app entry point
unknown_data.txt  — auto-generated log of unanswered questions
```

## Roadmap

- [ ] Streamlit UI
- [ ] Deploy to Streamlit Cloud
